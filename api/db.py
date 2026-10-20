import hashlib
import sqlite3
import time
from contextlib import contextmanager
from uuid import uuid4
from fastapi import HTTPException
from insurewise.storage import PolicyStore

SCHEMA = '''
CREATE TABLE IF NOT EXISTS web_users(id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, password TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS web_sessions(token TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES web_users(id) ON DELETE CASCADE, csrf TEXT NOT NULL, expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS web_resets(token TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES web_users(id) ON DELETE CASCADE, expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS web_rates(key TEXT PRIMARY KEY, attempts INTEGER NOT NULL, expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS web_policies(id TEXT PRIMARY KEY REFERENCES policies(policy_id) ON DELETE CASCADE, user_id TEXT NOT NULL REFERENCES web_users(id), hash TEXT NOT NULL, original BLOB NOT NULL, archived INTEGER NOT NULL DEFAULT 0, last_opened TEXT, UNIQUE(user_id,hash));
CREATE TABLE IF NOT EXISTS web_conversations(id TEXT PRIMARY KEY, policy_id TEXT NOT NULL REFERENCES web_policies(id) ON DELETE CASCADE, user_id TEXT NOT NULL REFERENCES web_users(id), title TEXT NOT NULL, messages TEXT NOT NULL DEFAULT '[]');
CREATE TABLE IF NOT EXISTS web_claims(id TEXT PRIMARY KEY, policy_id TEXT NOT NULL REFERENCES web_policies(id) ON DELETE CASCADE, user_id TEXT NOT NULL REFERENCES web_users(id), description TEXT NOT NULL, incident_date TEXT NOT NULL, gathered TEXT NOT NULL, updated_at TEXT NOT NULL);
'''
def uid(): return uuid4().hex
def digest(value): return hashlib.sha256(value.encode()).hexdigest()

class Database:
    def __init__(self, directory):
        self.path = directory / 'policyiq.db'
        self.store = PolicyStore(self.path)
        with self.connect() as conn:
            conn.execute('PRAGMA journal_mode=WAL')
            conn.executescript(SCHEMA)
    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        conn.execute('PRAGMA secure_delete=ON')
        try:
            with conn: yield conn
        finally: conn.close()
    def rate(self, key, limit, seconds=900):
        key = digest(key)
        now = time.time()
        with self.connect() as c:
            c.execute('DELETE FROM web_rates WHERE expires < ?', (now,))
            c.execute('INSERT INTO web_rates VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET attempts=attempts+1', (key, now+seconds))
            count = c.execute('SELECT attempts FROM web_rates WHERE key=?', (key,)).fetchone()[0]
        if count > limit:
            raise HTTPException(429, 'Too many attempts. Please wait before trying again.', headers={'Retry-After':str(seconds)})
    def owned(self, policy_id, user_id):
        with self.connect() as c:
            row = c.execute('SELECT p.*, w.archived, w.last_opened FROM policies p JOIN web_policies w ON p.policy_id=w.id WHERE w.id=? AND w.user_id=?', (policy_id,user_id)).fetchone()
        if row is None: raise HTTPException(404, 'Policy not found.')
        return row
