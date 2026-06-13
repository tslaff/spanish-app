import httpx

from .config import settings

# Cheap, fast model — fine for grading one learner's sentences.
MODEL = "claude-haiku-4-5-20251001"


async def grade_translation(
    spanish: str, english: str, attempt: str, direction: str = "es2en"
) -> str | None:
    """Ask Claude to gently evaluate the learner's translation.

    `direction` is "es2en" (they translated the Spanish into English) or
    "en2es" (they translated the English into Spanish), which decides which
    sentence is the prompt and which language their attempt should be in.
    Returns feedback text, or None if no API key is configured.
    """
    if not settings.claude_enabled:
        return None

    if not attempt.strip():
        return "Type your translation first, then check it."

    if direction == "en2es":
        source, source_text, reference, target_lang = "English", english, spanish, "Spanish"
    else:
        source, source_text, reference, target_lang = "Spanish", spanish, english, "English"

    prompt = (
        "You are a patient Spanish tutor. Evaluate a learner's translation.\n\n"
        f"{source} sentence: {source_text}\n"
        f"A reference {target_lang} translation: {reference}\n"
        f"The learner wrote (in {target_lang}): {attempt}\n\n"
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
