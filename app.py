import os
import re
import resend

from itsdangerous import (
    URLSafeTimedSerializer,
    BadSignature,
    SignatureExpired
)

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    jsonify
)

from flask_socketio import (
    SocketIO,
    emit,
    join_room,
    leave_room
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

from dotenv import load_dotenv
from functools import wraps
from datetime import datetime


# =========================================================
# ENVIRONMENT VARIABLES
# =========================================================

load_dotenv()

resend.api_key = os.getenv("RESEND_API_KEY")

RESEND_FROM_EMAIL = os.getenv(
    "RESEND_FROM_EMAIL",
    "onboarding@resend.dev"
)


# =========================================================
# DATABASE IMPORTS
# =========================================================

from db import (
    init_db,
    save_entry,
    get_all_entries,
    get_recent_entries,
    get_entry_by_id,
    get_entries_by_date,
    create_user,
    get_user_by_username,
    get_user_by_email,
    save_message,
    get_messages_for_entry,
    save_summary,
    get_entry_owner,
    update_user_password,
    update_entry_title,
    get_entry_title
)


# =========================================================
# AI IMPORTS
# =========================================================

from reflection import (
    generate_reflection,
    generate_chat_reply,
    generate_summary,
    generate_title
)


# =========================================================
# FLASK APP + SOCKET.IO
# =========================================================

app = Flask(__name__)

app.secret_key = os.getenv(
    "SECRET_KEY",
    "dev-secret-key-change-this"
)

# async_mode=None lets Flask-SocketIO auto-detect the best
# available backend. With simple-websocket installed and
# neither eventlet nor gevent present, it uses threading —
# which works on Python 3.13 without any compatibility issues.
socketio = SocketIO(
    app,
    async_mode="threading",
    cors_allowed_origins="*"
)


# =========================================================
# TEMPLATE FILTERS
# =========================================================

@app.template_filter("readable_date")
def readable_date(iso_string):
    dt = datetime.fromisoformat(iso_string)
    return dt.strftime("%B %d, %Y at %I:%M %p")


# =========================================================
# GLOBAL TEMPLATE CONTEXT
# =========================================================

@app.context_processor
def inject_sidebar_context():

    recent_entries = []
    active_entry_id = None

    user_id = session.get("user_id")

    if user_id is not None:

        recent_entries = get_recent_entries(
            user_id,
            limit=7
        )

        if request.endpoint == "view_entry":

            active_entry_id = (
                request.view_args.get("entry_id")
                if request.view_args
                else None
            )

    return {
        "recent_entries": recent_entries,
        "active_entry_id": active_entry_id
    }




def format_relative_time(iso_string):
    now=datetime.now()
    dt=datetime.fromisoformat(iso_string)
    diff=now-dt
    s=int(diff.total_seconds())
    if s<10:return "Just now"
    if s<60:return f"{s} sec ago"
    if s<3600:return f"{s//60} min ago"
    if s<86400:return f"{s//3600} hr ago"
    if s<172800:return "Yesterday"
    if s<604800:return f"{s//86400} days ago"
    return dt.strftime("%b %d")


# =========================================================
# AUTHENTICATION HELPERS
# =========================================================

def login_required(view_func):

    @wraps(view_func)
    def wrapped(*args, **kwargs):

        if "user_id" not in session:
            flash("Please log in to continue.")
            return redirect(url_for("login"))

        return view_func(*args, **kwargs)

    return wrapped


def validate_password(password):

    if len(password) < 8:
        return False, "Password must be at least 8 characters long."

    if not re.search(r"[A-Z]", password):
        return False, "Password must include at least one uppercase letter."

    if not re.search(r"[a-z]", password):
        return False, "Password must include at least one lowercase letter."

    if not re.search(r"\d", password):
        return False, "Password must include at least one number."

    if not re.search(r"[^A-Za-z0-9]", password):
        return False, "Password must include at least one special character."

    return True, None


# =========================================================
# PASSWORD RESET TOKEN HELPERS
# =========================================================

def get_reset_serializer():
    return URLSafeTimedSerializer(
        app.secret_key,
        salt="journelle-password-reset"
    )


def generate_reset_token(user_id):
    return get_reset_serializer().dumps({"user_id": user_id})


def verify_reset_token(token, max_age=1800):

    try:
        data = get_reset_serializer().loads(token, max_age=max_age)
        return data.get("user_id")
    except (SignatureExpired, BadSignature):
        return None


# =========================================================
# PASSWORD RESET EMAIL
# =========================================================

def send_password_reset_email(recipient_email, username, reset_url):

    if not resend.api_key:
        raise RuntimeError(
            "RESEND_API_KEY is missing from the environment."
        )

    params = {
        "from": f"Journelle <{RESEND_FROM_EMAIL}>",
        "to": [recipient_email],
        "subject": "Reset your Journelle password",
        "html": f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="margin:0;padding:0;background:#f7f4ef;font-family:Arial,sans-serif;color:#2f2a27;">
            <div style="max-width:600px;margin:0 auto;padding:40px 20px;">
                <div style="background:#ffffff;border:1px solid #e7dfd4;border-radius:24px;padding:36px;">
                    <p style="margin:0 0 10px;font-size:14px;font-weight:700;color:#8f7258;">JOURNELLE</p>
                    <h1 style="margin:0 0 18px;font-size:28px;line-height:1.2;color:#2f2a27;">Reset your password</h1>
                    <p style="margin:0 0 16px;font-size:16px;line-height:1.6;">Hi {username},</p>
                    <p style="margin:0 0 24px;font-size:16px;line-height:1.6;">We received a request to reset the password for your Journelle account.</p>
                    <a href="{reset_url}" style="display:inline-block;padding:14px 22px;background:#8f7258;color:#ffffff;text-decoration:none;border-radius:999px;font-size:15px;font-weight:700;">Reset Password</a>
                    <p style="margin:24px 0 0;font-size:14px;line-height:1.6;color:#746b65;">This link expires in 30 minutes.</p>
                    <p style="margin:12px 0 0;font-size:14px;line-height:1.6;color:#746b65;">If you did not request a password reset, you can ignore this email.</p>
                </div>
            </div>
        </body>
        </html>
        """
    }

    resend.Emails.send(params)
    return True


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

init_db()


# =========================================================
# SIGNUP
# =========================================================

@app.route("/signup", methods=["GET", "POST"])
def signup():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not username or not email or not password:
            flash("Username, email, and password are all required.")
            return redirect(url_for("signup"))

        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            flash("Please enter a valid email address.")
            return redirect(url_for("signup"))

        is_valid, error_message = validate_password(password)
        if not is_valid:
            flash(error_message)
            return redirect(url_for("signup"))

        if get_user_by_username(username):
            flash("That username is already taken. Try another.")
            return redirect(url_for("signup"))

        if get_user_by_email(email):
            flash("An account with that email already exists.")
            return redirect(url_for("signup"))

        user_id = create_user(
            username,
            email,
            generate_password_hash(password)
        )

        session["user_id"] = user_id
        session["username"] = username

        flash(f"Welcome, {username}! Your account has been created.")
        return redirect(url_for("index"))

    return render_template("signup.html")


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = get_user_by_username(username)

        if user is None or not check_password_hash(
            user["password_hash"], password
        ):
            flash("Incorrect username or password.")
            return redirect(url_for("login"))

        session["user_id"] = user["id"]
        session["username"] = user["username"]

        flash(f"Welcome back, {username}!")
        return redirect(url_for("index"))

    return render_template("login.html")


# =========================================================
# FORGOT PASSWORD
# =========================================================

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()

        if not email:
            flash("Please enter your email address.")
            return redirect(url_for("forgot_password"))

        user = get_user_by_email(email)

        if user is not None:

            token = generate_reset_token(user["id"])
            reset_url = url_for(
                "reset_password", token=token, _external=True
            )

            try:
                send_password_reset_email(
                    recipient_email=user["email"],
                    username=user["username"],
                    reset_url=reset_url
                )
            except Exception as error:
                app.logger.error(
                    "Password reset email failed: %s", error
                )

        flash(
            "If an account exists with that email, "
            "a password reset link has been sent."
        )
        return redirect(url_for("forgot_password"))

    return render_template("forgot_password.html")


# =========================================================
# RESET PASSWORD
# =========================================================

@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):

    user_id = verify_reset_token(token)

    if user_id is None:
        flash("This password reset link is invalid or has expired.")
        return redirect(url_for("forgot_password"))

    if request.method == "POST":

        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not password or not confirm_password:
            flash("Please complete both password fields.")
            return redirect(url_for("reset_password", token=token))

        if password != confirm_password:
            flash("Passwords do not match.")
            return redirect(url_for("reset_password", token=token))

        is_valid, error_message = validate_password(password)
        if not is_valid:
            flash(error_message)
            return redirect(url_for("reset_password", token=token))

        update_user_password(user_id, generate_password_hash(password))
        session.clear()

        flash("Your password has been reset successfully. You can now log in.")
        return redirect(url_for("login"))

    return render_template("reset_password.html")


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():
    session.clear()
    flash("You've been logged out.")
    return redirect(url_for("login"))


# =========================================================
# ARCHIVE
# =========================================================

@app.route("/archive")
@login_required
def archive():

    user_id = session["user_id"]
    selected_date = request.args.get("date", "").strip()

    entries = (
        get_entries_by_date(user_id, selected_date)
        if selected_date
        else get_all_entries(user_id)
    )

    return render_template(
        "archive.html",
        entries=entries,
        selected_date=selected_date
    )


# =========================================================
# NEW ENTRY PAGE
# =========================================================

@app.route("/")
@login_required
def index():
    return render_template("new_entry.html")


# =========================================================
# START CHAT (first message → creates entry)
# =========================================================

@app.route("/start_chat", methods=["POST"])
@login_required
def start_chat():

    user_id = session["user_id"]
    content = request.form.get("message", "").strip()

    if not content:
        flash("Write something before sending.")
        return redirect(url_for("index"))

    reflection = generate_reflection(content)
    new_id = save_entry(user_id, content, reflection)

    return redirect(url_for("view_entry", entry_id=new_id))


# =========================================================
# VIEW ENTRY
# =========================================================

@app.route("/entry/<int:entry_id>")
@login_required
def view_entry(entry_id):

    user_id = session["user_id"]
    entry = get_entry_by_id(user_id, entry_id)

    if entry is None:
        flash("That entry doesn't exist.")
        return redirect(url_for("archive"))

    messages = get_messages_for_entry(entry_id)

    return render_template(
        "entry.html",
        entry=entry,
        messages=messages
    )


# =========================================================
# CHAT (traditional form fallback — kept for safety)
# =========================================================

@app.route("/entry/<int:entry_id>/chat", methods=["POST"])
@login_required
def chat(entry_id):

    user_id = session["user_id"]

    if get_entry_owner(entry_id) != user_id:
        flash("That entry doesn't exist.")
        return redirect(url_for("archive"))

    entry = get_entry_by_id(user_id, entry_id)

    if entry["summary"]:
        flash("This conversation has already ended.")
        return redirect(url_for("view_entry", entry_id=entry_id))

    user_message = request.form.get("message", "").strip()

    if not user_message:
        flash("Type something before sending.")
        return redirect(url_for("view_entry", entry_id=entry_id))

    save_message(entry_id, "user", user_message)

    history = [{"role": "ai", "content": entry["reflection"]}]
    for m in get_messages_for_entry(entry_id):
        history.append({"role": m["role"], "content": m["content"]})

    ai_reply = generate_chat_reply(entry["content"], history)
    save_message(entry_id, "ai", ai_reply)

    return redirect(url_for("view_entry", entry_id=entry_id))


# =========================================================
# END CHAT (traditional form fallback — kept for safety)
# =========================================================

@app.route("/entry/<int:entry_id>/end_chat", methods=["POST"])
@login_required
def end_chat(entry_id):

    user_id = session["user_id"]

    if get_entry_owner(entry_id) != user_id:
        flash("That entry doesn't exist.")
        return redirect(url_for("archive"))

    entry = get_entry_by_id(user_id, entry_id)

    if entry["summary"]:
        flash("This conversation has already ended.")
        return redirect(url_for("view_entry", entry_id=entry_id))

    history = [{"role": "ai", "content": entry["reflection"]}]
    for m in get_messages_for_entry(entry_id):
        history.append({"role": m["role"], "content": m["content"]})

    summary = generate_summary(entry["content"], history)
    save_summary(entry_id, summary)

    flash("Conversation ended and summarized.")
    return redirect(url_for("view_entry", entry_id=entry_id))


# =========================================================
# AJAX ROUTES (HTTP fallback if WebSocket unavailable)
# =========================================================

@app.route("/entry/<int:entry_id>/chat_ajax", methods=["POST"])
@login_required
def chat_ajax(entry_id):

    user_id = session["user_id"]

    if get_entry_owner(entry_id) != user_id:
        return jsonify({"error": "Entry not found."}), 404

    entry = get_entry_by_id(user_id, entry_id)

    if not entry:
        return jsonify({"error": "Entry not found."}), 404

    if entry["summary"]:
        return jsonify({"error": "This conversation has already ended."}), 400

    data = request.get_json()
    user_message = (data.get("message", "") if data else "").strip()

    if not user_message:
        return jsonify({"error": "Message cannot be empty."}), 400

    save_message(entry_id, "user", user_message)

    history = [{"role": "ai", "content": entry["reflection"]}]
    for m in get_messages_for_entry(entry_id):
        history.append({"role": m["role"], "content": m["content"]})

    ai_reply = generate_chat_reply(entry["content"], history)
    save_message(entry_id, "ai", ai_reply)

    return jsonify({"user_message": user_message, "ai_reply": ai_reply})


@app.route("/entry/<int:entry_id>/end_chat_ajax", methods=["POST"])
@login_required
def end_chat_ajax(entry_id):

    user_id = session["user_id"]

    if get_entry_owner(entry_id) != user_id:
        return jsonify({"error": "Entry not found."}), 404

    entry = get_entry_by_id(user_id, entry_id)

    if not entry:
        return jsonify({"error": "Entry not found."}), 404

    if entry["summary"]:
        return jsonify({"error": "This conversation has already ended."}), 400

    history = [{"role": "ai", "content": entry["reflection"]}]
    for m in get_messages_for_entry(entry_id):
        history.append({"role": m["role"], "content": m["content"]})

    summary = generate_summary(entry["content"], history)
    save_summary(entry_id, summary)

    return jsonify({"summary": summary})


# =========================================================
# WEBSOCKET EVENTS
# =========================================================

@socketio.on("connect")
def handle_connect():
    """
    Fires when a client opens the Socket.IO connection.
    We verify they are logged in before accepting.
    """
    if "user_id" not in session:
        return False   # reject unauthenticated connections


@socketio.on("join_entry")
def handle_join(data):
    """
    Client tells us which entry conversation to join.
    We put them in a private room named after that entry
    so emits are scoped to this user's tab only.
    """
    entry_id = data.get("entry_id")
    if entry_id is not None:
        join_room(f"entry_{entry_id}")


@socketio.on("send_message")
def handle_send_message(data):
    """
    Main real-time chat event.

    Flow:
    1. Validate the user owns this entry
    2. Save their message to the database
    3. Emit their message back so the UI can render it
    4. Call Gemini, save the reply
    5. Emit the AI reply to the same room
    """
    user_id = session.get("user_id")
    entry_id = data.get("entry_id")
    user_message = (data.get("message") or "").strip()

    if not user_id or not entry_id or not user_message:
        emit("error", {"message": "Invalid request."})
        return

    if get_entry_owner(entry_id) != user_id:
        emit("error", {"message": "Entry not found."})
        return

    entry = get_entry_by_id(user_id, entry_id)

    if not entry:
        emit("error", {"message": "Entry not found."})
        return

    if entry["summary"]:
        emit("error", {"message": "This conversation has already ended."})
        return

    # Save and echo the user message immediately
    save_message(entry_id, "user", user_message)
    emit("message_saved", {"role": "user", "content": user_message})

    # Show typing indicator
    emit("typing_start", {})

    # Build history and get AI reply
    history = [{"role": "ai", "content": entry["reflection"]}]
    for m in get_messages_for_entry(entry_id):
        history.append({"role": m["role"], "content": m["content"]})

    ai_reply = generate_chat_reply(entry["content"], history)
    save_message(entry_id, "ai", ai_reply)

    emit(
        "typing_stop",
        {},
        to=f"entry_{entry_id}"
    )

    emit(
        "ai_reply",
        {
            "content": ai_reply
        },
        to=f"entry_{entry_id}"
    )

    title_info = get_entry_title(entry_id)

    if (not title_info) or (not title_info["locked"]):

        print("\n===== TITLE GENERATION =====")

        try:
            title = generate_title(
                entry["content"],
                history + [{"role": "ai", "content": ai_reply}]
            )

            print("Generated title:", repr(title))

            if title:
                update_entry_title(entry_id, title)
                print("Saved title to database")

                emit(
                    "title_updated",
                    {
                        "entry_id": entry_id,
                        "title": title
                    },
                    to=f"entry_{entry_id}"
                )
            else:
                print("generate_title() returned None or empty")

        except Exception as e:
            print("TITLE ERROR:", e)

    print("============================\n")


@socketio.on("end_conversation")
def handle_end_conversation(data):
    """
    Generates and saves a summary, then emits it to
    the client so the UI can render it without a reload.
    """
    user_id = session.get("user_id")
    entry_id = data.get("entry_id")

    if not user_id or not entry_id:
        emit("error", {"message": "Invalid request."})
        return

    if get_entry_owner(entry_id) != user_id:
        emit("error", {"message": "Entry not found."})
        return

    entry = get_entry_by_id(user_id, entry_id)

    if not entry:
        emit("error", {"message": "Entry not found."})
        return

    if entry["summary"]:
        emit("error", {"message": "This conversation has already ended."})
        return

    emit("summarising", {})

    history = [{"role": "ai", "content": entry["reflection"]}]
    for m in get_messages_for_entry(entry_id):
        history.append({"role": m["role"], "content": m["content"]})

    summary = generate_summary(entry["content"], history)
    save_summary(entry_id, summary)

    emit("summary_ready", {"summary": summary})


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host="0.0.0.0", port=port, debug=True, allow_unsafe_werkzeug=True)