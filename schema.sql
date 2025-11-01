DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS polls;
DROP TABLE IF EXISTS options;
DROP TABLE IF EXISTS votes;

-- Bu tablo şimdilik kullanılmıyor ama gelecek geliştirmeler için kalabilir.
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE polls (
    id TEXT PRIMARY KEY,
    question TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE options (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    poll_id TEXT NOT NULL,
    option_text TEXT NOT NULL,
    votes INTEGER DEFAULT 0,
    FOREIGN KEY (poll_id) REFERENCES polls (id)
);

-- OYLAMA SİSTEMİ İÇİN GÜNCELLENMİŞ TABLO
CREATE TABLE votes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    poll_id TEXT NOT NULL,
    email TEXT NOT NULL,              -- E-posta adresi voter_token'ın yerini aldı
    option_id INTEGER NOT NULL,       -- Hangi seçeneğe oy verdiği bilgisi eklendi
    confirmed BOOLEAN DEFAULT FALSE,  -- Oy'un e-posta ile doğrulanıp doğrulanmadığı
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (poll_id, email),          -- Bir e-posta, bir ankete sadece bir kez oy verebilir
    FOREIGN KEY (poll_id) REFERENCES polls (id)
);