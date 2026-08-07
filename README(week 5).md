# Journelle — Week 5: Real-Time WebSocket Chat

## What changed this week

Week 5 replaced the page-reload chat cycle with a genuine real-time
WebSocket connection using Flask-SocketIO. Sending a message, seeing
the AI think, and receiving a reply now all happen in a single
persistent connection — no page reload, no full HTTP round-trip per
message, no re-rendering the entire conversation on every send.

---

## 1. The Problem with the Previous Architecture

Before this week, the chat flow was:

```
User types → form POST → Flask saves message → Flask calls Gemini →
Flask saves reply → redirect → browser fetches entire page again →
browser re-renders entire conversation
```

Every message required a full page reload. The user had no feedback
while Gemini was generating — the browser just sat frozen. On slow
connections, this could mean 3-5 seconds of a blank/loading page per
message. This felt nothing like a real conversation.

---

## 2. What WebSockets Change

With Socket.IO:

```
User types → JavaScript emits "send_message" event →
server receives instantly → server saves message → emits
"typing_start" back → client shows dots → server calls
Gemini → server saves reply → emits "ai_reply" →
client renders bubble — all in one persistent connection
```

The page never reloads. The connection stays open. The user sees their
message appear the instant they press Enter, then animated dots while
Gemini thinks, then the reply arrives and replaces the dots — just
like iMessage or WhatsApp.

---

## 3. Flask-SocketIO Integration

**New dependency:** `flask-socketio==5.5.1`

**Initialization in `app.py`:**
```python
from flask_socketio import SocketIO, emit, join_room, leave_room

socketio = SocketIO(app, async_mode="threading", cors_allowed_origins="*")
```

`async_mode="threading"` uses Python's standard threading module as
the async backend — no eventlet or gevent required, fully compatible
with all Python versions.

**WebSocket events defined:**

| Event (server receives) | What it does |
|---|---|
| `connect` | Verifies the user is logged in; rejects unauthenticated connections |
| `join_entry` | Adds the client to a private Socket.IO room named `entry_<id>` |
| `send_message` | Validates ownership, saves message, emits `typing_start`, calls Gemini, saves reply, emits `typing_stop` + `ai_reply` |
| `end_conversation` | Validates ownership, generates summary, saves it, emits `summarising` then `summary_ready` |

| Event (server emits) | What it does |
|---|---|
| `message_saved` | Acknowledges the user's message was stored |
| `typing_start` | Triggers the bouncing dots indicator on the client |
| `typing_stop` | Removes the dots indicator |
| `ai_reply` | Delivers the AI's response text to the client |
| `summarising` | Shows "Summarising..." status to the client |
| `summary_ready` | Delivers the finished summary to the client |
| `error` | Delivers a human-readable error message for any failure |

---

## 4. Client-Side JavaScript (entry.html)

The Socket.IO CDN client (`socket.io.min.js` v4.7.5) is loaded in
`entry.html`. The key functions:

- **`sendMessage()`** — reads the textarea, renders the user bubble
  optimistically (immediately, before the server confirms), clears the
  input, disables the send button, and emits `send_message`
- **`showTypingIndicator()`** — appends a bouncing three-dot animation
  bubble styled as an AI message
- **`hideTypingIndicator()`** — removes the dots and replaces them with
  the real AI reply via `appendAiBubble()`
- **`escapeHtml()`** — sanitizes all user/AI text before injecting it
  into the DOM, preventing XSS
- **`scrollToBottom()`** — keeps the conversation scrolled to the
  latest message after every append

The form's default submit behavior is fully intercepted —
`event.preventDefault()` stops the traditional POST, and the
JavaScript handles everything via WebSocket instead.

**Enter key behavior:** Enter sends the message; Shift+Enter inserts a
new line — matching the convention used by Slack, WhatsApp, and most
modern messaging apps.

---

## 5. Typing Indicator CSS

```css
.typing-dots {
    display: flex;
    gap: 5px;
    align-items: center;
}

.typing-dots span {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--muted);
    animation: typingBounce 1.2s infinite ease-in-out;
}

@keyframes typingBounce {
    0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
    30% { transform: translateY(-6px); opacity: 1; }
}
```

Three dots staggered at 0.2s intervals give a natural, wave-like
typing animation consistent with what users expect from messaging apps.

---

## 6. AJAX Fallback Routes (kept alongside WebSockets)

Two HTTP routes were retained alongside the WebSocket events:
`/entry/<id>/chat_ajax` (POST, returns JSON) and
`/entry/<id>/end_chat_ajax` (POST, returns JSON). These are kept as a
safety net for environments where WebSocket connections are blocked
(corporate proxies, some VPNs, older browsers). If Socket.IO falls
back to HTTP long-polling, these routes ensure the chat still works.

---

## 7. Security: Room-Based Isolation

Every entry gets its own Socket.IO room named `entry_<id>`. When a
client opens an entry page, the JavaScript emits `join_entry` and the
server calls `join_room(f"entry_{entry_id}")`. AI replies are emitted
`to=f"entry_{entry_id}"` so they only reach the tab that's actually
viewing that entry — not any other open tabs or other users.

Entry ownership is re-verified inside every WebSocket event handler,
not just at the HTTP layer. A malicious client that manually emits
`send_message` with someone else's entry id will receive an `error`
event, not a successful reply.

---

## Files changed this week

```
modified:   app.py           — SocketIO initialization, 4 WebSocket
                               event handlers, 2 AJAX fallback routes
modified:   templates/entry.html — Socket.IO CDN script added,
                               entire <script> block replaced with
                               WebSocket client code
modified:   static/css/style.css — typing indicator animation added
modified:   requirements.txt — flask-socketio, simple-websocket,
                               gunicorn added
```

---

## New packages

```
flask-socketio==5.5.1
simple-websocket
gunicorn
```
