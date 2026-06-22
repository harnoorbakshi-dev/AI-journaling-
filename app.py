from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from functools import wraps
from datetime import datetime

load_dotenv()  # loads OPENAI_API_KEY from .env into the environment

from db import init_db, save_entry, get_all_entries, get_entry_by_id, get_entries_by_date, create_user, get_user_by_username
from reflection import generate_reflection

app = Flask(__name__)
app.secret_key = "dev-secret-key-change-this"  # required for flash messages to work

@app.template_filter("readable_date")
def readable_date(iso_string):
    """
    Converts a raw ISO timestamp like '2026-06-18T02:43:22.416825'
    into something human-friendly like 'June 18, 2026 at 2:43 AM'.
    We keep storing the raw ISO format in the database (it sorts and
    filters correctly), and only convert it to a nice format here,
    right before it's displayed.
    """
    dt = datetime.fromisoformat(iso_string)
    return dt.strftime("%B %d, %Y at %I:%M %p")


def login_required(view_func):
    """
    Decorator that protects a route so it can only be accessed by a
    logged-in user. If no one is logged in, redirects to the login page
    instead of showing the page.
    """
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)
    return wrapped

# Initialize the database when the app starts.
# If journal.db doesn't exist, this creates it fresh.
# If journal.db exists but is corrupted, init_db() raises a RuntimeError,
# which we catch here so the app fails with a clear message at startup
# instead of crashing unpredictably mid-request later.
init_db()
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Username and password are both required.")
            return redirect(url_for("signup"))

        existing = get_user_by_username(username)
        if existing:
            flash("That username is already taken. Try another.")
            return redirect(url_for("signup"))

        password_hash = generate_password_hash(password)
        user_id = create_user(username, password_hash)

        session["user_id"] = user_id
        session["username"] = username
        flash(f"Welcome, {username}! Your account has been created.")
        return redirect(url_for("index"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = get_user_by_username(username)

        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Incorrect username or password.")
            return redirect(url_for("login"))

        session["user_id"] = user["id"]
        session["username"] = user["username"]
        flash(f"Welcome back, {username}!")
        return redirect(url_for("index"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You've been logged out.")
    return redirect(url_for("login"))

@app.route("/")
@login_required
def index():
    user_id = session["user_id"]
    selected_date = request.args.get("date", "").strip()

    if selected_date:
        entries = get_entries_by_date(user_id, selected_date)
    else:
        entries = get_all_entries(user_id)

    return render_template("index.html", entries=entries, selected_date=selected_date)


@app.route("/save", methods=["POST"])
@login_required
def save():
    user_id = session["user_id"]
    content = request.form.get("content", "").strip()

    if not content:
        flash("Your entry can't be empty — write a little something first.")
        return redirect(url_for("index"))

    reflection = generate_reflection(content)
    new_id = save_entry(user_id, content, reflection)

    return redirect(url_for("view_entry", entry_id=new_id))

@app.route("/entry/<int:entry_id>")
@login_required
def view_entry(entry_id):
    user_id = session["user_id"]
    entry = get_entry_by_id(user_id, entry_id)
    if entry is None:
        flash("That entry doesn't exist.")
        return redirect(url_for("index"))
    return render_template("entry.html", entry=entry)


if __name__ == "__main__":
    app.run(debug=True)