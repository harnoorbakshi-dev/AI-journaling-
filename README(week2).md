# AI Journal Companion

A small web-based journaling app. Each user creates an account, writes
private journal entries, and has an ongoing reflective conversation with
an AI companion (Google Gemini) about each one — not just a single
canned reply, but a real back-and-forth. When the user is done talking,
they can end the conversation and get a short summary, which is saved
permanently alongside the original entry. Every entry, its full chat
history, and its summary are scoped to that user's account, so each
person can browse and re-read only their own past entries.

## Architecture

The app follows a simple layered design: a Flask web layer handles
HTTP routes, sessions, and rendering; a database layer (`db.py`)
handles all SQLite reads/writes (users, entries, and chat messages);
and an AI layer (`reflection.py`) handles every call to Gemini —
the initial reflection, ongoing chat replies, and end-of-conversation
summaries. These layers don't overlap — Flask never touches SQL
directly, and the database layer knows nothing about HTTP or the AI
provider.

```
                     ┌─────────────────────┐
                     │   User's Browser    │
                     └──────────┬──────────┘
                                │ HTTP (GET / POST)
                                ▼
                     ┌─────────────────────────────────┐
                     │             app.py                │
                     │         (Flask routes)            │
                     │ /signup /login /logout            │
                     │ /  /save                           │
                     │ /entry/<id>                        │
                     │ /entry/<id>/chat                   │
                     │ /entry/<id>/end_chat               │
                     │   (all protected by @login_required) │
                     └──────┬───────────────────┬─────────┘
                            │                   │
              ┌─────────────┘                   └─────────────┐
              ▼                                                ▼
     ┌──────────────────┐                            ┌────────────────────┐
     │      db.py         │                            │   reflection.py     │
     │ (SQLite layer)      │                            │  (Gemini API layer) │
     └────────┬───────────┘                            └──────────┬──────────┘
              │                                                   │
              ▼                                                   ▼
       journal.db                                       Google Gemini API
   ┌──────────────────┐                                  (gemini-2.5-flash,
   │ users               │                                 thinking disabled
   │  id, username,       │                                for fast, direct
   │  password_hash,      │                                replies)
   │  created_at          │
   ├──────────────────┤
   │ entries             │
   │  id, user_id,        │
   │  content,            │
   │  reflection,         │
   │  summary,            │
   │  created_at          │
   ├──────────────────┤
   │ messages            │
   │  id, entry_id,       │
   │  role, content,      │
   │  created_at          │
   └──────────────────┘
```

**Request flow for a new entry:**
1. User must be logged in (enforced by a `login_required` decorator on
   every journal route) → `POST /save`
2. `app.py` validates the input isn't empty
3. `reflection.py` sends the entry text to Gemini and gets back an
   initial 2–4 sentence reflection (or a graceful fallback message if
   the call fails for any reason)
4. `db.py` saves the entry + reflection + the logged-in user's id as
   one row in the `entries` table
5. User is redirected to the entry page, which now also acts as the
   start of a live conversation

**Request flow for the ongoing chat:**
1. `GET /entry/<id>` → fetches the entry (content, initial reflection,
   summary if ended) and every message in `messages` tied to that
   entry, then renders them as a conversation, oldest first
2. `POST /entry/<id>/chat` → saves the user's new message, rebuilds
   the full conversation history (initial reflection + every message
   so far), sends it to Gemini for a context-aware reply, and saves
   that reply — so the AI "remembers" the whole conversation each turn
3. `POST /entry/<id>/end_chat` → rebuilds the full history one more
   time, asks Gemini to produce a short 1–2 sentence summary of the
   whole exchange, and saves it permanently onto the entry's `summary`
   column. Once a summary exists, the chat becomes read-only — both in
   the UI (the chat form is hidden) and on the server (the `/chat` and
   `/end_chat` routes both reject further action on an already-ended
   entry)

Because the conversation and its summary are both stored permanently,
reopening an old entry always shows the exact same conversation and
the exact same summary it ended with. Because every query is scoped by
`user_id` (and every chat action re-checks entry ownership before
acting), one account can never read, post into, or end another
account's conversation.

## Features

- Each user creates an account (username + password) and logs in
  before journaling; passwords are hashed with werkzeug's scrypt-based
  hashing and are never stored or handled in plain text
- Every entry — and its entire conversation — is private to the
  account that created it; no user can view, post into, or end another
  user's chat, even by guessing a URL
- Write and save journal entries through a simple web form
- Each entry opens with a short, context-aware AI reflection — a
  follow-up question or observation grounded in what was actually
  written, not generic acknowledgment
- The entry page is a live, ongoing conversation: the user can keep
  replying, and the AI keeps responding with full awareness of
  everything said so far in that conversation, not just the original
  entry
- The user can end the conversation at any point, generating a short
  1–2 sentence summary that's saved permanently alongside the entry
- Once ended, a conversation becomes read-only (enforced both in the
  UI and on the server) — the full transcript and its summary remain
  exactly as they were every time the entry is reopened
- Entries persist across runs in a local SQLite database
  (`journal.db`), with WAL mode enabled for reliable concurrent access
- Browse all of your past entries in a list, newest first
- Filter your past entries by a specific date using a date picker
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
| Ongoing, context-aware conversation per entry | Every chat turn rebuilds the full message history and sends it to Gemini as multi-turn `Content`, so each reply accounts for everything said so far, not just the latest message |
| Conversation summary on ending, saved with the entry | `generate_summary()` produces a short summary from the full transcript; `save_summary()` stores it on the entry; the chat becomes read-only once a summary exists |
| Reflection/conversation stored with entry, same one shown on reopen | All messages and the summary are persisted in `messages`/`entries`; nothing is regenerated on reopen |
| Browse past entries, open one to re-read | `GET /` (list) and `GET /entry/<id>` (single conversation view) routes |
| API key from environment variable, never hardcoded/committed | `python-dotenv` loads it from `.env`; `.env` is in `.gitignore` |
| Empty input handled | Checked before any DB write or API call, both for new entries and for new chat messages; user gets a flash message |
| AI API errors & timeouts handled | All Gemini exceptions (`ClientError`, `ServerError`, and a generic catch-all) are caught in every `reflection.py` function (initial reflection, chat replies, and summaries); the entry/message/summary still saves with a fallback message instead of crashing |
| Missing/corrupt `journal.db` handled | `init_db()` recreates a missing file automatically; a corrupt file is quarantined (renamed with a timestamp) and a fresh database, with all three tables, is created automatically |
| Multi-user accounts | Users sign up / log in via Flask sessions (`werkzeug.security` password hashing); a `login_required` decorator protects every journal route; every entry/message query is scoped to `session["user_id"]`, and every chat action re-verifies entry ownership before acting |

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
> I had a rough day at work. My manager criticized my work in front of everyone.

**The companion opens the conversation:**
> That sounds incredibly difficult to experience, especially the public nature of the criticism. How did it feel in the moments after your manager spoke?

**You reply:**
> I just stayed quiet and got through the rest of the day.

**The companion continues, building on what you said:**
> It makes a lot of sense that you'd want to just get through the day after something like that. Was there anything small that helped you cope or just keep going in those moments?

**You end the conversation, and a summary is saved:**
> Summary: It sounds like today was tough, and your manager's public criticism left you feeling embarrassed and quiet, making it hard to just get through the day.

Reopening this entry later shows the exact same conversation, in the
exact same order, with the same summary at the top — nothing is
regenerated.

## Error handling

- **Empty entry / empty chat message:** rejected before any database
  write or API call; the user sees a flash message and nothing
  crashes.
- **AI API errors/timeouts:** every failure mode (timeout, client
  error, server error, unexpected error) is caught separately in each
  of `generate_reflection()`, `generate_chat_reply()`, and
  `generate_summary()`. The relevant message or summary is still
  saved successfully, with a calm fallback message in place of the AI
  text — nothing is ever lost just because one AI call failed.
- **Missing database:** if `journal.db` doesn't exist, it's created
  automatically on startup, with the `users`, `entries`, and
  `messages` tables.
- **Corrupt database:** if `journal.db` exists but isn't valid SQLite,
  the app backs up the bad file (renamed with a timestamp, nothing is
  deleted) and creates a fresh, working database automatically.
- **Unauthorized access:** visiting a journal page while logged out
  redirects to the login page. Trying to view, chat into, or end
  another user's entry by guessing its URL is rejected with "that
  entry doesn't exist," without revealing whether the entry actually
  belongs to someone else.
- **Acting on an ended conversation:** both `/entry/<id>/chat` and
  `/entry/<id>/end_chat` reject further action once a summary already
  exists, enforced on the server — not just by hiding the form in the
  UI — so a conversation can't be reopened or summarized twice.

## A note on the AI model

This app does not train, fine-tune, or modify any model. It calls
Google's already-trained `gemini-2.5-flash` model over their API for
inference only — sending the journal entry and conversation history as
a prompt and receiving a generated reply or summary back. Typical
response time for a single turn is about 1–3 seconds, depending on API
load at the time.

## Project structure

```
AI_Journal_companion/
├── app.py               # Flask routes, sessions, login_required decorator,
│                          # chat + end_chat routes
├── db.py                 # SQLite layer (users, entries, messages)
├── reflection.py          # Gemini integration: initial reflection,
│                          # multi-turn chat replies, summaries
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── entry.html        # entry + live conversation + summary view
│   ├── login.html
│   └── signup.html
├── requirements.txt
├── .env                  # not committed — holds GEMINI_API_KEY
└── .gitignore
```

## Possible future features

- **Full-text search** across entry content and conversation history
- **Editing or deleting** past entries
- **Mood/sentiment tagging**, with a simple trend chart over time
- **Tags or categories** for entries (e.g. work, health, relationships)
- **Reopening an ended conversation** to continue it further, instead
  of it being permanently read-only
- **Longitudinal awareness** — letting the AI reference patterns
  across the same user's previous entries and conversations (e.g.
  "you've mentioned exam stress a few times this month"), with the
  user's consent
- **Export entries and conversations** to PDF or Markdown for personal
  backup
- **Password reset / "forgot password" flow**
- **Daily reminder notifications** to encourage consistent journaling
- **Voice-to-text input** for entries and chat replies
- **Streaming AI replies** token-by-token instead of waiting for the
  full response
- **Switchable AI providers** (e.g. supporting OpenAI or a local
  model) behind the same interface, in case of cost or availability
  changes
