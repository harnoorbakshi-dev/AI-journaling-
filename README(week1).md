# AI Journal Companion

A small web-based journaling app. Each user creates an account, writes
private journal entries, and an AI companion (Google Gemini) responds
with a short, genuinely reflective follow-up — a gentle question or
observation grounded in what was actually written, not generic filler.
Every entry and its reflection are saved permanently and scoped to that
user's account, so each person can browse and re-read only their own
past entries, even after closing and reopening the app.

## Architecture

The app follows a simple layered design: a Flask web layer handles
HTTP routes, sessions, and rendering; a database layer (`db.py`)
handles all SQLite reads/writes (users and entries); and an AI layer
(`reflection.py`) handles the one external call to Gemini. These layers
don't overlap — Flask never touches SQL directly, and the database
layer knows nothing about HTTP or the AI provider.

```
                     ┌─────────────────────┐
                     │   User's Browser    │
                     └──────────┬──────────┘
                                │ HTTP (GET / POST)
                                ▼
                     ┌─────────────────────────────┐
                     │          app.py              │
                     │       (Flask routes)         │
                     │ /signup /login /logout       │
                     │ /  /save  /entry/<id>        │
                     │  (protected by @login_required)│
                     └──────┬───────────────┬───────┘
                            │               │
              ┌─────────────┘               └─────────────┐
              ▼                                            ▼
     ┌──────────────────┐                       ┌────────────────────┐
     │      db.py         │                       │   reflection.py     │
     │ (SQLite layer)      │                       │  (Gemini API layer) │
     └────────┬───────────┘                       └──────────┬──────────┘
              │                                              │
              ▼                                              ▼
       journal.db                                  Google Gemini API
   ┌─────────────────┐                              (gemini-2.5-flash,
   │ users table       │                             one request per
   │  id, username,     │                             new journal entry)
   │  password_hash,    │
   │  created_at        │
   ├─────────────────┤
   │ entries table      │
   │  id, user_id,      │
   │  content,          │
   │  reflection,       │
   │  created_at        │
   └─────────────────┘
```

**Request flow for a new entry:**
1. User must be logged in (enforced by a `login_required` decorator on
   every journal route) → `POST /save`
2. `app.py` validates the input isn't empty
3. `reflection.py` sends the entry text to `gemini-2.5-flash` and gets
   back a 2–4 sentence reflection (or a graceful fallback message if
   the API call fails for any reason)
4. `db.py` saves the entry + reflection + the logged-in user's id
   together as one row in `journal.db`
5. User is redirected to view the saved entry and its reflection

**Request flow for browsing:**
1. `GET /` → `db.py` fetches all entries belonging to the logged-in
   user only (or that user's entries filtered by a chosen date),
   newest first → rendered as a list
2. `GET /entry/<id>` → `db.py` fetches that one row, but only if it
   belongs to the requesting user → rendered as a single page

Because the reflection is generated once and stored in the database
(not regenerated on every view), reopening an old entry always shows
the exact same reflection it originally received. Because every query
is scoped by `user_id`, one account can never read, list, or guess its
way into another account's entries.

## Features

- Each user creates an account (username + password) and logs in
  before journaling; passwords are hashed with werkzeug's scrypt-based
  hashing and are never stored or handled in plain text
- Every entry is private to the account that created it — no user can
  view, list, or access another user's entries, even by guessing a
  URL
- Write and save journal entries through a simple web form
- Each entry receives a short (2–4 sentence), context-aware AI
  reflection from Gemini — a follow-up question or observation
  grounded in what was actually written, not generic acknowledgment
- The reflection is generated once and permanently stored with the
  entry, so re-opening it later always shows the same response
- Entries persist across runs in a local SQLite database
  (`journal.db`), with WAL mode enabled for reliable concurrent access
- Browse all of your past entries in a list, newest first
- Filter your past entries by a specific date using a date picker
- Open any past entry to re-read the full text and its original
  reflection
- Human-readable timestamps (e.g. "June 19, 2026 at 02:23 PM") instead
  of raw database format
- Gemini API key is read only from the `GEMINI_API_KEY` environment
  variable — never hardcoded, never committed (excluded via
  `.gitignore`)

## Requirements coverage

| Requirement | How it's handled |
|---|---|
| Write & save entries, persisted across runs (SQLite) | `db.py` + `journal.db`, tested independently before integration |
| AI reflection, 2–4 sentences, non-generic | `reflection.py`, system prompt explicitly bans filler phrases like "thanks for sharing"; Gemini's internal "thinking" step is disabled so the full token budget goes to the visible reply |
| Reflection stored with entry, same one shown on reopen | Reflection generated once at save time, stored in the same row, never regenerated |
| Browse past entries, open one to re-read | `GET /` (list) and `GET /entry/<id>` (single view) routes |
| API key from environment variable, never hardcoded/committed | `python-dotenv` loads it from `.env`; `.env` is in `.gitignore` |
| Empty input handled | Checked in `app.py` before any DB write or API call; user gets a flash message |
| AI API errors & timeouts handled | All Gemini exceptions (`ClientError`, `ServerError`, and a generic catch-all) caught in `reflection.py`; entry still saves with a fallback message instead of crashing |
| Missing/corrupt `journal.db` handled | `init_db()` recreates a missing file automatically; a corrupt file is quarantined (renamed with a timestamp) and a fresh database is created automatically |
| Multi-user accounts | Users sign up / log in via Flask sessions (`werkzeug.security` password hashing); a `login_required` decorator protects every journal route; every entry query is scoped to `session["user_id"]`, so one user can never read, list, or access another's entries |

## Requirements

- Python 3.9+
- A free Google Gemini API key (no credit card required) — see
  "Setting your API key" below

## Installation

1. Clone or download this repository, then move into the project
   folder:
   ```
   cd AI_Journal_companion
   ```

2. Create and activate a virtual environment:
   ```
   python -m venv venv
   venv\Scripts\activate        # Windows
   source venv/bin/activate     # macOS/Linux
   ```

3. Install dependencies:
   ```
   python -m pip install -r requirements.txt
   ```

## Setting your API key

This app reads your Gemini API key from the `GEMINI_API_KEY`
environment variable — it is never hardcoded in the source code.

1. Get a free key at https://aistudio.google.com/apikey (sign in with
   a Google account; no credit card needed).
2. Create a file named `.env` in the project root.
3. Add this line, replacing the placeholder with your real key:
   ```
   GEMINI_API_KEY=your-real-key-here
   ```

The `.env` file is excluded from version control via `.gitignore` and
should never be committed. If a key is ever accidentally exposed
(e.g. pasted somewhere public), revoke it immediately at the link
above and generate a new one.

## Running the app

```
python app.py
```

Then open http://127.0.0.1:5000 in your browser. You'll be prompted to
sign up or log in before you can start journaling.

## Example interaction

**You sign up, log in, and write:**
> Today I felt anxious about my exam tomorrow. I studied a lot but I still feel like it won't be enough.

**The companion reflects:**
> It sounds like a lot of effort has gone into preparing, and yet the worry still lingers about whether it will all be enough. What's the specific concern that comes up for you when you think about it not being enough?

This reflection is saved with the entry, so reopening it later — from
the same account — shows the exact same response.

## Error handling

- **Empty entry:** rejected before any database write or API call; the
  user sees a flash message and nothing crashes.
- **AI API errors/timeouts:** every failure mode (timeout, client
  error, server error, unexpected error) is caught in
  `reflection.py`. The entry is still saved successfully, with a calm
  fallback message in place of the reflection — a journal entry is
  never lost just because the AI call failed.
- **Missing database:** if `journal.db` doesn't exist, it's created
  automatically on startup, with both the `users` and `entries`
  tables.
- **Corrupt database:** if `journal.db` exists but isn't valid SQLite,
  the app backs up the bad file (renamed with a timestamp, nothing is
  deleted) and creates a fresh, working database automatically.
- **Unauthorized access:** visiting a journal page while logged out
  redirects to the login page. Trying to view another user's entry by
  guessing its URL returns "that entry doesn't exist," without
  revealing whether the entry actually belongs to someone else.

## A note on the AI model

This app does not train, fine-tune, or modify any model. It calls
Google's already-trained `gemini-2.5-flash` model over their API for
inference only — sending the journal entry as a prompt and receiving a
generated reflection back. Typical response time for a single entry is
about 1–3 seconds, depending on API load at the time.

## Project structure

```
AI_Journal_companion/
├── app.py               # Flask routes, sessions, login_required decorator
├── db.py                 # SQLite layer (users + entries)
├── reflection.py          # Gemini API integration
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── entry.html
│   ├── login.html
│   └── signup.html
├── requirements.txt
├── .env                  # not committed — holds GEMINI_API_KEY
└── .gitignore
```

## Possible future features

- **Full-text search** across entry content, not just filtering by date
- **Editing or deleting** past entries
- **Mood/sentiment tagging**, with a simple trend chart over time
- **Tags or categories** for entries (e.g. work, health, relationships)
- **Multi-turn reflections** — letting the user reply to the AI's
  follow-up question instead of it being a one-shot response
- **Longitudinal awareness** — letting the reflection reference
  patterns across the same user's previous entries (e.g. "you've
  mentioned exam stress a few times this month"), with the user's
  consent
- **Export entries** to PDF or Markdown for personal backup
- **Password reset / "forgot password" flow**
- **Daily reminder notifications** to encourage consistent journaling
- **Voice-to-text input** for entries
- **Streaming the reflection** token-by-token instead of waiting for
  the full response
- **Switchable AI providers** (e.g. supporting OpenAI or a local
  model) behind the same interface, in case of cost or availability
  changes
