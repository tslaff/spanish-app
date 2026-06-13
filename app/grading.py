import re
import unicodedata


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


def check_answer(attempt: str, expected: str) -> bool:
    """True if the attempt matches the expected translation, accent-insensitively.

    The expected text may list several acceptable answers separated by "/"
    (e.g. "hi / hello"); any one of them counts as correct.
    """
    if not attempt or not attempt.strip():
        return False
    norm_attempt = normalize(attempt)
    return any(
        norm_attempt == normalize(option)
        for option in expected.split("/")
        if option.strip()
    )
