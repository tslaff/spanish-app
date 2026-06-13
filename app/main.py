import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from . import auth, content, db, srs, translate
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


def _due(items: list[dict], pm: dict) -> list[dict]:
    return [it for it in items if srs.is_due(pm.get(it["id"]))]


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


# ----- dashboard -----

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    if (r := _redirect_if_anon(request)) is not None:
        return r
    pm = db.progress_map()
    decks = []
    for d in content.load_decks():
        decks.append(
            {
                "id": d["id"],
                "name": d["name"],
                "vocab_total": len(d["cards"]),
                "vocab_due": len(_due(d["cards"], pm)),
                "sent_total": len(d["sentences"]),
                "sent_due": len(_due(d["sentences"], pm)),
            }
        )
    return templates.TemplateResponse("index.html", {"request": request, "decks": decks})


# ----- flashcard review -----

@app.get("/review/{deck_id}", response_class=HTMLResponse)
def review(request: Request, deck_id: str):
    if (r := _redirect_if_anon(request)) is not None:
        return r
    deck = content.get_deck(deck_id)
    if not deck:
        return RedirectResponse("/", status_code=303)
    due = _due(deck["cards"], db.progress_map())
    return templates.TemplateResponse(
        "review.html",
        {"request": request, "deck": deck, "card": due[0] if due else None, "remaining": len(due)},
    )


@app.post("/review/{deck_id}/grade", response_class=HTMLResponse)
def review_grade(request: Request, deck_id: str, card_id: str = Form(...), correct: str = Form(...)):
    if (r := _redirect_if_anon(request)) is not None:
        return r
    is_correct = correct == "1"
    box, next_due = srs.next_state(db.get_progress(card_id), is_correct)
    db.record_review(card_id, box, next_due, is_correct)

    deck = content.get_deck(deck_id)
    due = _due(deck["cards"], db.progress_map())
    return templates.TemplateResponse(
        "_review_inner.html",
        {"request": request, "deck": deck, "card": due[0] if due else None, "remaining": len(due)},
    )


# ----- sentence practice -----

@app.get("/sentences/{deck_id}", response_class=HTMLResponse)
def sentences(request: Request, deck_id: str):
    if (r := _redirect_if_anon(request)) is not None:
        return r
    deck = content.get_deck(deck_id)
    if not deck:
        return RedirectResponse("/", status_code=303)
    due = _due(deck["sentences"], db.progress_map())
    return templates.TemplateResponse(
        "sentences.html",
        {
            "request": request,
            "deck": deck,
            "item": due[0] if due else None,
            "remaining": len(due),
            "claude_enabled": settings.claude_enabled,
        },
    )


@app.post("/sentences/{deck_id}/grade", response_class=HTMLResponse)
def sentences_grade(request: Request, deck_id: str, item_id: str = Form(...), correct: str = Form(...)):
    if (r := _redirect_if_anon(request)) is not None:
        return r
    is_correct = correct == "1"
    box, next_due = srs.next_state(db.get_progress(item_id), is_correct)
    db.record_review(item_id, box, next_due, is_correct)

    deck = content.get_deck(deck_id)
    due = _due(deck["sentences"], db.progress_map())
    return templates.TemplateResponse(
        "_sentence_inner.html",
        {
            "request": request,
            "deck": deck,
            "item": due[0] if due else None,
            "remaining": len(due),
            "claude_enabled": settings.claude_enabled,
        },
    )


@app.post("/sentences/{deck_id}/check", response_class=HTMLResponse)
async def sentences_check(request: Request, deck_id: str, item_id: str = Form(...), attempt: str = Form("")):
    if (r := _redirect_if_anon(request)) is not None:
        return r
    deck = content.get_deck(deck_id)
    item = next((s for s in deck["sentences"] if s["id"] == item_id), None) if deck else None
    if not item:
        return HTMLResponse("")
    feedback = await translate.grade_translation(item["es"], item["en"], attempt)
    return templates.TemplateResponse(
        "_feedback.html", {"request": request, "feedback": feedback or ""}
    )
