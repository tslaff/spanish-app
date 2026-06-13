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

## How the spaced repetition works

Each card sits in a Leitner box (1–5). Answer correctly and it moves up a box
and won't return for longer (1, 3, 7, 14, then 30 days). Miss it and it drops
back to box 1. The dashboard shows how many cards are due per lesson, and a
review session simply walks the due cards. Tune the schedule in
`app/srs.py` (`INTERVALS`).

## Optional: AI translation feedback

If you set `ANTHROPIC_API_KEY`, the sentence screen gains a "Check my
translation" box that asks Claude to evaluate your attempt and suggest more
natural phrasing. Without the key, sentences work as reveal-and-self-grade
cards. It uses a small, inexpensive model — fine for one learner.
