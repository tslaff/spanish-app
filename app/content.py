import glob
import logging
import os
import re

import yaml

from .config import settings

logger = logging.getLogger(__name__)


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:40] or "item"


def _card_id(deck_id: str, kind: str, item: dict, key_field: str) -> str:
    raw = item.get("id") or slugify(str(item[key_field]))
    return f"{deck_id}::{kind}::{raw}"


def load_decks(subdir: str = "spanish") -> list[dict]:
    """Read every *.yaml / *.yml file in a content subdirectory into a deck list.

    Each domain keeps its lessons in its own subdirectory (content/spanish,
    content/knowledge, …). Files may be nested in subdirectories; the
    immediate subfolder name (relative to the domain directory) is used as
    the deck's "category" for dashboard grouping.
    """
    base = os.path.join(settings.content_dir, subdir)
    paths = sorted(
        glob.glob(os.path.join(base, "**/*.yaml"), recursive=True)
        + glob.glob(os.path.join(base, "**/*.yml"), recursive=True)
    )
    decks = []
    for path in paths:
        try:
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except yaml.YAMLError as exc:
            logger.warning("Skipping %s: invalid YAML (%s)", path, exc)
            continue

        if not isinstance(data, dict):
            logger.warning("Skipping %s: top level must be a mapping", path)
            continue

        rel = os.path.relpath(path, base)
        parts = rel.split(os.sep)
        category = parts[0] if len(parts) > 1 else None

        stem = os.path.splitext(os.path.basename(path))[0]
        deck_id = str(data.get("id") or slugify(stem))

        cards = []
        for c in data.get("cards", []) or []:
            if not isinstance(c, dict) or not c.get("front") or not c.get("back"):
                logger.warning(
                    "Skipping card in %s: needs both 'front' and 'back' (got %r)", path, c
                )
                continue
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
            if not isinstance(s, dict) or not s.get("es") or not s.get("en"):
                logger.warning(
                    "Skipping sentence in %s: needs both 'es' and 'en' (got %r)", path, s
                )
                continue
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
                "name": str(data.get("name", deck_id)),
                "category": category,
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
