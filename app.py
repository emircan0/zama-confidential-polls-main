# app.py
import os
import sqlite3
import uuid
import re
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash
from dotenv import load_dotenv
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature
import bleach
import requests

# ================== Load .env at the very beginning ==================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))

# ================== App Setup ==================
app = Flask(__name__)

# (debug) .env verification (temporary; remove after troubleshooting)
print("MAILGUN_DOMAIN:", os.getenv("MAILGUN_DOMAIN"))
k = os.getenv("MAILGUN_API_KEY")
print("MAILGUN_API_KEY set?", bool(k), "| len:", len(k or "0"))
print("MAILGUN_SENDER:", os.getenv("MAILGUN_SENDER"))

# SECRET_KEY
app.secret_key = os.environ.get('SECRET_KEY')
if not app.secret_key:
    print("⚠️ WARNING: SECRET_KEY is not set; generating a temporary key (add to .env for PROD)!")
    app.secret_key = 'dev-key-' + uuid.uuid4().hex
app.config['SECRET_KEY'] = app.secret_key

# General settings
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024  # 16KB
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)
app.config['SESSION_COOKIE_SECURE'] = False   # Set True in production (HTTPS)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

# ================== Mailgun Settings ==================
MAILGUN_DOMAIN = os.getenv("MAILGUN_DOMAIN")     # e.g., sandboxxxxx.mailgun.org
MAILGUN_API_KEY = os.getenv("MAILGUN_API_KEY")   # may not necessarily start with "key-" (new formats exist)
MAILGUN_SENDER  = os.getenv("MAILGUN_SENDER")    # e.g., Zama Poll <postmaster@...>

def send_mailgun_email(to: str, subject: str, html_content: str):
    """
    Sends an email via the Mailgun API.
    If you're using a sandbox domain, the 'to' address must be VERIFIED under Authorized Recipients in the Mailgun dashboard.
    """
    if not (MAILGUN_DOMAIN and MAILGUN_API_KEY and MAILGUN_SENDER):
        print("❌ Missing Mailgun env variables (MAILGUN_DOMAIN / MAILGUN_API_KEY / MAILGUN_SENDER).")
        raise RuntimeError("Mailgun env vars missing")

    url = f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages"
    try:
        resp = requests.post(
            url,
            auth=("api", MAILGUN_API_KEY),
            data={
                "from": MAILGUN_SENDER,
                "to": [to],
                "subject": subject,
                "html": html_content
            },
            timeout=15
        )
        print("📤 Mailgun response:", resp.status_code, resp.text[:500])
        resp.raise_for_status()  # raises on 4xx/5xx
        return resp
    except requests.RequestException as e:
        print("❌ Mailgun send error:", repr(e))
        raise

# ================== Database ==================
os.makedirs(app.instance_path, exist_ok=True)
DB_PATH = os.path.join(app.instance_path, "database.db")

def init_db():
    """Simple polling schema"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS polls (
            id TEXT PRIMARY KEY,
            question TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1,
            max_votes INTEGER DEFAULT 1000,
            expire_date TIMESTAMP
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS options (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            poll_id TEXT NOT NULL,
            option_text TEXT NOT NULL,
            votes INTEGER DEFAULT 0,
            FOREIGN KEY (poll_id) REFERENCES polls(id) ON DELETE CASCADE
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            poll_id TEXT NOT NULL,
            email TEXT NOT NULL,
            option_id INTEGER NOT NULL,
            confirmed BOOLEAN DEFAULT 0,
            ip_address TEXT,
            voted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (poll_id) REFERENCES polls(id) ON DELETE CASCADE,
            FOREIGN KEY (option_id) REFERENCES options(id) ON DELETE CASCADE,
            UNIQUE(poll_id, email)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS rate_limits (
            ip_address TEXT,
            endpoint TEXT,
            attempt_count INTEGER DEFAULT 1,
            last_attempt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (ip_address, endpoint)
        )
    ''')

    c.execute('CREATE INDEX IF NOT EXISTS idx_votes_poll ON votes(poll_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_votes_email ON votes(email)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_options_poll ON options(poll_id)')

    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

# ================== Helpers (Security) ==================
def validate_email(email: str) -> bool:
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email or "") is not None

def sanitize_input(text: str, max_length=500) -> str:
    if not text:
        return ""
    text = text.strip()[:max_length]
    return bleach.clean(text, tags=[], strip=True)

def get_client_ip():
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr

def check_rate_limit(endpoint, max_attempts=50, time_window=300):
    """
    50 attempts allowed in 5 minutes. Returns False if exceeded.
    """
    ip = get_client_ip()
    conn = get_db()
    c = conn.cursor()

    now = datetime.now()
    time_threshold = now - timedelta(seconds=time_window)
    c.execute("DELETE FROM rate_limits WHERE last_attempt < ?", (time_threshold,))

    res = c.execute(
        "SELECT attempt_count FROM rate_limits WHERE ip_address=? AND endpoint=?",
        (ip, endpoint)
    ).fetchone()

    if res:
        if res[0] >= max_attempts:
            conn.close()
            return False
        c.execute(
            "UPDATE rate_limits SET attempt_count=attempt_count+1, last_attempt=? WHERE ip_address=? AND endpoint=?",
            (now, ip, endpoint)
        )
    else:
        c.execute(
            "INSERT INTO rate_limits (ip_address, endpoint, attempt_count, last_attempt) VALUES (?, ?, 1, ?)",
            (ip, endpoint, now)
        )

    conn.commit()
    conn.close()
    return True

def rate_limit_decorator(endpoint_name):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not check_rate_limit(endpoint_name):
                flash("⚠️ Too many attempts. Please try again in a few minutes.", "danger")
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ================== Routes ==================
@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/create_poll", methods=["POST"])
@rate_limit_decorator('create_poll')
def create_poll():
    question = sanitize_input(request.form.get("question"), max_length=500)

    if not question or len(question) < 10:
        flash("⚠️ The question must be at least 10 characters.", "danger")
        return redirect(url_for("index"))

    # collect options
    raw_options = request.form.getlist("options")
    options = []
    for opt in raw_options:
        cleaned = sanitize_input(opt, max_length=200)
        if cleaned and len(cleaned) >= 2:
            options.append(cleaned)

    if len(options) < 2:
        flash("⚠️ Enter at least 2 valid options (min 2 characters each).", "danger")
        return redirect(url_for("index"))

    if len(options) > 10:
        flash("⚠️ You can add up to 10 options.", "danger")
        return redirect(url_for("index"))

    if len(options) != len(set(options)):
        flash("⚠️ Options must be distinct.", "danger")
        return redirect(url_for("index"))

    poll_id = uuid.uuid4().hex[:12]

    conn = get_db()
    try:
        c = conn.cursor()
        expire_date = datetime.now() + timedelta(days=30)
        c.execute(
            "INSERT INTO polls (id, question, expire_date) VALUES (?, ?, ?)",
            (poll_id, question, expire_date)
        )
        for opt in options:
            c.execute(
                "INSERT INTO options (poll_id, option_text) VALUES (?, ?)",
                (poll_id, opt)
            )
        conn.commit()
        flash("✅ Poll created.", "success")
        return redirect(url_for("poll", poll_id=poll_id))
    except Exception as e:
        conn.rollback()
        app.logger.error(f"create_poll error: {e}")
        flash("❌ Failed to create the poll.", "danger")
        return redirect(url_for("index"))
    finally:
        conn.close()

@app.route("/poll/<poll_id>")
def poll(poll_id):
    if not re.match(r'^[a-f0-9]{12}$', poll_id):
        flash("❌ Invalid poll ID.", "danger")
        return redirect(url_for("index"))

    conn = get_db()
    try:
        poll_row = conn.execute("SELECT * FROM polls WHERE id=?", (poll_id,)).fetchone()
        if not poll_row:
            flash("❌ Poll not found.", "danger")
            return redirect(url_for("index"))

        # is it active and not expired?
        if not poll_row["is_active"]:
            flash("⚠️ This poll is not active.", "warning")
            return redirect(url_for("results", poll_id=poll_id))

        if poll_row['expire_date']:
            expire_date = datetime.fromisoformat(poll_row['expire_date'])
            if datetime.now() > expire_date:
                flash("⚠️ This poll has expired.", "warning")
                return redirect(url_for("results", poll_id=poll_id))

        options = conn.execute(
            "SELECT * FROM options WHERE poll_id=? ORDER BY id",
            (poll_id,)
        ).fetchall()

        return render_template("poll.html", poll=poll_row, options=options)
    finally:
        conn.close()

@app.route("/vote/<poll_id>", methods=["POST"])
@rate_limit_decorator('vote')
def vote(poll_id):
    email = (request.form.get("email") or "").strip().lower()
    option_id = request.form.get("option")

    if not email or not validate_email(email):
        flash("⚠️ Please enter a valid email address.", "danger")
        return redirect(url_for("poll", poll_id=poll_id))

    if not option_id or not option_id.isdigit():
        flash("⚠️ Please choose an option.", "danger")
        return redirect(url_for("poll", poll_id=poll_id))

    conn = get_db()
    try:
        poll = conn.execute("SELECT is_active, expire_date FROM polls WHERE id=?", (poll_id,)).fetchone()
        if not poll or not poll['is_active']:
            flash("❌ This poll is not active.", "danger")
            return redirect(url_for("index"))

        # does the option exist?
        option = conn.execute(
            "SELECT id FROM options WHERE id=? AND poll_id=?",
            (option_id, poll_id)
        ).fetchone()
        if not option:
            flash("❌ Invalid option.", "danger")
            return redirect(url_for("poll", poll_id=poll_id))

        # has this email already voted?
        existing = conn.execute(
            "SELECT id FROM votes WHERE poll_id=? AND email=?",
            (poll_id, email)
        ).fetchone()
        if existing:
            flash("⚠️ A vote has already been cast with this email.", "warning")
            return redirect(url_for("results", poll_id=poll_id))

        # token for confirmation mail
        token = serializer.dumps(
            {'poll_id': poll_id, 'option_id': option_id, 'email': email, 'ip': request.remote_addr},
            salt='email-confirm-v2'
        )
        confirm_url = url_for('confirm_vote', token=token, _external=True)

        html = f"""
        <html><body style="font-family: Arial, sans-serif">
        <h2>🔒 Zama Poll - Confirm Your Vote</h2>
        <p>To complete your vote, click the link below:</p>
        <p><a href="{confirm_url}" style="background:#4F46E5;color:#fff;padding:10px 16px;border-radius:6px;text-decoration:none;">Confirm My Vote</a></p>
        <p style="color:#666">This link is valid for 1 hour.</p>
        </body></html>
        """

        send_mailgun_email(
            to=email,
            subject="Zama Poll | Confirm Your Vote",
            html_content=html
        )

        flash("📧 Check your email and click the verification link.", "success")
        return redirect(url_for('poll', poll_id=poll_id))

    except Exception as e:
        app.logger.error(f"vote/send mail error: {e}")
        flash("❌ Verification email could not be sent.", "danger")
        return redirect(url_for("poll", poll_id=poll_id))
    finally:
        conn.close()

@app.route('/confirm_vote/<token>')
def confirm_vote(token):
    try:
        data = serializer.loads(token, salt='email-confirm-v2', max_age=3600)
        poll_id = data['poll_id']
        option_id = data['option_id']
        email = data['email']
    except SignatureExpired:
        flash("⚠️ The verification link has expired. Please vote again.", "danger")
        return redirect(url_for('index'))
    except BadTimeSignature:
        flash("❌ Invalid verification link.", "danger")
        return redirect(url_for('index'))

    conn = get_db()
    try:
        c = conn.cursor()

        # already confirmed?
        existing = c.execute(
            "SELECT id FROM votes WHERE poll_id=? AND email=?",
            (poll_id, email)
        ).fetchone()
        if existing:
            flash("⚠️ This vote has already been confirmed.", "warning")
            return redirect(url_for('results', poll_id=poll_id))

        c.execute(
            "INSERT INTO votes (poll_id, email, option_id, confirmed, ip_address) VALUES (?, ?, ?, 1, ?)",
            (poll_id, email, option_id, request.remote_addr)
        )
        c.execute("UPDATE options SET votes = votes + 1 WHERE id=?", (option_id,))
        conn.commit()

        flash("✅ Thank you! Your vote has been recorded.", "success")
        return redirect(url_for('results', poll_id=poll_id))

    except sqlite3.IntegrityError:
        flash("⚠️ This vote is already recorded.", "warning")
        return redirect(url_for('results', poll_id=poll_id))
    except Exception as e:
        app.logger.error(f"confirm_vote error: {e}")
        flash("❌ An error occurred while recording the vote.", "danger")
        return redirect(url_for('index'))
    finally:
        conn.close()

@app.route("/results/<poll_id>")
def results(poll_id):
    if not re.match(r'^[a-f0-9]{12}$', poll_id):
        flash("❌ Invalid poll ID.", "danger")
        return redirect(url_for("index"))

    conn = get_db()
    try:
        poll_row = conn.execute("SELECT * FROM polls WHERE id=?", (poll_id,)).fetchone()
        if not poll_row:
            flash("❌ Poll not found.", "danger")
            return redirect(url_for("index"))

        options = conn.execute(
            "SELECT * FROM options WHERE poll_id=? ORDER BY votes DESC, id",
            (poll_id,)
        ).fetchall()

        total_votes = sum(o['votes'] for o in options)
        return render_template("results.html", poll=poll_row, options=options, total_votes=total_votes)
    finally:
        conn.close()

# ================== Test/Debug Routes (temporary) ==================
@app.route("/test_mailgun")
def test_mailgun():
    try:
        # Note: With a sandbox domain, the 'to' address must be VERIFIED under Authorized Recipients in Mailgun.
        html = "<h2>Mailgun Test</h2><p>The Flask app can send emails 🎉</p>"
        r = send_mailgun_email(
            to="zamacreatorprogram@gmail.com",
            subject="📬 Mailgun Test Successful!",
            html_content=html
        )
        return f"<pre>{r.status_code} - {r.text}</pre>", 200
    except Exception as e:
        import traceback
        return f"<pre>{traceback.format_exc()}</pre>", 500

@app.route("/healthz")
def healthz():
    return "ok", 200

@app.route("/debug_env")
def debug_env():
    keys = ["MAILGUN_DOMAIN", "MAILGUN_API_KEY", "MAILGUN_SENDER"]
    status = {k: ("SET" if os.getenv(k) else "MISSING") for k in keys}
    html = "<br>".join([f"{k}: {v}" for k, v in status.items()])
    return html, 200

# ================== Error Pages ==================
@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404

@app.errorhandler(500)
def internal_error(e):
    app.logger.error(f"Internal error: {e}")
    return render_template("500.html"), 500

# ================== Startup ==================
@app.before_request
def before_first_request_handler():
    if not hasattr(app, 'db_initialized'):
        init_db()
        app.db_initialized = True

if __name__ == "__main__":
    init_db()
    print("\n" + "="*50)
    print("🚀 Zama Poll (Mailgun) starting...")
    print("="*50)
    print("📍 URL: http://127.0.0.1:5000")
    print("⚠️ Debug: ON")
    print("="*50 + "\n")
    app.run(debug=True, port=5000, host='127.0.0.1')
