import re
import unicodedata
from difflib import SequenceMatcher

_ARTICLES = re.compile(
    r"^(the|a|an|el|la|los|las|un|una|unos|unas)\s+", re.IGNORECASE
)

FUZZY_THRESHOLD = 0.90


def normalize(text: str) -> str:
    """Fold a translation down to its comparable core.

    Lowercases, strips accents/diacritics (so "cafe" matches "café"), drops
    surrounding punctuation, and collapses whitespace. This is what makes the
    answer check forgiving about accents and small typing differences.
    """
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower().strip()
    text = re.sub(r"[¿?¡!.,;:\"'()]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _strip_article(text: str) -> str:
    return _ARTICLES.sub("", text).strip()


def _matches(attempt: str, option: str) -> bool:
    norm_a = normalize(attempt)
    norm_o = normalize(option)
    if norm_a == norm_o:
        return True
    # Allow leading articles to differ on either side
    if _strip_article(norm_a) == _strip_article(norm_o):
        return True
    # Fuzzy match for phrases (90%+ similarity)
    ratio = SequenceMatcher(None, norm_a, norm_o).ratio()
    return ratio >= FUZZY_THRESHOLD


def check_answer(attempt: str, expected: str) -> bool:
    """True if the attempt matches the expected translation, accent-insensitively.

    The expected text may list several acceptable answers separated by "/"
    (e.g. "hi / hello"); any one of them counts as correct.
    Accepts answers that differ only by a leading article ("the"/"a"/"el"/etc.)
    or that are >=90% similar to any accepted option.
    """
    if not attempt or not attempt.strip():
        return False
    return any(
        _matches(attempt, option)
        for option in expected.split("/")
        if option.strip()
    )
