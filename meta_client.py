"""Thin client for Meta Model API (chat + Muse Voice Transcribe)."""
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
    if use_open_model and config.BASETEN_BASE_URL:
        base, key, model = config.BASETEN_BASE_URL, config.BASETEN_API_KEY, config.OPEN_MODEL
    else:
        base, key, model = config.META_BASE_URL, config.META_API_KEY, config.META_CHAT_MODEL

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


async def diagnose_image(image_bytes: bytes, content_type: str, question: str = "") -> str:
    """Send a crop photo to Muse Spark (image understanding) and get a Telugu answer."""
    if config.MOCK_MODE:
        return mock.DIAGNOSIS
    import base64

    b64 = base64.b64encode(image_bytes).decode()
    prompt = (
        "You are Krishi Mitra, a farming assistant. Look at this crop photo. "
        "Identify the crop, any visible disease, pest or nutrient problem, how sure you are, "
        "and simple next steps for a small farmer. Answer in simple Telugu. "
        "If the photo is unclear, say so and ask for a better photo."
    )
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
