import os
import random
from contextlib import asynccontextmanager
from datetime import date, timedelta

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from . import auth, content, db, domains, grading, modes, srs, translate
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
# Make the domain registry available to every template (base.html reads it to
# pick the stylesheet, brand and the domain switcher).
templates.env.globals["domains"] = domains


def _redirect_if_anon(request: Request):
    if not auth.is_authenticated(request):
        return RedirectResponse("/login", status_code=303)
    return None


MASTERY_COUNT = 3


def _subdir(request: Request) -> str:
    return domains.current(request)["subdir"]


def _due(items: list[dict], pm: dict, direction: str) -> list[dict]:
    result = []
    for it in items:
        p = pm.get(modes.progress_id(it["id"], direction))
        if srs.is_due(p) and (p["correct_count"] if p else 0) < MASTERY_COUNT:
            result.append(it)
    return result


def _kw_due_cards(deck: dict, pm: dict) -> list[dict]:
    """Flip cards still to review: not yet completed. No direction, bare id."""
    result = []
    for c in deck["cards"]:
        p = pm.get(c["id"])
        if (p["correct_count"] if p else 0) < MASTERY_COUNT:
            result.append(c)
    return result


def _kw_pick(deck: dict, exclude: str | None = None) -> tuple[dict | None, int]:
    """Pick the next due flip card (random, avoiding an immediate repeat)."""
    due = _kw_due_cards(deck, db.progress_map())
    pool = [c for c in due if c["id"] != exclude] if exclude else due
    if not pool:
        pool = due  # only the excluded card is left — show it again rather than nothing
    return (random.choice(pool) if pool else None), len(due)


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


@app.get("/domain/{value}")
def set_domain(request: Request, value: str):
    """Switch study domain (Spanish vs Knowledge Work), then go to the dashboard."""
    if (r := _redirect_if_anon(request)) is not None:
        return r
    if value in domains.DOMAINS:
        request.session["domain"] = value
    return RedirectResponse("/", status_code=303)


# ----- dashboard -----

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    if (r := _redirect_if_anon(request)) is not None:
        return r
    pm = db.progress_map()
    dom = domains.current(request)

    if dom["kind"] == "flip":
        decks = []
        for d in content.load_decks(dom["subdir"]):
            decks.append(
                {
                    "id": d["id"],
                    "name": d["name"],
                    "total": len(d["cards"]),
                    "due": len(_kw_due_cards(d, pm)),
                }
            )
        return templates.TemplateResponse(
            "knowledge_index.html", {"request": request, "decks": decks}
        )

    direction = modes.get_direction(request)
    decks = []
    for d in content.load_decks(dom["subdir"]):
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
    deck = content.get_deck(deck_id, _subdir(request))
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
    deck = content.get_deck(deck_id, _subdir(request))
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
    deck = content.get_deck(deck_id, _subdir(request))
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
    deck = content.get_deck(deck_id, _subdir(request))
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
    deck = content.get_deck(deck_id, _subdir(request))
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
    deck = content.get_deck(deck_id, _subdir(request))
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
    deck = content.get_deck(deck_id, _subdir(request))
    item = next((s for s in deck["sentences"] if s["id"] == item_id), None) if deck else None
    if not item:
        return HTMLResponse("")
    direction = modes.get_direction(request)
    feedback = await translate.grade_translation(item["es"], item["en"], attempt, direction)
    return templates.TemplateResponse(
        "_feedback.html", {"request": request, "feedback": feedback or ""}
    )


# ----- knowledge work (flip cards) -----

@app.get("/k/{deck_id}", response_class=HTMLResponse)
def kw_review(request: Request, deck_id: str):
    if (r := _redirect_if_anon(request)) is not None:
        return r
    deck = content.get_deck(deck_id, "knowledge")
    if not deck:
        return RedirectResponse("/", status_code=303)
    card, remaining = _kw_pick(deck)
    return templates.TemplateResponse(
        "knowledge_review.html",
        {"request": request, "deck": deck, "card": card, "remaining": remaining},
    )


@app.get("/k/{deck_id}/next", response_class=HTMLResponse)
def kw_next(request: Request, deck_id: str, exclude: str = ""):
    """Next due card's front — used by Skip and after Completed."""
    if (r := _redirect_if_anon(request)) is not None:
        return r
    deck = content.get_deck(deck_id, "knowledge")
    if not deck:
        return RedirectResponse("/", status_code=303)
    card, remaining = _kw_pick(deck, exclude or None)
    return templates.TemplateResponse(
        "_kw_front.html",
        {"request": request, "deck": deck, "card": card, "remaining": remaining},
    )


@app.get("/k/{deck_id}/back", response_class=HTMLResponse)
def kw_back(request: Request, deck_id: str, card_id: str):
    """Reveal the back of a card ('Check back'). The card stays in the queue."""
    if (r := _redirect_if_anon(request)) is not None:
        return r
    deck = content.get_deck(deck_id, "knowledge")
    card = next((c for c in deck["cards"] if c["id"] == card_id), None) if deck else None
    if not card:
        return RedirectResponse("/", status_code=303)
    remaining = len(_kw_due_cards(deck, db.progress_map()))
    return templates.TemplateResponse(
        "_kw_back.html",
        {"request": request, "deck": deck, "card": card, "remaining": remaining},
    )


@app.post("/k/{deck_id}/complete", response_class=HTMLResponse)
def kw_complete(request: Request, deck_id: str, card_id: str = Form(...)):
    """Mark a card completed (it leaves the queue) and show the next one."""
    if (r := _redirect_if_anon(request)) is not None:
        return r
    deck = content.get_deck(deck_id, "knowledge")
    if not deck:
        return RedirectResponse("/", status_code=303)
    next_due = (date.today() + timedelta(days=srs.INTERVALS[srs.MAX_BOX])).isoformat()
    db.complete_card(card_id, MASTERY_COUNT, srs.MAX_BOX, next_due)
    card, remaining = _kw_pick(deck, card_id)
    return templates.TemplateResponse(
        "_kw_front.html",
        {"request": request, "deck": deck, "card": card, "remaining": remaining},
    )
