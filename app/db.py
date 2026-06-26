import os
import sqlite3
from datetime import date

from .config import settings


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    os.makedirs(settings.data_dir, exist_ok=True)
    conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS progress (
            card_id        TEXT PRIMARY KEY,
            box            INTEGER NOT NULL DEFAULT 1,
            next_due       TEXT    NOT NULL,
            last_reviewed  TEXT,
            correct_count  INTEGER NOT NULL DEFAULT 0,
            wrong_count    INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.commit()
    conn.close()


def progress_map() -> dict:
    """Return {card_id: row} for every card we've ever reviewed."""
    conn = get_conn()
    rows = conn.execute("SELECT * FROM progress").fetchall()
    conn.close()
    return {r["card_id"]: r for r in rows}


def get_progress(card_id: str):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM progress WHERE card_id = ?", (card_id,)
    ).fetchone()
    conn.close()
    return row


def complete_card(card_id: str, correct_count: int, box: int, next_due: str) -> None:
    """Mark a flip card done in one action (Knowledge Work's 'Completed').

    Sets correct_count straight to the mastery threshold so the card drops out
    of the queue, instead of needing several correct passes like a graded card.
    """
    today = date.today().isoformat()
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO progress (card_id, box, next_due, last_reviewed, correct_count, wrong_count)
        VALUES (?, ?, ?, ?, ?, 0)
        ON CONFLICT(card_id) DO UPDATE SET
            box = excluded.box,
            next_due = excluded.next_due,
            last_reviewed = excluded.last_reviewed,
            correct_count = excluded.correct_count
        """,
        (card_id, box, next_due, today, correct_count),
    )
    conn.commit()
    conn.close()


def record_review(card_id: str, box: int, next_due: str, correct: bool) -> None:
    conn = get_conn()
    existing = conn.execute(
        "SELECT correct_count, wrong_count FROM progress WHERE card_id = ?",
        (card_id,),
    ).fetchone()
    cc = existing["correct_count"] if existing else 0
    wc = existing["wrong_count"] if existing else 0
    if correct:
        cc += 1
    else:
        wc += 1
    today = date.today().isoformat()
    conn.execute(
        """
        INSERT INTO progress (card_id, box, next_due, last_reviewed, correct_count, wrong_count)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(card_id) DO UPDATE SET
            box = excluded.box,
            next_due = excluded.next_due,
            last_reviewed = excluded.last_reviewed,
            correct_count = excluded.correct_count,
            wrong_count = excluded.wrong_count
        """,
        (card_id, box, next_due, today, cc, wc),
    )
    conn.commit()
    conn.close()
