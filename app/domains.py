"""Study domains: the app can serve more than one subject.

A domain bundles together where its content lives, how it looks, and how its
cards behave. The chosen domain lives in the session (like translation
direction), so the same login can switch between, say, Spanish and Knowledge
Work without separate accounts.

kind:
  "translate" — typed answers graded against a target, with a direction toggle
                 and an optional sentence-practice section (the Spanish app).
  "flip"      — plain front/back flashcards you self-assess with
                 Completed / Check back / Skip (Knowledge Work).
"""

from fastapi import Request

DOMAINS: dict[str, dict] = {
    "spanish": {
        "id": "spanish",
        "name": "Spanish",
        "brand": "Español",
        "subdir": "spanish",
        "stylesheet": "style.css",
        "theme_color": "#7c3aed",
        "kind": "translate",
    },
    "knowledge": {
        "id": "knowledge",
        "name": "Knowledge Work",
        "brand": "Knowledge Work",
        "subdir": "knowledge",
        "stylesheet": "knowledge.css",
        "theme_color": "#1e3a8a",
        "kind": "flip",
    },
}

DEFAULT = "spanish"


def current(request: Request) -> dict:
    """The domain selected in this session (falls back to the default)."""
    return DOMAINS.get(request.session.get("domain", DEFAULT), DOMAINS[DEFAULT])
