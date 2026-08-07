# Journelle — Week 4: UI Overhaul, Auth Improvements & Change in Layout

## What changed this week

Week 4 focused on three distinct areas: a complete visual identity
upgrade (Gilroy font system-wide, dark mode), meaningful security
improvements to authentication (strong password validation, forgot
password with real email delivery), and a structural UX shift inspired
by Pi.ai — moving from a top-navigation layout to a persistent left
sidebar with a full-screen conversation canvas.

---

## 1. Gilroy Font System

**Before:** the app used Fraunces (serif headings) + Inter (body text),
loaded from Google Fonts.

**After:** Gilroy is used exclusively across every element — headings,
body text, buttons, inputs, labels, placeholders, and the logo. The
two officially free weights (Light 300 and ExtraBold 800) are
self-hosted as `.woff2` files in `static/fonts/`, eliminating the
Google Fonts network dependency entirely.

**Why two weights only:** Gilroy's full weight range (Regular, Medium,
SemiBold, Bold) is a paid commercial license. Using Light + ExtraBold
covers the full typographic range the app actually needs — Light for
body copy and UI labels, ExtraBold for headings, the logo, and buttons.

**Files changed:**
- `static/fonts/gilroy-light.woff2` — new
- `static/fonts/gilroy-extrabold.woff2` — new
- `static/css/style.css` — `@font-face` declarations replaced Google
  Fonts `@import`; every `font-family` reference updated

---

## 2. Dark Mode

A full dark mode implementation using CSS custom properties, with a
toggle button in the sidebar footer.

**Implementation approach:** all colors in the design system are
defined as CSS variables in `:root`. A `[data-theme="dark"]` attribute
selector on the `<html>` element overrides every variable with its dark
equivalent. JavaScript reads/writes `localStorage` to persist the
user's preference across sessions and page navigations.

**Color tokens changed for dark mode:**

| Token | Light | Dark |
|---|---|---|
| `--background` | `#F8F7F4` | `#171719` |
| `--card` | `#FFFFFF` | `#222225` |
| `--card-soft` | `#F4F2FF` | `#2A2835` |
| `--primary` | `#6B63FF` | `#8B83FF` |
| `--text` | `#222437` | `#F4F2EE` |
| `--muted` | `#7D8195` | `#AAA8B2` |
| `--border` | `#E9E5DD` | `#343438` |

Component-specific overrides were added for: the nav bar (darker
frosted glass), the conversation summary border, the finish button
shadow, the composer focus ring, and date inputs (`color-scheme: dark`
to fix the browser's native date picker in dark environments).

**Files changed:**
- `static/css/style.css` — `[data-theme="dark"]` block added
- `templates/base.html` — theme toggle button added to sidebar footer
- JavaScript added to `base.html` to read/write `localStorage` and
  apply `data-theme` on load without flash

---

## 3. Strong Password Validation

**Before:** signup accepted any non-empty password.

**After:** `validate_password()` in `app.py` enforces:
- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one number
- At least one special character (any character that is not A-Z, a-z,
  or 0-9)

The same validation runs on both the signup form and the reset password
form, so the same rules apply everywhere a password is set. Validation
happens server-side before any database write. The specific failing
requirement is returned as a user-facing flash message so the user
knows exactly what to fix.

**Files changed:**
- `app.py` — `validate_password()` function added; called in `signup()`
  and `reset_password()`

---

## 4. Forgot Password with Email Delivery (Resend)

A complete forgot-password flow using signed tokens and real email
delivery via the Resend API.

**Flow:**
1. User visits `/forgot-password`, enters their email address
2. If an account with that email exists, a signed, time-limited token
   is generated using `itsdangerous.URLSafeTimedSerializer`
3. A password-reset email is sent via Resend containing a link to
   `/reset-password/<token>`
4. The user clicks the link, sets a new password (validated against
   the same `validate_password()` rules), and is redirected to login
5. Tokens expire after 30 minutes (`max_age=1800`)
6. The response to the forgot-password form is always the same message
   ("If an account exists with that email...") regardless of whether
   the email matched — this prevents user enumeration

**Security notes:**
- Tokens are signed with the app's `SECRET_KEY` — tampering with the
  token invalidates it
- The token contains only the user's id, not their email or password
- On successful reset, the session is cleared so the user must log in
  fresh with the new password

**New dependencies:**
- `resend` — email delivery SDK
- `itsdangerous` — already present (used for Flask sessions), now also
  used explicitly for reset tokens

**New environment variables:**
- `RESEND_API_KEY` — Resend account API key
- `RESEND_FROM_EMAIL` — sender address (defaults to
  `onboarding@resend.dev` for Resend's sandbox)

**Files changed:**
- `app.py` — `forgot_password()`, `reset_password()`,
  `send_password_reset_email()`, `get_reset_serializer()`,
  `generate_reset_token()`, `verify_reset_token()` all added
- `db.py` — `get_user_by_email()`, `update_user_password()` added;
  `users` table updated to include `email` column
- `templates/forgot_password.html` — new
- `templates/reset_password.html` — new
- `requirements.txt` — `resend` added

---

## 5. Inspired App Shell Layout

The biggest structural change of the week: replacing the top navigation
bar with a persistent left sidebar, matching the layout pattern used
by Pi.ai and similar conversational AI products.

**Before:** every page had a sticky frosted-glass top nav bar
(logo + links + user pill). The main content sat below it in a
centered column.

**After:** logged-in pages use an "app shell" layout:
- A fixed 280px left sidebar (`app-sidebar`) containing the brand,
  navigation links ("New Entry", "Archive"), a "Recents" section
  showing the 7 most recent entries for quick access, and a footer
  with the username, theme toggle, and logout
- The main content area (`app-main`) occupies the remaining
  `calc(100% - 280px)` of the viewport
- On mobile (≤ 900px), the sidebar collapses off-screen and is
  triggered by a hamburger button in a fixed mobile header bar; a
  semi-transparent overlay closes it on tap

**Why this matters:** the sidebar "Recents" section means users never
have to navigate to the Archive just to switch between recent entries
— their last 7 conversations are always one click away from anywhere
in the app. This is exactly how Pi.ai handles conversation history.

**New backend support:**
- `get_recent_entries(user_id, limit)` added to `db.py`
- `inject_sidebar_context()` context processor added to `app.py` to
  make `recent_entries` and `active_entry_id` available to every
  template automatically, without changing individual route functions

**Files changed:**
- `static/css/style.css` — full `.app-shell`, `.app-sidebar`,
  `.app-main`, `.mobile-app-header`, `.sidebar-overlay` block added,
  plus responsive overrides
- `templates/base.html` — complete rewrite from top-nav to sidebar
  shell; mobile header and overlay added
- `db.py` — `get_recent_entries()` added
- `app.py` — `inject_sidebar_context()` context processor added

---

## Files changed this week

```
modified:   app.py           — validate_password, forgot/reset password
                               routes, inject_sidebar_context
modified:   db.py             — email column, get_user_by_email,
                               update_user_password, get_recent_entries
modified:   static/css/style.css — Gilroy font, dark mode variables,
                               app shell layout, sidebar, mobile header
modified:   templates/base.html  — full sidebar shell rewrite
new file:   static/fonts/gilroy-light.woff2
new file:   static/fonts/gilroy-extrabold.woff2
new file:   templates/forgot_password.html
new file:   templates/reset_password.html
modified:   requirements.txt — resend added
```

---

## How to run (unchanged)

```
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS/Linux
python -m pip install -r requirements.txt
```

Set environment variables in `.env`:
```
GEMINI_API_KEY=your-gemini-key
SECRET_KEY=your-secret-key
RESEND_API_KEY=your-resend-key
RESEND_FROM_EMAIL=you@yourdomain.com
```

```
python app.py
```
