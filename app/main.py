import os
import random
from contextlib import asynccontextmanager

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from . import auth, content, db, grading, modes, srs, translate
from .config import settings

BASE_DIR = os.path.dirname(__file__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


def _redirect_if_anon(request: Request):
    if not auth.is_authenticated(request):
        return RedirectResponse("/login", status_code=303)
    return None


MASTERY_COUNT = 3


def _due(items: list[dict], pm: dict, direction: str) -> list[dict]:
    result = []
    for it in items:
        p = pm.get(modes.progress_id(it["id"], direction))
        if srs.is_due(p) and (p["correct_count"] if p else 0) < MASTERY_COUNT:
            result.append(it)
    return result


# ----- auth -----

@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login")
def login(request: Request, password: str = Form(...)):
    if auth.check_password(password):
        request.session["auth"] = True
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(
        "login.html", {"request": request, "error": "Wrong password."}, status_code=401
    )


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/direction/{value}")
def set_direction(request: Request, value: str, next: str = "/"):
    """Switch translation direction, then return to the page you were on."""
    if (r := _redirect_if_anon(request)) is not None:
        return r
    if value in modes.LABELS:
        request.session["direction"] = value
    target = next if next.startswith("/") else "/"  # only allow local redirects
    return RedirectResponse(target, status_code=303)


# ----- dashboard -----

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    if (r := _redirect_if_anon(request)) is not None:
        return r
    pm = db.progress_map()
    direction = modes.get_direction(request)
    decks = []
    for d in content.load_decks():
        decks.append(
            {
                "id": d["id"],
                "name": d["name"],
                "vocab_total": len(d["cards"]),
                "vocab_due": len(_due(d["cards"], pm, direction)),
                "sent_total": len(d["sentences"]),
                "sent_due": len(_due(d["sentences"], pm, direction)),
            }
        )
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "decks": decks, "direction": direction, "labels": modes.LABELS, "next": "/"},
    )


# ----- flashcard review -----

@app.get("/review/{deck_id}", response_class=HTMLResponse)
def review(request: Request, deck_id: str):
    if (r := _redirect_if_anon(request)) is not None:
        return r
    deck = content.get_deck(deck_id)
    if not deck:
        return RedirectResponse("/", status_code=303)
    direction = modes.get_direction(request)
    due = _due(deck["cards"], db.progress_map(), direction)
    random.shuffle(due)
    cards = [modes.card_view(c, direction) for c in due]
    return templates.TemplateResponse(
        "review.html",
        {
            "request": request,
            "deck": deck,
            "card": cards[0] if cards else None,
            "remaining": len(cards),
            "direction": direction,
            "labels": modes.LABELS,
            "next": f"/review/{deck['id']}",
        },
    )


@app.get("/review/{deck_id}/next", response_class=HTMLResponse)
def review_next(request: Request, deck_id: str):
    """Render the next due card (used by the 'Next' button after a check)."""
    if (r := _redirect_if_anon(request)) is not None:
        return r
    deck = content.get_deck(deck_id)
    if not deck:
        return RedirectResponse("/", status_code=303)
    direction = modes.get_direction(request)
    due = _due(deck["cards"], db.progress_map(), direction)
    random.shuffle(due)
    cards = [modes.card_view(c, direction) for c in due]
    return templates.TemplateResponse(
        "_review_inner.html",
        {"request": request, "deck": deck, "card": cards[0] if cards else None, "remaining": len(cards)},
    )


@app.post("/review/{deck_id}/check", response_class=HTMLResponse)
def review_check(
    request: Request,
    deck_id: str,
    card_id: str = Form(...),
    attempt: str = Form(""),
    reveal: str = Form(""),
):
    """Check a typed translation, grade the card, and show the result."""
    if (r := _redirect_if_anon(request)) is not None:
        return r
    deck = content.get_deck(deck_id)
    raw = next((c for c in deck["cards"] if c["id"] == card_id), None) if deck else None
    if not raw:
        return RedirectResponse("/", status_code=303)

    direction = modes.get_direction(request)
    card = modes.card_view(raw, direction)
    pid = modes.progress_id(card_id, direction)

    prog = db.get_progress(pid)
    correct_count_before = prog["correct_count"] if prog else 0
    is_correct = False if reveal == "1" else grading.check_answer(attempt, card["answer"])
    box, next_due = srs.next_state(prog, is_correct)
    db.record_review(pid, box, next_due, is_correct)
    mastered = is_correct and correct_count_before + 1 >= MASTERY_COUNT

    due = _due(deck["cards"], db.progress_map(), direction)
    return templates.TemplateResponse(
        "_review_result.html",
        {
            "request": request,
            "deck": deck,
            "card": card,
            "correct": is_correct,
            "attempt": attempt,
            "remaining": len(due),
            "mastered": mastered,
        },
    )


# ----- sentence practice -----

@app.get("/sentences/{deck_id}", response_class=HTMLResponse)
def sentences(request: Request, deck_id: str):
    if (r := _redirect_if_anon(request)) is not None:
        return r
    deck = content.get_deck(deck_id)
    if not deck:
        return RedirectResponse("/", status_code=303)
    direction = modes.get_direction(request)
    due = _due(deck["sentences"], db.progress_map(), direction)
    random.shuffle(due)
    items = [modes.sentence_view(s, direction) for s in due]
    return templates.TemplateResponse(
        "sentences.html",
        {
            "request": request,
            "deck": deck,
            "item": items[0] if items else None,
            "remaining": len(items),
            "claude_enabled": settings.claude_enabled,
            "direction": direction,
            "labels": modes.LABELS,
            "next": f"/sentences/{deck['id']}",
        },
    )


@app.get("/sentences/{deck_id}/next", response_class=HTMLResponse)
def sentences_next(request: Request, deck_id: str):
    """Render the next due sentence (used by the 'Next' button after a check)."""
    if (r := _redirect_if_anon(request)) is not None:
        return r
    deck = content.get_deck(deck_id)
    if not deck:
        return RedirectResponse("/", status_code=303)
    direction = modes.get_direction(request)
    due = _due(deck["sentences"], db.progress_map(), direction)
    random.shuffle(due)
    items = [modes.sentence_view(s, direction) for s in due]
    return templates.TemplateResponse(
        "_sentence_inner.html",
        {
            "request": request,
            "deck": deck,
            "item": items[0] if items else None,
            "remaining": len(items),
            "claude_enabled": settings.claude_enabled,
        },
    )


@app.post("/sentences/{deck_id}/check", response_class=HTMLResponse)
def sentences_check(
    request: Request,
    deck_id: str,
    item_id: str = Form(...),
    attempt: str = Form(""),
    reveal: str = Form(""),
):
    """Check a typed sentence translation, grade it, and show the result."""
    if (r := _redirect_if_anon(request)) is not None:
        return r
    deck = content.get_deck(deck_id)
    raw = next((s for s in deck["sentences"] if s["id"] == item_id), None) if deck else None
    if not raw:
        return RedirectResponse("/", status_code=303)

    direction = modes.get_direction(request)
    item = modes.sentence_view(raw, direction)
    pid = modes.progress_id(item_id, direction)

    prog = db.get_progress(pid)
    correct_count_before = prog["correct_count"] if prog else 0
    is_correct = False if reveal == "1" else grading.check_answer(attempt, item["answer"])
    box, next_due = srs.next_state(prog, is_correct)
    db.record_review(pid, box, next_due, is_correct)
    mastered = is_correct and correct_count_before + 1 >= MASTERY_COUNT

    due = _due(deck["sentences"], db.progress_map(), direction)
    return templates.TemplateResponse(
        "_sentence_result.html",
        {
            "request": request,
            "deck": deck,
            "item": item,
            "correct": is_correct,
            "attempt": attempt,
            "remaining": len(due),
            "claude_enabled": settings.claude_enabled,
            "direction": direction,
            "mastered": mastered,
        },
    )


@app.post("/sentences/{deck_id}/feedback", response_class=HTMLResponse)
async def sentences_feedback(request: Request, deck_id: str, item_id: str = Form(...), attempt: str = Form("")):
    """Optional richer feedback from Claude on a sentence translation."""
    if (r := _redirect_if_anon(request)) is not None:
        return r
    deck = content.get_deck(deck_id)
    item = next((s for s in deck["sentences"] if s["id"] == item_id), None) if deck else None
    if not item:
        return HTMLResponse("")
    direction = modes.get_direction(request)
    feedback = await translate.grade_translation(item["es"], item["en"], attempt, direction)
    return templates.TemplateResponse(
        "_feedback.html", {"request": request, "feedback": feedback or ""}
    )
