"""Thin client for Meta Model API (chat + Muse Voice Transcribe)."""
import asyncio
import json
import re

import httpx

from . import config, mock


def _headers(key: str) -> dict:
    return {"Authorization": f"Bearer {key}"}


async def chat(messages: list[dict], use_open_model: bool = False, **extra) -> str:
    """Chat completion text. Set use_open_model=True to route to Muse Spark Open on Baseten."""
    if config.MOCK_MODE:
        return mock.ANSWER
    msg = await chat_message(messages, use_open_model, **extra)
    return msg.get("content") or ""


async def chat_message(messages: list[dict], use_open_model: bool = False, **extra) -> dict:
    """Chat completion returning the full assistant message (needed for tool calls)."""
    if use_open_model and config.BASETEN_API_KEY:
        base, key, model = config.BASETEN_BASE_URL, config.BASETEN_API_KEY, config.OPEN_MODEL
    else:
        base, key, model = config.CHAT_BASE, config.CHAT_KEY, config.CHAT_MODEL

    payload = {"model": model, "messages": messages, **extra}
    async with httpx.AsyncClient(timeout=config.REQUEST_TIMEOUT) as client:
        r = await client.post(
            f"{base}/chat/completions", json=payload, headers=_headers(key)
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]


async def transcribe(audio_bytes: bytes, filename: str, content_type: str) -> str:
    """Muse Voice Transcribe: POST /v1/asr/transcribe.

    NOTE: confirm exact field names (file/language) against the Meta Model API
    reference (dev.meta.ai/docs) when the API key is available.
    """
    if config.MOCK_MODE:
        return mock.TRANSCRIPT
    if config.PROVIDER == "baseten":
        return await _transcribe_via_chat(audio_bytes, filename)
    files = {"file": (filename, audio_bytes, content_type)}
    data = {"language": "te"}  # Telugu
    async with httpx.AsyncClient(timeout=config.REQUEST_TIMEOUT) as client:
        r = await client.post(
            f"{config.META_BASE_URL}/asr/transcribe",
            files=files,
            data=data,
            headers=_headers(config.META_API_KEY),
        )
        r.raise_for_status()
        body = r.json()
        return body.get("text") or body.get("transcript") or ""


async def diagnose_image(image_bytes: bytes, content_type: str, question: str = "", lang: str = "auto") -> str:
    """Send a crop photo to Muse Spark (image understanding) and get a Telugu answer."""
    if config.MOCK_MODE:
        return mock.DIAGNOSIS
    import base64

    b64 = base64.b64encode(image_bytes).decode()
    prompt = (
        "You are Krishi Mitra, a farming assistant. Look at this crop photo. "
        "Identify the crop, any visible disease, pest or nutrient problem, how sure you are, "
        "and simple next steps for a small farmer. {lang_instruction} "
        "If the photo is unclear, say so and ask for a better photo. Never give exact pesticide doses. "
        "If the problem looks serious or you are unsure, tell the farmer to call the Kisan Call Centre "
        "(1800-180-1551) or the local agriculture officer."
    )
    from . import lang as langmod
    prompt = prompt.format(lang_instruction=langmod.instruction(langmod.resolve(lang, question)))
    if question:
        prompt += f"\nFarmer's question: {question}"
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{content_type};base64,{b64}"},
                },
            ],
        }
    ]
    return await chat(messages)


async def _to_wav(audio_bytes: bytes) -> tuple[bytes, str]:
    """Browsers record WebM/Opus, which Baseten does not list. Convert to 16 kHz mono WAV
    with ffmpeg. Returns (bytes, mime). Falls back to the original bytes if ffmpeg fails."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-loglevel", "error", "-i", "pipe:0", "-ac", "1", "-ar", "16000",
            "-f", "wav", "pipe:1",
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        out, _err = await proc.communicate(audio_bytes)
        if proc.returncode == 0 and out:
            return out, "audio/wav"
    except FileNotFoundError:
        pass
    return audio_bytes, "audio/webm"


class AudioNotUnderstood(Exception):
    """The model could not produce a usable transcript (silence, unsupported audio, refusal)."""


_REFUSAL_HINTS = ("audio", "listen", "transcribe", "unable", "cannot", "can't", "don't have", "do not have", "sorry")


def parse_transcript(raw: str) -> str | None:
    """Return the transcript text, or None when the model did not really transcribe.
    Expects JSON {"understood": bool, "text": str}; accepts a short plain transcript too,
    but never a refusal like "I can't listen to audio" (that must not become the farmer's question)."""
    raw = (raw or "").strip()
    m = re.search(r"\{.*\}", raw, re.S)
    if m:
        try:
            obj = json.loads(m.group(0))
            text = str(obj.get("text") or "").strip()
            return text if obj.get("understood") and text else None
        except (json.JSONDecodeError, AttributeError):
            pass
    low = raw.lower()
    if not raw or len(raw) > 400 or any(h in low for h in _REFUSAL_HINTS):
        return None
    return raw


async def _transcribe_via_chat(audio_bytes: bytes, filename: str) -> str:
    """Muse Spark Open takes audio as an `audio_url` content part (Baseten docs:
    inference/model-apis/audio). Supported: WAV, MP3, FLAC, OGG, M4A. Not WebM."""
    import base64

    data, mime = await _to_wav(audio_bytes)
    b64 = base64.b64encode(data).decode()
    prompt = (
        "This is a farmer speaking Telugu, Hindi or English, often mixing English words such as price, rate, mandi, market, weather, rain, scheme, loan, insurance, paddy, groundnut, cotton, tomato, fertilizer, pest. Transcribe the speech in this audio exactly as spoken, in the language it is spoken in "
        "(write Telugu speech in Telugu script, Hindi in Devanagari). Reply with JSON only: "
        '{"understood": true or false, "language": "te|hi|en|other", "text": "<exact transcript>"}. '
        "If there is no clear speech or you cannot process the audio, set understood to false and text to an "
        "empty string. Never add explanations."
    )
    messages = [{
        "role": "user",
        "content": [
            {"type": "text", "text": prompt},
            {"type": "audio_url", "audio_url": {"url": f"data:{mime};base64,{b64}"}},
        ],
    }]
    text = parse_transcript(await chat(messages))
    if not text:
        raise AudioNotUnderstood(
            f"audio not understood (input {len(audio_bytes)} bytes, wav {len(data)} bytes, ffmpeg_ok={mime == 'audio/wav'})"
        )
    return text
