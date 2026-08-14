# Journelle — AI Journaling App
### Week 7: Final Polish, Threading Fix & Project Wrap-Up

Journelle is a Flask web app for AI-guided journaling. You write an entry, an AI reflection responds to it in real time over WebSockets, you can chat back and forth about what you wrote, and when you're done the conversation gets summarized and saved to your personal archive.

This is the final week of the build. The focus was stability and cleanup rather than new features: fixing a deployment-breaking threading bug in `app.py`, tidying up the codebase, and pulling everything together into one coherent README instead of five separate weekly ones.

---

## What changed this week

### 1. `app.py` threading fix
Flask-SocketIO needs a "async mode" to know how to handle concurrent WebSocket connections, and it normally prefers `eventlet` or `gevent` if either is installed. Both of those libraries monkey-patch Python's networking internals in ways that are broken (or flaky) on newer Python versions, which caused connection drops and silent failures under load.

The fix was to pin the async mode explicitly:

```python
socketio = SocketIO(
    app,
    async_mode="threading",
    cors_allowed_origins="*"
)
```

With `async_mode="threading"` and `simple-websocket` installed (no `eventlet`/`gevent` in the request path), Socket.IO falls back to Python's native threading model. It's slightly less throughput-efficient than eventlet under heavy concurrency, but for a journaling app with a handful of concurrent users per room, it's more than enough — and it removes an entire class of environment-specific bugs.

### 2. Final polish
- Cleaned up route organization in `app.py` (auth, entries, chat, AJAX fallbacks, and WebSocket events are now grouped under clear section headers).
- Verified the HTTP fallback routes (`/chat_ajax`, `/end_chat_ajax`) still work correctly if a client's WebSocket connection fails, so the app degrades gracefully instead of breaking.
- Confirmed password reset emails (via Resend), password validation rules, and session-based auth all behave correctly end-to-end.
- General pass over error handling and flash messages for clarity.

### 3. Consolidated README
Weeks 1–3 each had their own README. This week's README replaces the need to read through all of them — it documents the app as it stands now, complete.

---

## Features

- **Account system** — signup, login, logout, and email-based password reset (via [Resend](https://resend.com)) with expiring, signed tokens.
- **AI-guided journaling** — write a free-form entry and get an AI-generated reflection back.
- **Real-time chat** — continue the conversation with the AI about your entry over WebSockets (Flask-SocketIO), with typing indicators and live updates. Falls back to AJAX/HTTP if WebSockets aren't available.
- **Auto-generated titles** — entries are automatically titled based on the conversation once enough context exists.
- **Conversation summaries** — end a conversation to get an AI-generated summary saved with the entry.
- **Archive** — browse and filter past entries by date.
- **Per-user data isolation** — every entry, message, and chat room is scoped to the logged-in user.

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Flask, Flask-SocketIO (threading mode) |
| AI | Google Gemini (`google-genai`) for reflections, chat replies, summaries, and titles |
| Database | SQLite (`db.py`) |
| Auth | `werkzeug.security` password hashing, `itsdangerous` signed tokens for password reset |
| Email | Resend API |
| Frontend | Jinja2 templates, static CSS/JS |
| Deployment | Render (`render.yaml`), Gunicorn |

---

## Project structure

```
AI-journaling-/
├── app.py              # Flask routes, auth, WebSocket events
├── db.py                # Database access layer
├── reflection.py         # AI logic: reflections, chat replies, summaries, titles
├── templates/            # Jinja2 HTML templates
├── static/               # CSS / JS / assets
├── requirements.txt
├── runtime.txt
└── render.yaml           # Render deployment config
```

---

## Running locally

1. Clone the repo and install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Create a `.env` file in the project root with:
   ```
   SECRET_KEY=your-secret-key
   RESEND_API_KEY=your-resend-key
   RESEND_FROM_EMAIL=onboarding@resend.dev
   GEMINI_API_KEY=your-gemini-key
   ```
   (check `reflection.py` for the exact AI-related environment variable name it expects)
3. Run the app:
   ```bash
   python app.py
   ```
4. Visit `http://localhost:5000`.

---

## Deployment

The app is configured for [Render](https://render.com) via `render.yaml`, using Gunicorn as the production server. The `async_mode="threading"` fix applies here too — it's what makes WebSocket connections stable in the deployed environment, matching the local dev setup.

---

## Project wrap-up

Over the seven weeks, Journelle grew from a basic entry-and-reflection prototype into a full journaling app with accounts, real-time AI chat, summaries, and an archive. The biggest lessons from this final week were about deployment realism: async library compatibility issues that never show up in local testing can quietly break an app in production, and it's worth pinning explicit configuration (like `async_mode`) rather than relying on auto-detection.

Possible next steps beyond this project:
- Move from SQLite to a hosted database for multi-instance deployments.
- Add rate limiting on AI-facing routes.
- Export entries (PDF/Markdown) from the archive.
