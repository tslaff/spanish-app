"""Translation direction: Spanish→English vs English→Spanish.

The chosen direction lives in the session. Progress is tracked separately per
direction (recognising a word and producing it are different skills), so each
card has its own Leitner box in each direction. To stay backward-compatible
with progress recorded before this feature existed, the default es2en direction
keeps using the card's bare id while en2es gets a suffixed key.
"""

from fastapi import Request

LABELS = {"es2en": "ES → EN", "en2es": "EN → ES"}
DEFAULT = "es2en"


def get_direction(request: Request) -> str:
    d = request.session.get("direction", DEFAULT)
    return d if d in LABELS else DEFAULT


def progress_id(card_id: str, direction: str) -> str:
    """The db key for a card in a given direction (es2en stays on the bare id)."""
    return card_id if direction == DEFAULT else f"{card_id}::{direction}"


def card_view(card: dict, direction: str) -> dict:
    """A vocab card oriented for the current direction (prompt vs answer)."""
    if direction == "en2es":
        prompt, answer = card["back"], card["front"]
    else:
        prompt, answer = card["front"], card["back"]
    return {
        "id": card["id"],
        "prompt": prompt,
        "answer": answer,
        "notes": card["notes"],
    }


def sentence_view(item: dict, direction: str) -> dict:
    """A sentence oriented for the current direction (prompt vs answer)."""
    if direction == "en2es":
        prompt, answer = item["en"], item["es"]
    else:
        prompt, answer = item["es"], item["en"]
    return {
        "id": item["id"],
        "prompt": prompt,
        "answer": answer,
        "notes": item["notes"],
    }
