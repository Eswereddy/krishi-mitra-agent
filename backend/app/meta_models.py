"""Clients for the other Meta Model API models, used by the optional extras (leaf scan, advice card, speech).

Meta Model API (https://api.meta.ai/v1, key in MODEL_API_KEY):
  * muse-voice-transcribe-1.0  POST /asr/transcribe   (WAV, 16 kHz mono)        -> /api/asr
  * sam-3.1                    POST /responses         (image + short noun prompt) -> /api/leaf-scan
  * muse-image-1.0             POST /images/generations                          -> /api/advice-card
The core agent keeps running on Muse Spark Open (open weights, Baseten); this module is purely additive and does
nothing unless MODEL_API_KEY is set. Request shapes follow the public docs at dev.meta.ai/docs.
"""
import base64
import io
import json
import os

import httpx
from PIL import Image, ImageChops, ImageDraw

BASE = os.getenv("META_BASE_URL", "https://api.meta.ai/v1").rstrip("/")
ASR_MODEL = "muse-voice-transcribe-1.0"
SAM_MODEL = "sam-3.1"
IMAGE_MODEL = "muse-image-1.0"
WONDER_MODEL = os.getenv("WONDER_MODEL", "muse-wonder-1.0")
TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "60"))
MIN_CONFIDENCE = 0.3
MAX_SIDE = 1024
_TRANSPORT: httpx.AsyncBaseTransport | None = None   # tests inject a mock transport here
LANG_NAMES = {"te": "Telugu", "hi": "Hindi", "en": "English"}


def key() -> str:
    return os.getenv("MODEL_API_KEY", "")


def available() -> bool:
    return bool(key())


def status() -> dict:
    """Which Meta models this deployment is using (shown at /api/meta-models, handy for judges)."""
    from . import config
    return {
        "muse_spark_open": {"model": config.OPEN_MODEL, "role": "chat, tool calling, vision, audio (open weights)",
                            "configured": bool(config.BASETEN_API_KEY) or config.PROVIDER != "baseten"},
        "muse_glimmer": {"model": config.GLIMMER_MODEL, "role": "open-weight fallback when the main model call fails",
                         "configured": bool(config.GLIMMER_BASE_URL)},
        "muse_voice_transcribe": {"model": ASR_MODEL, "role": "speech to text (/api/asr)", "configured": available()},
        "sam": {"model": SAM_MODEL, "role": "leaf damage measurement (/api/leaf-scan)", "configured": available()},
        "muse_wonder": {"model": WONDER_MODEL, "role": "independent second-opinion audit of answers (/api/second-opinion)", "configured": available()},
        "muse_image": {"model": IMAGE_MODEL, "role": "shareable advice card (/api/advice-card)", "configured": available()},
    }


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=TIMEOUT, transport=_TRANSPORT)


def _auth() -> dict:
    return {"Authorization": f"Bearer {key()}"}


# ---------------------------------------------------------------- Muse Voice Transcribe

async def asr_transcribe(wav: bytes, languages: tuple[str, ...] = ("Telugu", "Hindi", "English")) -> str:
    """Transcribe a 16 kHz mono WAV recording. Returns "" when nothing was heard."""
    req = {"model": ASR_MODEL, "audioEncoding": "PCM_16KHZ", "mode": "PUSH_TO_TALK", "languageBias": list(languages)}
    async with _client() as c:
        r = await c.post(f"{BASE}/asr/transcribe", headers=_auth(),
                         files={"request": (None, json.dumps(req), "application/json"),
                                "audio": ("question.wav", wav, "audio/wav")})
        r.raise_for_status()
        return str(r.json().get("transcript") or "").strip()


# ---------------------------------------------------------------- Muse Wonder (reasoning model)

def _output_text(body: dict) -> str:
    """Text of a Responses API reply: `output_text` if present, else the text parts of the output messages."""
    if isinstance(body.get("output_text"), str):
        return body["output_text"].strip()
    parts = []
    for item in body.get("output") or []:
        for c in (item.get("content") or []) if isinstance(item, dict) else []:
            if isinstance(c, dict) and isinstance(c.get("text"), str) and c.get("type", "output_text") == "output_text":
                parts.append(c["text"])
    return "".join(parts).strip()


async def wonder(instructions: str, text: str, effort: str = "medium", max_tokens: int = 1500) -> str:
    """One call to Muse Wonder (reasoning model) through the Responses API. Returns its text."""
    body = {"model": WONDER_MODEL, "instructions": instructions, "input": text,
            "reasoning": {"effort": effort}, "max_output_tokens": max_tokens}
    async with _client() as c:
        r = await c.post(f"{BASE}/responses", headers=_auth(), json=body)
        r.raise_for_status()
        return _output_text(r.json())


# ---------------------------------------------------------------- Muse Image

async def generate_image(prompt: str, size: str = "1024x1024") -> bytes:
    body = {"model": IMAGE_MODEL, "prompt": prompt, "n": 1, "size": size, "response_format": "b64_json",
            "output_format": "png"}
    async with _client() as c:
        r = await c.post(f"{BASE}/images/generations", headers=_auth(), json=body)
        r.raise_for_status()
        data = r.json().get("data") or []
    if not data or not data[0].get("b64_json"):
        raise ValueError("image service returned no image")
    return base64.b64decode(data[0]["b64_json"])


# ---------------------------------------------------------------- SAM 3.1

async def segment(jpeg: bytes, prompt: str) -> str:
    """Ask SAM 3.1 for every instance of a short noun phrase; returns its raw special-token output text."""
    body = {"model": SAM_MODEL, "stream": True, "metadata": {"include_confidence": "true"},
            "input": [{"type": "message", "role": "user", "content": [
                {"type": "input_text", "text": prompt},
                {"type": "input_image", "image_url": "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()}]}]}
    parts: list[str] = []
    async with _client() as c:
        async with c.stream("POST", f"{BASE}/responses", headers={**_auth(), "Accept": "text/event-stream"},
                            json=body) as r:
            if r.status_code >= 400:
                await r.aread()
                r.raise_for_status()
            async for line in r.aiter_lines():
                if not line.startswith("data:"):
                    continue
                try:
                    ev = json.loads(line[5:].strip())
                except ValueError:
                    continue
                if str(ev.get("type", "")).endswith("output_text.delta") and isinstance(ev.get("delta"), str):
                    parts.append(ev["delta"])
    return "".join(parts)


def _layer(records, size: tuple[int, int]) -> tuple[Image.Image, list[dict]]:
    """Paint every confident mask of one SAM result onto a full-size binary layer (255 = object)."""
    import meta_sam_parser as sp
    layer = Image.new("L", size, 0)
    spots = []
    box_conf = {r.object_id: r.confidence for r in records if getattr(r, "kind", "") == "box"}   # c may sit on the box
    for rec in records:
        if getattr(rec, "kind", "") != "mask":
            continue
        conf = rec.confidence if rec.confidence is not None else box_conf.get(rec.object_id)
        if conf is not None and conf < MIN_CONFIDENCE:
            continue
        b = rec.bounds
        bw, bh = max(1, round(b.right - b.left)), max(1, round(b.bottom - b.top))
        raster = sp.decode_mask_to_raster(rec.mask)
        m = Image.frombytes("L", (rec.mask.width, rec.mask.height), raster.translate(bytes([0] + [255] * 255)))
        piece = Image.new("L", size, 0)
        piece.paste(m.resize((bw, bh), Image.NEAREST), (round(b.left), round(b.top)))
        layer = ImageChops.lighter(layer, piece)
        spots.append({"box": [round(b.left), round(b.top), round(b.right), round(b.bottom)],
                      "confidence": None if conf is None else round(conf, 2)})
    return layer, spots


def parse_segmentation(raw: str, size: tuple[int, int]) -> tuple[Image.Image, list[dict]]:
    import meta_sam_parser as sp
    parser = sp.image_segmentation_format().create_parser()
    parser.push(raw)
    res = parser.finish(sp.CompletedOutcome()).result
    return _layer(res.records, size)


def _count(layer: Image.Image) -> int:
    return layer.histogram()[255]


BANDS = ((5, "mild"), (25, "moderate"), (101, "severe"))


def measure(lesion_raw: str, leaf_raw: str, base: Image.Image) -> dict:
    """Damage measurement done in code from SAM masks: share of the leaf covered by lesions.
    The model finds the regions; the percentage is plain arithmetic on pixels, never a model guess."""
    size = base.size
    lesions, spots = parse_segmentation(lesion_raw, size)
    leaf, leaf_spots = parse_segmentation(leaf_raw, size)
    n_les, n_leaf = _count(lesions), _count(leaf)
    if n_les == 0:
        return {"found": False, "severity_pct": 0.0, "band": "none", "spots": [], "leaf_found": n_leaf > 0,
                "overlay": _overlay(base, lesions, leaf_spots, [])}
    if n_leaf > 0:
        inside = _count(ImageChops.multiply(lesions, leaf))
        pct, basis = inside / n_leaf * 100, "leaf"
    else:
        pct, basis = n_les / (size[0] * size[1]) * 100, "photo"
    pct = round(min(pct, 100.0), 1)
    band = next(name for limit, name in BANDS if pct < limit)
    return {"found": True, "severity_pct": pct, "band": band, "basis": basis, "spots": spots[:8],
            "spot_count": len(spots), "leaf_found": n_leaf > 0,
            "overlay": _overlay(base, lesions, leaf_spots, spots)}


def _overlay(base: Image.Image, lesions: Image.Image, leaf_spots: list[dict], spots: list[dict]) -> str:
    red = Image.new("RGB", base.size, (230, 40, 40))
    img = Image.composite(red, base, lesions.point(lambda v: 130 if v else 0))
    d = ImageDraw.Draw(img)
    for s in leaf_spots[:3]:
        d.rectangle(s["box"], outline=(40, 200, 90), width=3)
    for s in spots[:8]:
        d.rectangle(s["box"], outline=(255, 210, 0), width=2)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=82)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def prepare_image(data: bytes) -> tuple[bytes, Image.Image]:
    """Decode an upload, fix orientation, shrink to MAX_SIDE, return (jpeg bytes, RGB image). ValueError if not an image."""
    try:
        from PIL import ImageOps
        img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    except Exception as e:
        raise ValueError("not a readable image") from e
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=88)
    return buf.getvalue(), img
