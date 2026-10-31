"""Optional endpoints that use more of Meta's model family (all additive; the core agent is unchanged).

  GET  /api/meta-models   which Meta models this deployment uses
  POST /api/asr           speech to text: Muse Voice Transcribe when MODEL_API_KEY is set, else the existing Spark Open path
  POST /api/leaf-scan     SAM 3.1 finds lesions + leaf; the damage percentage is computed in code from the masks
  POST /api/second-opinion  Muse Wonder audits an answer against its tool results (numbers are also checked in code)
  POST /api/advice-card   Muse Image makes a shareable advice card from a verified answer
"""
import asyncio
import re

import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from . import audit, config, meta_client, meta_models as mm, ratelimit

router = APIRouter()
MAX_AUDIO_BYTES = 10 * 1024 * 1024
MAX_IMAGE_BYTES = 8 * 1024 * 1024
ratelimit.LIMITS.update({"/api/asr": ratelimit.LIMITS["/api/transcribe"],
                         "/api/leaf-scan": 6, "/api/advice-card": 6, "/api/second-opinion": 8})   # image models cost real credits


def _need_key() -> None:
    if not mm.available():
        raise HTTPException(503, "This feature uses the Meta Model API: set MODEL_API_KEY on the server.")


@router.get("/api/meta-models")
async def meta_models():
    return mm.status()


def _bias(lang: str) -> tuple[str, ...]:
    """Language hint for Muse Voice Transcribe: the chosen language first, then the common ones (code-switching is fine)."""
    from . import lang as langmod
    first = langmod.NAMES.get(lang)
    base = ["Telugu", "Hindi", "English"]
    return tuple(([first] if first else []) + [b for b in base if b != first])


@router.post("/api/asr")
async def asr(audio: UploadFile = File(...), lang: str = Form("auto")):
    """Muse Voice Transcribe (dedicated speech model) when a Meta Model API key is set; otherwise, or if that call
    fails, the existing Muse Spark Open audio path, so voice never stops working."""
    data = await audio.read(MAX_AUDIO_BYTES + 1)
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "Audio too long (max 10MB)")
    if mm.available():
        try:
            wav, _mime = await meta_client._to_wav(data)
            text = await mm.asr_transcribe(wav, _bias(lang))
            if not text:
                raise HTTPException(422, "Could not understand the audio. Please try again.")
            return {"text": text, "engine": mm.ASR_MODEL}
        except (httpx.HTTPError, ValueError):
            pass                                            # fall through to the existing path
    if not config.CHAT_KEY and not config.MOCK_MODE:
        raise HTTPException(503, "API key for the selected PROVIDER not set in backend/.env")
    try:
        text = await meta_client.transcribe(data, audio.filename or "audio.webm", audio.content_type or "audio/webm")
    except meta_client.AudioNotUnderstood as e:
        raise HTTPException(422, str(e))
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"Meta API error: {e.response.text[:300]}")
    return {"text": text, "engine": config.CHAT_MODEL}


@router.post("/api/leaf-scan")
async def leaf_scan(image: UploadFile = File(...)):
    """Measure how much of a leaf is damaged. SAM 3.1 segments 'diseased leaf spot' and 'leaf'; we compute the share.
    This is a measurement of the photo, not a diagnosis: it never names a disease or a pesticide."""
    _need_key()
    if not (image.content_type or "").lower().startswith("image/"):
        raise HTTPException(415, "Please upload a photo (JPEG or PNG)")
    raw = await image.read(MAX_IMAGE_BYTES + 1)
    if len(raw) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "Image too large (max 8MB)")
    try:
        jpeg, base = mm.prepare_image(raw)
    except ValueError:
        raise HTTPException(400, "Could not read this image")
    try:
        lesion_raw, leaf_raw = await asyncio.gather(mm.segment(jpeg, "diseased leaf spot"), mm.segment(jpeg, "leaf"))
        result = await asyncio.to_thread(mm.measure, lesion_raw, leaf_raw, base)
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"Meta API error: {e.response.text[:300]}")
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Model service unavailable ({type(e).__name__}). Please try again in a moment.")
    result["needs_expert"] = result["band"] == "severe"
    result["model"] = mm.SAM_MODEL
    result["note"] = ("Measured from the photo with SAM 3.1. This is how much of the visible leaf is marked, "
                      "not a diagnosis. Ask the agriculture officer or call the Kisan Call Centre 1800-180-1551.")
    return result


def headline(text: str, limit: int = 110) -> str:
    """First sentence of an answer, without markdown, shortened: the only words that go on the card."""
    t = re.sub(r"[*_#`>•\-]+", " ", text or "")
    t = re.sub(r"\s+", " ", t).strip()
    m = re.match(r"(.+?[.!?।])(\s|$)", t)
    t = (m.group(1) if m else t)
    return t[:limit].rstrip(" ,;:") if len(t) > limit else t


@router.post("/api/advice-card")
async def advice_card(payload: dict):
    """Muse Image: a clean, shareable advice card (for WhatsApp groups) from an answer the farmer already received."""
    _need_key()
    line = headline(str(payload.get("text") or ""))
    if not line:
        raise HTTPException(400, "text required")
    lang = payload.get("lang") if payload.get("lang") in mm.LANG_NAMES else "en"
    crop = re.sub(r"[^\w \-]", "", str(payload.get("crop") or ""))[:30]
    prompt = (
        "A clean, friendly square advisory card for Indian farmers, warm green and cream palette, flat illustration "
        + (f"of a {crop} field" if crop else "of a farm field")
        + " at the top, large easy-to-read text panel below. The ONLY text on the card is this exact line in "
        + f"{mm.LANG_NAMES[lang]}, written exactly as given and nothing else: \"{line}\". Small footer text: Krishi Mitra. "
        "No other words, no numbers other than those in the line, no logos, no people's faces."
    )
    try:
        png = await mm.generate_image(prompt, "1024x1024")
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"Meta API error: {e.response.text[:300]}")
    except (httpx.HTTPError, ValueError) as e:
        raise HTTPException(502, f"Image service unavailable ({type(e).__name__}). Please try again.")
    import base64
    return {"image": "data:image/png;base64," + base64.b64encode(png).decode(), "text": line, "model": mm.IMAGE_MODEL}


@router.post("/api/second-opinion")
async def second_opinion(payload: dict):
    """A second Meta model (Muse Wonder) reviews an answer against the tool results the agent saw. The number check
    runs in code and works even without a key; the reasoning review needs MODEL_API_KEY."""
    answer = str(payload.get("answer") or "").strip()
    if not answer:
        raise HTTPException(400, "answer required")
    from . import lang as langmod
    lang = payload.get("lang") if payload.get("lang") in langmod.NAMES else "en"
    return await audit.second_opinion(answer, payload.get("steps") or [], lang)
