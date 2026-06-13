import httpx

from .config import settings

# Cheap, fast model — fine for grading one learner's sentences.
MODEL = "claude-haiku-4-5-20251001"


async def grade_translation(spanish: str, reference_en: str, attempt: str) -> str | None:
    """Ask Claude to gently evaluate the learner's translation.

    Returns feedback text, or None if no API key is configured.
    """
    if not settings.claude_enabled:
        return None

    if not attempt.strip():
        return "Type your translation first, then check it."

    prompt = (
        "You are a patient Spanish tutor. Evaluate a learner's translation.\n\n"
        f"Spanish sentence: {spanish}\n"
        f"A reference English translation: {reference_en}\n"
        f"The learner wrote: {attempt}\n\n"
        "In 2-3 short sentences: say whether their translation is essentially correct, "
        "then point out any grammar or word-choice issues and suggest a more natural "
        "phrasing if useful. Be encouraging. Do not just repeat the reference."
    )

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": settings.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": MODEL,
                    "max_tokens": 400,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
        resp.raise_for_status()
        data = resp.json()
        return "".join(
            block.get("text", "")
            for block in data.get("content", [])
            if block.get("type") == "text"
        ).strip() or "(No feedback returned.)"
    except Exception as exc:  # keep the app usable even if the API call fails
        return f"Couldn't reach the grading service: {exc}"
