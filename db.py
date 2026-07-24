import sqlite3
import os
from datetime import datetime


DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "journal.db"
)


def get_connection():
    try:
        conn = sqlite3.connect(
            DB_PATH,
            timeout=10
        )

        conn.execute(
            "PRAGMA journal_mode=WAL"
        )

        conn.row_factory = sqlite3.Row

        return conn

    except sqlite3.Error as e:
        raise RuntimeError(
            f"Could not connect to the database: {e}"
        )


def init_db():
    """
    Creates the users, entries, and messages tables if they
    do not already exist.

    For an existing database:
    - preserves current users
    - preserves current journal entries
    - preserves current messages
    - safely adds the email column if missing
    - creates a unique email index

    If journal.db is corrupted:
    - backs up the corrupted database
    - creates a fresh empty database
    """

    conn = None

    try:
        conn = get_connection()

        # =====================================================
        # USERS TABLE
        # =====================================================

        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        # -----------------------------------------------------
        # Existing database migration
        # -----------------------------------------------------

        user_columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(users)"
            ).fetchall()
        }

        if "email" not in user_columns:
            conn.execute(
                "ALTER TABLE users ADD COLUMN email TEXT"
            )

        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email
            ON users(email)
            WHERE email IS NOT NULL
        """)

        # =====================================================
        # ENTRIES TABLE
        # =====================================================

        conn.execute("""
            CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                reflection TEXT,
                summary TEXT,
                title TEXT,
                title_locked INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)

        # Existing database migration for entries
        entry_columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(entries)"
            ).fetchall()
        }

        if "title" not in entry_columns:
            conn.execute(
                "ALTER TABLE entries ADD COLUMN title TEXT"
            )

        if "title_locked" not in entry_columns:
            conn.execute(
                "ALTER TABLE entries ADD COLUMN title_locked INTEGER DEFAULT 0"
            )

        # =====================================================
        # MESSAGES TABLE
        # =====================================================

        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (entry_id) REFERENCES entries (id)
            )
        """)

        conn.commit()
        conn.close()

    except sqlite3.DatabaseError:

        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass

        # -----------------------------------------------------
        # Back up corrupted database
        # -----------------------------------------------------

        if os.path.exists(DB_PATH):

            backup_path = (
                DB_PATH
                + ".corrupted."
                + datetime.now().strftime("%Y%m%d%H%M%S")
            )

            os.rename(
                DB_PATH,
                backup_path
            )

            print(
                "WARNING: journal.db was corrupted and has "
                f"been backed up to {backup_path}. "
                "A new, empty journal.db has been created."
            )

        # -----------------------------------------------------
        # Create fresh database
        # -----------------------------------------------------

        conn = get_connection()

        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email
            ON users(email)
            WHERE email IS NOT NULL
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                reflection TEXT,
                summary TEXT,
                title TEXT,
                title_locked INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (entry_id) REFERENCES entries (id)
            )
        """)

        conn.commit()
        conn.close()


def save_entry(user_id, content, reflection):
    """
    Saves a new journal entry for a specific user,
    along with its AI reflection.

    Returns the new entry id.
    """

    conn = get_connection()

    timestamp = datetime.now().isoformat()

    cursor = conn.execute(
        """
        INSERT INTO entries (
            user_id,
            content,
            reflection,
            created_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            user_id,
            content,
            reflection,
            timestamp
        )
    )

    conn.commit()

    new_id = cursor.lastrowid

    conn.close()

    return new_id


def get_all_entries(user_id):
    """
    Returns all entries belonging to the given user,
    newest first.
    """

    conn = get_connection()

    rows = conn.execute(
        """
        SELECT
            id,
            title,
            title_locked,
            content,
            created_at
        FROM entries
        WHERE user_id = ?
        ORDER BY created_at DESC
        """,
        (user_id,)
    ).fetchall()

    conn.close()

    return rows


def get_recent_entries(user_id, limit=7):
    """
    Returns the most recent journal entries belonging
    only to the given user.

    Used for the sidebar RECENTS section.

    Behavior:
    - newest entries first
    - only entries owned by the logged-in user
    - limited to a small number for sidebar usability
    - returns an empty list if the user has no entries

    The empty-list behavior allows the template to hide
    the entire RECENTS section when there is no history.
    """

    conn = get_connection()

    rows = conn.execute(
        """
        SELECT
            id,
            title,
            title_locked,
            content,
            created_at
        FROM entries
        WHERE user_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT ?
        """,
        (
            user_id,
            limit
        )
    ).fetchall()

    conn.close()

    return rows


def get_entry_by_id(user_id, entry_id):
    """
    Returns a single entry only if it belongs to the
    given user.

    Returns None if:
    - the entry does not exist
    - the entry belongs to another user
    """

    conn = get_connection()

    row = conn.execute(
        """
        SELECT
            id,
            content,
            reflection,
            summary,
            title,
            title_locked,
            created_at
        FROM entries
        WHERE id = ?
        AND user_id = ?
        """,
        (
            entry_id,
            user_id
        )
    ).fetchone()

    conn.close()

    return row


def get_entries_by_date(user_id, date_str):
    """
    Returns entries belonging to the given user
    for a specific date.

    Expected date format:
    YYYY-MM-DD
    """

    conn = get_connection()

    rows = conn.execute(
        """
        SELECT
            id,
            title,
            title_locked,
            content,
            created_at
        FROM entries
        WHERE user_id = ?
        AND date(created_at) = ?
        ORDER BY created_at DESC
        """,
        (
            user_id,
            date_str
        )
    ).fetchall()

    conn.close()

    return rows


def create_user(username, email, password_hash):
    """
    Creates a new user with:
    - username
    - email
    - already-hashed password

    Returns the new user id.

    The database enforces:
    - unique username
    - unique non-null email
    """

    conn = get_connection()

    cursor = conn.execute(
        """
        INSERT INTO users (
            username,
            email,
            password_hash,
            created_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            username,
            email,
            password_hash,
            datetime.now().isoformat()
        )
    )

    conn.commit()

    new_id = cursor.lastrowid

    conn.close()

    return new_id


def get_user_by_username(username):
    """
    Returns a user by username.

    Returns None if no matching user exists.
    """

    conn = get_connection()

    row = conn.execute(
        """
        SELECT
            id,
            username,
            email,
            password_hash,
            created_at
        FROM users
        WHERE username = ?
        """,
        (username,)
    ).fetchone()

    conn.close()

    return row


def get_user_by_email(email):
    """
    Returns a user by email.

    Email matching is case-insensitive.

    Used by the forgot-password flow.
    Returns None if no matching user exists.
    """

    conn = get_connection()

    row = conn.execute(
        """
        SELECT
            id,
            username,
            email,
            password_hash,
            created_at
        FROM users
        WHERE LOWER(email) = LOWER(?)
        """,
        (email,)
    ).fetchone()

    conn.close()

    return row


def save_message(entry_id, role, content):
    """
    Saves one message as part of the ongoing
    chat attached to a specific journal entry.

    role is expected to be:
    - user
    - ai
    """

    conn = get_connection()

    conn.execute(
        """
        INSERT INTO messages (
            entry_id,
            role,
            content,
            created_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            entry_id,
            role,
            content,
            datetime.now().isoformat()
        )
    )

    conn.commit()

    conn.close()


def get_messages_for_entry(entry_id):
    """
    Returns every message for a given journal entry,
    oldest first.
    """

    conn = get_connection()

    rows = conn.execute(
        """
        SELECT
            role,
            content,
            created_at
        FROM messages
        WHERE entry_id = ?
        ORDER BY id ASC
        """,
        (entry_id,)
    ).fetchall()

    conn.close()

    return rows


def save_summary(entry_id, summary):
    """
    Saves the final conversation summary
    onto the journal entry.
    """

    conn = get_connection()

    conn.execute(
        """
        UPDATE entries
        SET summary = ?
        WHERE id = ?
        """,
        (
            summary,
            entry_id
        )
    )

    conn.commit()

    conn.close()


def get_entry_owner(entry_id):
    """
    Returns the user_id that owns an entry.

    Returns None if the entry does not exist.
    """

    conn = get_connection()

    row = conn.execute(
        """
        SELECT user_id
        FROM entries
        WHERE id = ?
        """,
        (entry_id,)
    ).fetchone()

    conn.close()

    return row["user_id"] if row else None


def update_user_password(user_id, password_hash):
    """
    Updates a user's password hash.

    The caller must validate the new password
    and hash it before calling this function.
    """

    conn = get_connection()

    conn.execute(
        """
        UPDATE users
        SET password_hash = ?
        WHERE id = ?
        """,
        (
            password_hash,
            user_id
        )
    )

    conn.commit()
    conn.close()

def update_entry_title(entry_id, title):
    conn = get_connection()
    conn.execute(
        '''
        UPDATE entries
        SET title = ?, title_locked = 1
        WHERE id = ?
        ''',
        (title, entry_id),
    )
    conn.commit()
    conn.close()


def get_entry_title(entry_id):
    conn = get_connection()
    row = conn.execute(
        '''
        SELECT title, title_locked
        FROM entries
        WHERE id = ?
        ''',
        (entry_id,),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return {
        "title": row["title"],
        "locked": bool(row["title_locked"]),
    }
