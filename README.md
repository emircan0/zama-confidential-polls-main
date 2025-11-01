<p align="center"> <img src="https://raw.githubusercontent.com/eisenheim37/zama-confidential-polls/main/static/zama_logo.jpg" alt="Zama Logo" width="120" /> </p> <h1 align="center">🗳️ Zama Confidential Polls</h1> <p align="center"> <b>A secure, email-verified polling platform built with Flask.</b> </p> <p align="center"> <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.10+-blue.svg?logo=python&logoColor=white" /></a> <a href="https://flask.palletsprojects.com/"><img src="https://img.shields.io/badge/Flask-Framework-black.svg?logo=flask&logoColor=white" /></a> <a href="https://choosealicense.com/licenses/mit/"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" /></a> <a href="https://github.com/eisenheim37/zama-confidential-polls/stargazers"><img src="https://img.shields.io/github/stars/eisenheim37/zama-confidential-polls?style=social" /></a> </p>
🔒 Overview

Zama Confidential Polls is a lightweight, privacy-first survey system that uses email verification to ensure vote integrity.
Users can create polls, share secure links, and view transparent results — every vote is verified via email to guarantee “one person, one vote”.

🧑‍💻 About this version:
This is an early release of Zama Confidential Polls, where votes are confirmed via email.
In the upcoming stage, all users will be able to verify their email once and then directly vote or launch new polls.

🚀 Key Features
🔐 Email-Verified Voting

Each vote must be confirmed via a unique verification link sent to the voter’s email (valid for 1 hour).

🛡️ Rate Limiting

Prevents bot or spam attempts with IP-based rate limiting on critical endpoints like create_poll and vote.

🧹 XSS Protection

Sanitizes all user input (questions, options) with bleach to prevent Cross-Site Scripting attacks.

⚙️ Secure Configuration

Sensitive variables like SECRET_KEY and email credentials are loaded securely from a .env file.

📊 Real-Time Results

Displays live, percentage-based results for all verified votes.

🧩 SQLite Integration

Uses a simple single-file SQLite database for easy setup and management.

🎨 Responsive UI

Modern, mobile-friendly interface powered by Bootstrap 5 and custom CSS.

🧱 Project Structure
zama-confidential-polls/
│
├── app.py               # Main Flask app (routes, logic, DB initialization)
├── database.db          # SQLite database (auto-created)
├── .env.example         # Example environment variables
├── requirements.txt     # Python dependencies
│
├── static/              # CSS, images, logos
│   ├── style.css
│   └── zama_logo.jpg
│
└── templates/           # HTML templates
    ├── base.html
    ├── index.html        # Homepage (create poll)
    ├── poll.html         # Voting page
    ├── results.html      # Results page
    ├── about.html
    ├── email_confirmation.html  # Email verification template
    ├── 404.html
    └── 500.html

⚙️ Setup Instructions
1️⃣ Clone the Project
git clone https://github.com/eisenheim37/zama-confidential-polls.git
cd zama-confidential-polls

2️⃣ Create and Activate a Virtual Environment
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate

3️⃣ Install Dependencies
pip install -r requirements.txt

4️⃣ Configure Environment Variables

Create a .env file by copying the example:

# Windows
copy .env.example .env

# macOS/Linux
cp .env.example .env


Then edit .env and fill in the values (for email sending):

# .env file example

SECRET_KEY='YOUR_SUPER_SECRET_KEY'

MAIL_SERVER='smtp.yandex.com'
MAIL_PORT=465
MAIL_USE_SSL=True
MAIL_USE_TLS=False
MAIL_USERNAME='youremail@yandex.com'
MAIL_PASSWORD='YOUR_PASSWORD_OR_APP_PASSWORD'


💡 If you use Gmail, you’ll need to generate an App Password.

5️⃣ Run the Application
python app.py


When first launched, the app automatically creates the database.db file.

Visit http://127.0.0.1:5000
 to get started.

📈 Roadmap

 User Accounts (Sign up / Login) for poll management

 API-based voting system

 Edit & delete polls

 🔐 FHE (Fully Homomorphic Encryption) — encrypted votes even on the server

 HTTPS deployment on a custom domain

🤝 Contributing

Pull requests and ideas are welcome!
Please open an issue first to discuss major changes.

🛡 License

This project is licensed under the MIT License.
See the LICENSE
 file for details.

<p align="center"> <i>© 2025 Cryptoeisenheim — Building the Confidential Future with Zama.</i><br> <img src="https://img.shields.io/badge/Confidential_Computing-Zama-yellow?style=for-the-badge&logo=lock&logoColor=black" /> </p>