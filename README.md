# Español — a personal Spanish learning app

A tiny single-user web app for flashcards and sentence translation, with
spaced repetition. One FastAPI service, SQLite for progress, and your lessons
stored as YAML files you can edit and push. Designed to deploy to Railway and
work nicely from your phone.

## What's inside

| Path | What it is |
|------|------------|
| `app/main.py` | Routes (login, dashboard, flashcards, sentences) |
| `app/srs.py` | Leitner spaced-repetition logic |
| `app/db.py` | SQLite progress storage |
| `app/content.py` | Loads lessons from `content/*.yaml` |
| `app/modes.py` | Translation direction (ES↔EN) and per-direction progress |
| `app/grading.py` | Accent-insensitive checking of typed translations |
| `app/translate.py` | Optional Claude-powered translation feedback |
| `content/*.yaml` | Your vocabulary and sentences |

## Run it locally

```bash
cd spanish-app
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env        # then edit APP_PASSWORD and SECRET_KEY
set -a; source .env; set +a # load .env into your shell (macOS/Linux)

uvicorn app.main:app --reload
```

Open http://localhost:8000 and log in with your `APP_PASSWORD`.

## Deploy to Railway

1. Push this folder to a GitHub repo.
2. In Railway: **New Project -> Deploy from GitHub repo**. It auto-detects
   Python and uses the `Procfile` to start the app.
3. Add a **Volume** to the service and set its mount path to `/data`.
   This is what keeps your review progress across deploys.
4. Add these service **Variables**:
   - `APP_PASSWORD` — your login password
   - `SECRET_KEY` — a random string (`python -c "import secrets; print(secrets.token_hex(32))"`)
   - `DATA_DIR` — set to `/data` (matches the volume mount)
   - `ANTHROPIC_API_KEY` — optional, only to enable AI translation feedback
5. Open the generated URL on your phone and use **Add to Home Screen** so it
   behaves like an app.

## Adding lessons and vocab

Create a new file in `content/`, e.g. `lesson-03-travel.yaml`:

```yaml
id: travel
name: "Travel"
cards:
  - front: "el aeropuerto"
    back: "the airport"
  - front: "la maleta"
    back: "the suitcase"
    notes: "optional hint shown with the answer"
sentences:
  - es: "¿Dónde está la estación?"
    en: "Where is the station?"
```

Commit and push — Railway redeploys and the lesson appears. Progress is keyed
to each card's `front` text, so editing the back/notes keeps your history;
changing the front text starts that card fresh.

## Two directions: ES → EN and EN → ES

Every screen (dashboard, flashcards, sentences) has a toggle at the top to
switch between **Spanish → English** and **English → Spanish**. The toggle
flips which side is the prompt and which side you type:

- **ES → EN** — see the Spanish, type the English (recognition).
- **EN → ES** — see the English, type the Spanish (production).

Your choice is remembered for the session. Progress is tracked **separately per
direction** — recognising a word and producing it are different skills, so each
card has its own spaced-repetition schedule in each direction, and the "due"
counts on the dashboard reflect the direction you're currently in.

## Checking your answers

Both flashcards and sentences let you **type the translation and check it**.
You see the prompt (in whichever language the current direction shows) and type
the translation. Hit **Check** (or press Enter) and the app tells you whether
you're right, then reveals the expected answer and any notes.

The check **ignores accents and diacritics**, case, and surrounding
punctuation — so `buenos dias` matches `buenos días` and `Hello!` matches
`hello`. You can also list several acceptable answers in the lesson YAML by
separating them with `/`:

```yaml
cards:
  - front: "hola"
    back: "hi / hello"
```

The result feeds the spaced-repetition schedule automatically: a correct
answer moves the card up a box, a miss drops it back to box 1. Don't feel like
typing? Hit **Show answer** to reveal it (counted as a miss) and move on.

## How the spaced repetition works

Each card sits in a Leitner box (1–5). Answer correctly and it moves up a box
and won't return for longer (1, 3, 7, 14, then 30 days). Miss it and it drops
back to box 1. The dashboard shows how many cards are due per lesson, and a
review session simply walks the due cards. Tune the schedule in
`app/srs.py` (`INTERVALS`).

## Optional: AI translation feedback

The built-in answer check (above) is an exact, accent-insensitive match. If you
also set `ANTHROPIC_API_KEY`, the sentence result screen gains an **"Ask Claude
for feedback"** button that sends your attempt to Claude for a gentler,
free-form critique — handy for sentences where several phrasings are valid and
it can point out grammar or word-choice nuances. It uses a small, inexpensive
model — fine for one learner. Without the key, this button simply doesn't
appear and everything else works as normal.
