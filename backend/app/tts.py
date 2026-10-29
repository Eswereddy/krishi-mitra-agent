"""Server-side text-to-speech fallback.

Many laptops and some phones have no Telugu (or Hindi) voice for the browser's speech synthesis.
When that happens the frontend asks this endpoint for an MP3 instead, so the agent can always talk.
Uses gTTS (Google Translate voice); results are cached in memory.
"""
import io
from functools import lru_cache

LANGS = {"te": ("te", "com"), "hi": ("hi", "co.in"), "en": ("en", "co.in")}
MAX_CHARS = 1200


@lru_cache(maxsize=64)
def synthesize(text: str, lang: str) -> bytes:
    from gtts import gTTS  # imported lazily so the rest of the app runs without it

    code, tld = LANGS.get(lang, LANGS["en"])
    buf = io.BytesIO()
    gTTS(text=text[:MAX_CHARS], lang=code, tld=tld).write_to_fp(buf)
    return buf.getvalue()
