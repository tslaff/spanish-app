import glob
import os
import re

import yaml

from .config import settings


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:40] or "item"


def _card_id(deck_id: str, kind: str, item: dict, key_field: str) -> str:
    raw = item.get("id") or slugify(str(item[key_field]))
    return f"{deck_id}::{kind}::{raw}"


def load_decks(subdir: str = "spanish") -> list[dict]:
    """Read every *.yaml / *.yml file in a content subdirectory into a deck list.

    Each domain keeps its lessons in its own subdirectory (content/spanish,
    content/knowledge, …). Reloaded on each request, so editing a file (and
    redeploying) updates content with no database migration. Card identities are
    derived from their text, so progress sticks to a card as long as its front
    text is unchanged.
    """
    base = os.path.join(settings.content_dir, subdir)
    paths = sorted(
        glob.glob(os.path.join(base, "*.yaml"))
        + glob.glob(os.path.join(base, "*.yml"))
    )
    decks = []
    for path in paths:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        base = os.path.splitext(os.path.basename(path))[0]
        deck_id = data.get("id") or slugify(base)

        cards = []
        for c in data.get("cards", []) or []:
            cards.append(
                {
                    "id": _card_id(deck_id, "vocab", c, "front"),
                    "front": c["front"],
                    "back": c["back"],
                    "notes": c.get("notes", ""),
                }
            )

        sentences = []
        for s in data.get("sentences", []) or []:
            sentences.append(
                {
                    "id": _card_id(deck_id, "sent", s, "es"),
                    "es": s["es"],
                    "en": s["en"],
                    "notes": s.get("notes", ""),
                }
            )

        decks.append(
            {
                "id": deck_id,
                "name": data.get("name", deck_id),
                "cards": cards,
                "sentences": sentences,
            }
        )
    return decks


def get_deck(deck_id: str, subdir: str = "spanish") -> dict | None:
    for d in load_decks(subdir):
        if d["id"] == deck_id:
            return d
    return None
