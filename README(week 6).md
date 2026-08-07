# Journelle — Week 6: Production Deployment on Render

## What changed this week

Week 6 moved the app from PythonAnywhere (free tier, no WebSocket
support) to Render, a platform that supports WebSockets on its free
tier with persistent disk storage. This involved navigating a series
of real-world Python version and server compatibility issues that are
worth documenting in detail, since they're instructive about the
difference between development and production environments.

---

## 1. Why Render Instead of PythonAnywhere

PythonAnywhere's free tier explicitly does not support WebSocket
connections — outbound connections are restricted to a whitelist of
approved domains, and the server infrastructure doesn't support
long-lived WebSocket connections. Since Week 5 built the entire chat
experience around WebSockets, a different host was needed.

Render was chosen because:
- Free tier supports WebSockets natively
- Persistent disk means `journal.db` survives deploys and restarts
- Deploys automatically from GitHub on every push to `main`
- Supports Python Flask apps with gunicorn out of the box

---

## 2. Deployment Configuration

**`render.yaml`** — tells Render how to build and run the app:

```yaml
services:
  - type: web
    name: journelle
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn --worker-class gthread --threads 4 --bind 0.0.0.0:$PORT app:app
    envVars:
      - key: GEMINI_API_KEY
        sync: false
      - key: SECRET_KEY
        sync: false
      - key: RESEND_API_KEY
        sync: false
      - key: RESEND_FROM_EMAIL
        sync: false
    autoDeploy: true
```

`sync: false` on env vars means they must be manually set in the
Render dashboard — they are never stored in the repository.

---

## 3. Compatibility Issues Encountered and Resolved

This section documents the actual errors hit during deployment, what
caused them, and how each was fixed.

### Issue 1: Werkzeug refusing to run in production

**Error:**
```
RuntimeError: The Werkzeug web server is not designed to run
in production. Pass allow_unsafe_werkzeug=True to the run()
method to disable this error.
```

**Cause:** the app's `if __name__ == "__main__"` block called
`socketio.run(app, ...)` which uses Werkzeug's development server.
Render runs this block directly rather than using gunicorn, because
the `startCommand` was incorrectly set to `python app.py` instead of
`gunicorn ...`.

**Fix:** updated `render.yaml` startCommand to use gunicorn. Also
added `allow_unsafe_werkzeug=True` as a fallback for local development
only.

---

### Issue 2: Python 3.14 + simple-websocket incompatibility

**Error:**
```
TypeError: argument of type 'int' is not a container or iterable
  File "simple_websocket/ws.py", line 264, in __init__
    if 'werkzeug.socket' in environ:
```

**Cause:** Render defaulted to Python 3.14.3 (released after our
development environment). The `simple_websocket` package had not yet
updated its code to handle a change in how gunicorn passes the WSGI
`environ` dict in Python 3.14 — specifically, `environ` was being
initialized with an integer in some code path rather than a dict,
making the `in` operator fail.

**Attempts to fix by pinning Python version:**
- `runtime.txt` with `python-3.11.9` — Render does not read this file
- `PYTHON_VERSION=3.11.9` environment variable — correctly documented
  by Render but the build cache was serving Python 3.14.3 regardless

**Final fix:** switched from `simple_websocket.Server` to gunicorn's
built-in `gthread` worker, combined with `async_mode="threading"` in
Flask-SocketIO. This completely eliminates the dependency on
`simple_websocket` for the production server, working on any Python
version including 3.14.

---

### Issue 3: Flask-SocketIO session setter error

**Error:**
```
AttributeError: property 'session' of 'RequestContext'
object has no setter
```

**Cause:** Flask-SocketIO 5.3.x tries to directly assign to
`ctx.session`, which became a read-only property in Flask 3.x. This
is a known compatibility break between Flask 3.x and older
Flask-SocketIO versions.

**Fix:** upgraded Flask-SocketIO from `5.3.6` to `5.5.1`, which
handles Flask 3.x session management correctly.

---

## 4. Final Working Configuration

| Component | Choice | Reason |
|---|---|---|
| WSGI server | gunicorn | Production-grade, widely supported |
| Worker class | `gthread` | Built into gunicorn, Python 3.14 compatible |
| Threads | 4 | Enough for concurrent WebSocket + HTTP requests |
| Flask-SocketIO async mode | `threading` | No eventlet/gevent needed, any Python version |
| Flask-SocketIO version | 5.5.1 | Flask 3.x compatible |

---

## 5. Environment Variables Required on Render

Set these in the Render dashboard → Environment tab:

| Variable | Description |
|---|---|
| `GEMINI_API_KEY` | Google Gemini API key for AI reflections |
| `SECRET_KEY` | Flask session signing key (any random string) |
| `RESEND_API_KEY` | Resend API key for password reset emails |
| `RESEND_FROM_EMAIL` | Sender address for password reset emails |

The app will start without `RESEND_API_KEY` and `RESEND_FROM_EMAIL`
but the forgot-password email flow will fail silently (the error is
caught and logged rather than crashing the app).

---

## 6. Live URL

```
https://ai-journaling-dyvk.onrender.com
```

Note: Render's free tier spins down after 15 minutes of inactivity.
The first request after the service is idle takes approximately
20-30 seconds to wake up. Subsequent requests are fast.

---

## Files changed this week

```
new file:   render.yaml       — Render deployment configuration
modified:   app.py            — allow_unsafe_werkzeug=True in run();
                               async_mode changed to "threading"
modified:   requirements.txt  — flask-socketio bumped to 5.5.1;
                               gunicorn and simple-websocket added
```
