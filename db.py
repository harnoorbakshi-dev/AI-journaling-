import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "journal.db")


def get_connection():
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        raise RuntimeError(f"Could not connect to the database: {e}")


def init_db():
    """
    Creates the users and entries tables if they don't already exist.
    If journal.db is missing, SQLite creates it fresh automatically.
    If journal.db exists but is corrupted (not a valid SQLite file),
    we back up the bad file and create a brand new empty database
    instead of crashing or refusing to start.
    """
    try:
        conn = get_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                reflection TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        conn.commit()
        conn.close()

    except sqlite3.DatabaseError as e:
        try:
            conn.close()
        except Exception:
            pass

        if os.path.exists(DB_PATH):
            backup_path = DB_PATH + ".corrupted." + datetime.now().strftime("%Y%m%d%H%M%S")
            os.rename(DB_PATH, backup_path)
            print(f"WARNING: journal.db was corrupted and has been backed up to "
                  f"{backup_path}. A new, empty journal.db has been created.")

        conn = get_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                reflection TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        conn.commit()
        conn.close()

def save_entry(user_id, content, reflection):
    """
    Saves a new journal entry for a specific user, along with its
    AI reflection. Returns the new entry's id.
    """
    conn = get_connection()
    timestamp = datetime.now().isoformat()
    cursor = conn.execute(
        "INSERT INTO entries (user_id, content, reflection, created_at) VALUES (?, ?, ?, ?)",
        (user_id, content, reflection, timestamp)
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id


def get_all_entries(user_id):
    """
    Returns a list of entries belonging to the given user, most recent
    first. Used for the 'browse past entries' list view.
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, content, created_at FROM entries WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,)
    ).fetchall()
    conn.close()
    return rows


def get_entry_by_id(user_id, entry_id):
    """
    Returns a single entry (with its reflection) by id, but only if it
    belongs to the given user. Returns None if the entry doesn't exist
    OR belongs to someone else — both cases are treated identically so
    we don't leak whether an entry id exists for another account.
    """
    conn = get_connection()
    row = conn.execute(
        "SELECT id, content, reflection, created_at FROM entries WHERE id = ? AND user_id = ?",
        (entry_id, user_id)
    ).fetchone()
    conn.close()
    return row


def get_entries_by_date(user_id, date_str):
    """
    Returns entries belonging to the given user, created on the given
    date (format: YYYY-MM-DD), most recent first.
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, content, created_at FROM entries "
        "WHERE user_id = ? AND date(created_at) = ? ORDER BY created_at DESC",
        (user_id, date_str)
    ).fetchall()
    conn.close()
    return rows

def create_user(username, password_hash):
    """
    Creates a new user with the given username and (already-hashed)
    password. Returns the new user's id.
    Raises sqlite3.IntegrityError if the username is already taken
    (enforced by the UNIQUE constraint on the username column).
    """
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
        (username, password_hash, datetime.now().isoformat())
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id


def get_user_by_username(username):
    """
    Returns a user row (id, username, password_hash, created_at) by
    username, or None if no such user exists. Used during both login
    (to check the password) and signup (to check if the name is taken).
    """
    conn = get_connection()
    row = conn.execute(
        "SELECT id, username, password_hash, created_at FROM users WHERE username = ?",
        (username,)
    ).fetchone()
    conn.close()
    return row