from datetime import date, timedelta

# Leitner boxes: each level waits longer before the card comes back.
INTERVALS = {1: 1, 2: 3, 3: 7, 4: 14, 5: 30}  # box -> days until next review
MAX_BOX = 5


def is_due(progress, today: date | None = None) -> bool:
    """A card is due if we've never seen it, or its next_due date has arrived."""
    today = today or date.today()
    if progress is None:
        return True
    return progress["next_due"] <= today.isoformat()


def next_state(progress, correct: bool, today: date | None = None):
    """Given current progress and whether the answer was right, return (box, next_due)."""
    today = today or date.today()
    box = progress["box"] if progress is not None else 1
    if correct:
        box = min(box + 1, MAX_BOX)
    else:
        box = 1  # missed cards drop all the way back
    next_due = (today + timedelta(days=INTERVALS[box])).isoformat()
    return box, next_due
