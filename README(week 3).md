# Journelle — Week 3: Chat-First UX & Visual Redesign

## What changed this week

Week 3 was focused entirely on the user experience — how the app
*feels* to use, not just what it does. The backend (Flask, SQLite,
Gemini, multi-user accounts, persistence, error handling) remained
unchanged from Weeks 1 and 2. Everything this week touched the
interface, the interaction model, and a real AI reliability bug.

---

## 1. Chat-First Landing Page

**Before:** logging in took you to a combined page with a textarea
form ("write your entry here") and a list of past entries below it.
Writing an entry and chatting about it were two separate steps.

**After:** logging in drops you directly into a live conversation.
The landing page (`/`) shows a single AI chat bubble — "What's on
your mind today?" — with a message input bar below it. Whatever you
type becomes that day's journal entry. The AI's reply is the opening
reflection. From that point on, it's one continuous chat thread, not
a form-then-chat sequence.

**Why:** the old flow asked users to mentally switch between "writing
mode" (the textarea) and "conversation mode" (the chat below). Folding
them into one step removes that friction and makes the experience feel
more natural and immediate — closer to opening a messaging app than
filling out a form.

**Route changes:**
- `/` → renamed from "home with form" to "chat starter" (`new_entry.html`)
- `/start_chat` (POST) → new route; saves the first message as the entry content, generates the opening reflection, redirects into the conversation
- `/save` → removed entirely; replaced by `/start_chat`
- `/archive` → new dedicated route for browsing past entries (previously combined with the home page)

---

## 2. Real Chat-Bubble UI

**Before:** conversations rendered as stacked white "document" cards
with uppercase role labels ("YOU", "AI COMPANION"), heavy padding,
and full-width layout — visually more like a report than a chat.

**After:** real WhatsApp/iMessage-style message bubbles:
- User messages align **right**, solid purple (`#6B63FF`)
- AI messages align **left**, soft lavender (`#E4E0FF`)
- Bubbles use `width: fit-content` — they size tightly to their text
  content rather than stretching to fill available space
- `max-width: 60%` caps longer messages so they don't span the full
  page width
- `white-space: pre-wrap` with no internal HTML indentation — prevents
  leading spaces from appearing inside bubbles
- A single rounded pill-shaped input bar at the bottom, with the Send
  button inline, matching modern messaging app conventions

**CSS classes added/replaced:**
- `.chat-thread` — flex column container for the whole conversation
- `.chat-bubble.user` / `.chat-bubble.ai` — the actual bubble elements
- `.chat-input-form` — the pill-shaped input bar
- Old classes removed: `.conversation-section`, `.conversation-list`,
  `.conversation-message`, `.message-role`, `.message-content`,
  `.reply-form`, `.entry-paper`, `.reflection-card`, `.journal-body`

---

## 3. Lovable-Inspired Visual Redesign

The entire visual design was reworked, inspired by a Lovable-generated
mockup, hand-ported into the existing Flask/Jinja templates rather than
rebuilding the app on a different stack.

**Design system (`static/css/style.css`):**

| Token | Value | Used for |
|---|---|---|
| `--background` | `#F8F7F4` | Page background (warm off-white) |
| `--card` | `#FFFFFF` | Cards, input backgrounds |
| `--card-soft` | `#F4F2FF` | Soft lavender — AI bubble base |
| `--primary` | `#6B63FF` | Buttons, links, user bubbles, accents |
| `--primary-dark` | `#564EEA` | Button hover state |
| `--text` | `#222437` | Main body text |
| `--muted` | `#7D8195` | Secondary text, timestamps, labels |
| `--border` | `#E9E5DD` | All borders and dividers |

**Typography:**
- `Fraunces` (serif, weights 500/600/700) — headings, logo, archive titles
- `Inter` (sans-serif, weights 300–700) — all body text, UI labels, inputs

**Nav redesign:**
- Sticky frosted-glass pill nav (backdrop-filter blur, semi-transparent background)
- Logo icon: gradient purple square with rounded corners, "J" in Fraunces
- Logo is now a clickable link back to `/` (the chat starter)
- Nav links: "New Entry", "Archive", username pill, "Logout"
- Previously: flat nav bar with minimal styling

**Archive cards:**
- Each entry is a white rounded card with a colored dot (cycling through 5 colors), entry title, timestamp, preview text, and an "Open →" link
- Hover: lifts slightly with a deeper shadow (`translateY(-4px)`)
- Previously: a plain `<ul>` list with simple link styling

**Auth pages:**
- Centered white card on the warm background
- Badge label ("✦ Welcome Back"), large Fraunces heading, muted subtitle
- Full-width pill button matching the app's primary color

---

## 4. Mobile Responsiveness

The app was not previously tested or optimized for mobile. A full
`@media` query block was added targeting screens ≤ 768px (and a
secondary block for ≤ 400px), covering:

| Element | Desktop | Mobile fix |
|---|---|---|
| Nav | Single row, logo + links side by side | Logo on top row, links wrap to second row with a border separator |
| Nav logo icon | 52×52px | 40×40px |
| Hero h1 | `4rem` | `2.4rem` (→ `2rem` at 400px) |
| Chat bubbles | `max-width: 60%` | `max-width: 82%` (→ `88%` at 400px) |
| Archive cards | Side-by-side left/right layout | Stacked vertically, date and "Open →" on same row at bottom |
| Auth card | `50px` padding | `32px 24px` padding, smaller border-radius |
| Secondary button | Inline | Full-width on mobile |
| Page padding | `40px 0` | `16px 16px 60px` |

Tested on a real iPhone via `harnoor1207.pythonanywhere.com` and
confirmed working across all pages.

---

## 5. Hallucination Guard

**Bug discovered:** when a user typed a very short or vague message
(e.g. "hi"), the AI would generate a reflection inventing specific,
confident-sounding details that were never mentioned — people, events,
emotional scenarios — because the system prompt instructed it to "be
specific" but gave it almost no real content to work with.

**Root cause:** a low-content prompt + a "be specific" instruction is
a known LLM failure mode — the model satisfies the specificity demand
by fabricating a plausible-sounding scenario rather than honestly
acknowledging there's nothing concrete to reflect on.

**Why it matters:** in a journaling context, a reflection that
confidently references "your sister" or "the argument at work" when
the user said nothing of the sort is actively unsettling and could
undermine trust in the app.

**Fix:** updated `SYSTEM_PROMPT` in `reflection.py` to explicitly
instruct the model:
- Only be specific about details the user *actually wrote*
- Never invent people, events, or specifics not mentioned
- If the entry is very short or vague, warmly invite the user to share
  more rather than fabricating a scenario

**Verified:** typing "hi" now produces an inviting response ("What's
on your mind? I'd love to hear more") rather than a fabricated,
oddly-specific scenario.

---

## 6. Navigation Fixes

- Logo now links to `/` from every page
- "New Entry" nav link added — lets users start a fresh conversation
  from anywhere in the app (Archive, an ended entry, etc.)
- All internal `url_for("index")` references in error-redirect paths
  updated to `url_for("archive")` where appropriate
- Back link on entry page corrected to point to `/archive` instead of
  the old `/` (which no longer shows the entries list)

---

## Files changed this week

```
modified:   app.py                        — new /start_chat + /archive routes,
                                            removed /save, nav redirect fixes
modified:   static/css/style.css          — full design system rewrite +
                                            mobile responsive block
modified:   templates/base.html           — new nav design, logo link,
                                            New Entry + Archive links
modified:   templates/entry.html          — replaced document cards with
                                            chat-bubble thread
modified:   reflection.py                 — hallucination guard in SYSTEM_PROMPT
new file:   templates/new_entry.html      — chat-starter landing page
new file:   templates/archive.html        — dedicated past entries page
                                            (renamed + stripped from index.html)
deleted:    templates/index.html          — split into new_entry.html + archive.html
```

---

## How to run (unchanged from Week 1)

```
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS/Linux
python -m pip install -r requirements.txt
```

Create `.env` with your Gemini key:
```
GEMINI_API_KEY=your-real-key-here
```

Run:
```
python app.py
```

Live site: http://harnoor1207.pythonanywhere.com
