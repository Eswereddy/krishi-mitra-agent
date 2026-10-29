"""WhatsApp channel (Meta WhatsApp Cloud API): the same agent, for farmers who will not install an app.

A farmer sends text, a voice note or a crop photo to the business number; the webhook runs the same
`agent.run_agent` (tools + verification layer) and replies with text, plus a voice reply for voice notes.

Setup (see README): set WHATSAPP_VERIFY_TOKEN, WHATSAPP_ACCESS_TOKEN, WHATSAPP_PHONE_NUMBER_ID,
WHATSAPP_APP_SECRET, then point the Meta webhook at  https://<your-host>/webhook/whatsapp
and subscribe to the "messages" field. Optional: WHATSAPP_ALLOWED_NUMBERS (comma separated, digits only)
restricts who can use the bot, which protects API credits while the number is in test mode.
"""
import asyncio
import hashlib
import hmac
import json
import logging
import os
import re
import time

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response

from . import agent, lang as langmod, meta_client, ratelimit, tts as ttsmod

log = logging.getLogger("krishi.whatsapp")
router = APIRouter()

MAX_TEXT = 3500           # WhatsApp allows 4096 characters per text message
SESSION_TTL_S = 24 * 3600
MAX_SESSIONS = 500
DEFAULT_PHOTO_QUESTION = "Please check this crop photo and tell me what to do."

FOOTER = {
    "te": "✓ అన్ని సంఖ్యలు టూల్ ఫలితాలతో సరిపోలాయి",
    "hi": "✓ सभी आंकड़े टूल परिणामों से मिले",
    "en": "✓ All figures verified against tool results",
}
HELP = (
    "🌾 *Krishi Mitra*\n"
    "Send a question (text or voice note) or a crop photo. / మీ ప్రశ్న (టెక్స్ట్ లేదా వాయిస్) లేదా పంట ఫోటో పంపండి. / "
    "सवाल (टेक्स्ट या वॉइस) या फसल की फोटो भेजें.\n\n"
    "Commands: /district Kurnool · /crop Groundnut · /land yes|no · /state Andhra Pradesh · /reset"
)
SORRY = {
    "te": "క్షమించండి, ఇప్పుడు సమాధానం ఇవ్వలేకపోయాను. కొద్దిసేపటి తర్వాత మళ్లీ ప్రయత్నించండి.",
    "hi": "क्षमा करें, अभी जवाब नहीं दे सका। थोड़ी देर बाद फिर कोशिश करें।",
    "en": "Sorry, I could not answer just now. Please try again in a little while.",
}
NOT_HEARD = {
    "te": "స్పష్టంగా వినిపించలేదు. దయచేసి మళ్లీ వాయిస్ పంపండి లేదా టైప్ చేయండి.",
    "hi": "साफ़ सुनाई नहीं दिया। कृपया फिर से वॉइस भेजें या टाइप करें।",
    "en": "I could not hear that clearly. Please send the voice note again or type your question.",
}
UNSUPPORTED = "Please send text, a voice note or a crop photo. / టెక్స్ట్, వాయిస్ లేదా పంట ఫోటో పంపండి."

_SEEN: dict[str, float] = {}
_SESSIONS: dict[str, dict] = {}


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


def _graph(path: str) -> str:
    return f"https://graph.facebook.com/{_env('WHATSAPP_GRAPH_VERSION', 'v21.0')}/{path}"


# ---------------------------------------------------------------- webhook endpoints
@router.get("/webhook/whatsapp")
async def verify_webhook(request: Request):
    """Meta calls this once when you save the webhook URL in the developer console."""
    q = request.query_params
    token = _env("WHATSAPP_VERIFY_TOKEN")
    if token and q.get("hub.mode") == "subscribe" and hmac.compare_digest(q.get("hub.verify_token", ""), token):
        return Response(q.get("hub.challenge", ""), media_type="text/plain")
    raise HTTPException(403, "Verification failed")


def signature_ok(body: bytes, header: str) -> bool:
    """Check Meta's X-Hub-Signature-256 so nobody else can post fake messages to the webhook."""
    secret = _env("WHATSAPP_APP_SECRET")
    if not secret:
        return _env("WHATSAPP_ALLOW_UNSIGNED").lower() in ("1", "true")   # local testing only
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header or "")


@router.post("/webhook/whatsapp")
async def receive_webhook(request: Request, background: BackgroundTasks):
    body = await request.body()
    if not signature_ok(body, request.headers.get("x-hub-signature-256", "")):
        raise HTTPException(403, "Bad signature")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid JSON")
    for msg in extract_messages(payload):
        background.add_task(handle_message, msg)       # answer after replying 200 quickly (Meta retries slow webhooks)
    return {"ok": True}


def extract_messages(payload: dict) -> list[dict]:
    """Flatten Meta's nested webhook payload into simple message dicts."""
    out = []
    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            for m in (change.get("value") or {}).get("messages") or []:
                kind = m.get("type")
                item = {"id": m.get("id") or "", "from": m.get("from") or "", "type": kind, "text": ""}
                if kind == "text":
                    item["text"] = (m.get("text") or {}).get("body", "")
                elif kind in ("audio", "image"):
                    media = m.get(kind) or {}
                    item["media_id"] = media.get("id")
                    item["mime"] = media.get("mime_type") or ("audio/ogg" if kind == "audio" else "image/jpeg")
                    if kind == "image":
                        item["text"] = media.get("caption", "")
                if item["id"] and item["from"]:
                    out.append(item)
    return out


# ---------------------------------------------------------------- sessions, dedup, allow-list
def _digits(s: str) -> str:
    return re.sub(r"\D", "", s or "")


def _allowed(sender: str) -> bool:
    allow = {_digits(n) for n in _env("WHATSAPP_ALLOWED_NUMBERS").split(",") if _digits(n)}
    return not allow or _digits(sender) in allow


def _first_time(message_id: str) -> bool:
    """Meta retries webhooks; answer each message once."""
    now = time.time()
    for k in [k for k, t in _SEEN.items() if now - t > 3600]:
        del _SEEN[k]
    if message_id in _SEEN:
        return False
    _SEEN[message_id] = now
    return True


def _session(sender: str) -> dict:
    now = time.time()
    for k in [k for k, s in _SESSIONS.items() if now - s["ts"] > SESSION_TTL_S]:
        del _SESSIONS[k]
    if sender not in _SESSIONS and len(_SESSIONS) >= MAX_SESSIONS:
        del _SESSIONS[min(_SESSIONS, key=lambda k: _SESSIONS[k]["ts"])]
    s = _SESSIONS.setdefault(sender, {"history": [], "profile": {"state": "Andhra Pradesh"}, "ts": now})
    s["ts"] = now
    return s


def _command(sess: dict, text: str) -> str | None:
    """Tiny profile commands, so the agent knows the farmer's district and crop. None = not a command."""
    m = re.match(r"^/(\w+)\s*(.*)$", text.strip(), re.S)
    if not m:
        return None
    cmd, arg = m.group(1).lower(), m.group(2).strip()
    prof = sess["profile"]
    if cmd in ("help", "start"):
        return HELP
    if cmd == "reset":
        sess["history"].clear()
        sess["profile"] = {"state": "Andhra Pradesh"}
        return "✓ Reset. / రీసెట్ అయింది."
    if cmd in ("district", "crop", "state") and arg:
        prof["main_crop" if cmd == "crop" else cmd] = arg[:60]
        return f"✓ {cmd}: {arg[:60]}"
    if cmd == "land" and arg.lower() in ("yes", "no", "y", "n"):
        prof["owns_land"] = arg.lower() in ("yes", "y")
        return f"✓ land: {'yes' if prof['owns_land'] else 'no'}"
    return HELP


# ---------------------------------------------------------------- formatting
def to_whatsapp(text: str) -> str:
    """Our answers use **bold** and # headings; WhatsApp uses *bold*."""
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)
    return re.sub(r"(?m)^#+\s*", "", text).strip()


def split_text(text: str, limit: int = MAX_TEXT) -> list[str]:
    parts, cur = [], ""
    for para in text.split("\n\n"):
        while len(para) > limit:                       # a single huge paragraph
            cut = para.rfind(" ", 0, limit)
            if cut <= 0:
                cut = limit
            parts.append(para[:cut].strip())
            para = para[cut:].lstrip()
        if cur and len(cur) + len(para) + 2 > limit:
            parts.append(cur.strip())
            cur = ""
        cur += ("\n\n" if cur else "") + para
    if cur.strip():
        parts.append(cur.strip())
    return parts or [text[:limit]]


def speech_text(text: str, code: str) -> str:
    rupee = {"te": "రూపాయలు", "hi": "रुपये", "en": "rupees"}.get(code, "rupees")
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"₹\s?([\d,]+(?:\.\d+)?)", rf"\1 {rupee}", text)
    text = re.sub(r"[*_`#>|]", "", text)
    text = re.sub("[\U0001F300-\U0001FAFF☀-➿✅✓✔️]", "", text)
    return re.sub(r"\s*\n+\s*", ". ", text).strip()


def _footer(result: dict, code: str) -> str:
    v = result.get("verification") or {}
    return f"\n\n{FOOTER.get(code, FOOTER['en'])}" if v.get("passed") and v.get("checked", 0) > 0 else ""


# ---------------------------------------------------------------- Graph API calls
async def _graph_call(method: str, path: str, **kw):
    headers = {"Authorization": f"Bearer {_env('WHATSAPP_ACCESS_TOKEN')}"}
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.request(method, _graph(path), headers=headers, **kw)
    if r.status_code >= 400:
        log.warning("WhatsApp API %s %s -> %s %s", method, path, r.status_code, r.text[:200])
        r.raise_for_status()
    return r


async def _post_message(to: str, body: dict) -> None:
    pnid = _env("WHATSAPP_PHONE_NUMBER_ID")
    await _graph_call("POST", f"{pnid}/messages", json={"messaging_product": "whatsapp", "to": to, **body})


async def _send_text(to: str, text: str) -> None:
    for part in split_text(text):
        await _post_message(to, {"type": "text", "text": {"body": part, "preview_url": False}})


async def _send_audio(to: str, mp3: bytes) -> None:
    pnid = _env("WHATSAPP_PHONE_NUMBER_ID")
    r = await _graph_call("POST", f"{pnid}/media", data={"messaging_product": "whatsapp", "type": "audio/mpeg"},
                          files={"file": ("reply.mp3", mp3, "audio/mpeg")})
    await _post_message(to, {"type": "audio", "audio": {"id": r.json()["id"]}})


async def _mark_read(message_id: str) -> None:
    try:
        pnid = _env("WHATSAPP_PHONE_NUMBER_ID")
        await _graph_call("POST", f"{pnid}/messages",
                          json={"messaging_product": "whatsapp", "status": "read", "message_id": message_id})
    except Exception:
        pass                                            # a missing read receipt must never block the answer


async def _download_media(media_id: str, fallback_mime: str) -> tuple[bytes, str]:
    meta = (await _graph_call("GET", media_id)).json()
    headers = {"Authorization": f"Bearer {_env('WHATSAPP_ACCESS_TOKEN')}"}
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.get(meta["url"], headers=headers)
        r.raise_for_status()
    return r.content, (meta.get("mime_type") or fallback_mime).split(";")[0]


# ---------------------------------------------------------------- the conversation
async def _ask(sess: dict, text: str, image: tuple[bytes, str] | None = None) -> dict:
    result = await agent.run_agent(text or DEFAULT_PHOTO_QUESTION, False, "auto", dict(sess["profile"]),
                                   None if image else list(sess["history"]), image)
    sess["history"] += [{"role": "user", "content": text or "(crop photo)"},
                        {"role": "assistant", "content": result["answer"]}]
    del sess["history"][:-6]
    return result


async def _reply(to: str, result: dict, code: str, heard: str = "", voice: bool = False) -> None:
    answer = to_whatsapp(result["answer"])
    prefix = f"🎤 _{heard}_\n\n" if heard else ""
    await _send_text(to, prefix + answer + _footer(result, code))
    if voice and _env("WHATSAPP_VOICE_REPLY", "1") != "0":
        try:
            mp3 = await asyncio.to_thread(ttsmod.synthesize, speech_text(answer, code)[: ttsmod.MAX_CHARS], code)
            await _send_audio(to, mp3)
        except Exception as e:                          # text answer already delivered; voice is a bonus
            log.warning("voice reply failed: %s", type(e).__name__)


async def handle_message(msg: dict) -> None:
    sender = msg["from"]
    if not _allowed(sender) or not _first_time(msg["id"]):
        return
    await _mark_read(msg["id"])
    wait = ratelimit.check(f"wa:{sender}", "/api/agent")
    if wait is not None:
        await _send_text(sender, f"Please wait {wait} seconds. / దయచేసి {wait} సెకన్లు ఆగండి.")
        return
    sess = _session(sender)
    code = langmod.detect(msg.get("text") or "")
    try:
        kind = msg["type"]
        if kind == "text":
            reply = _command(sess, msg["text"])
            if reply is not None:
                return await _send_text(sender, reply)
            if not msg["text"].strip():
                return
            return await _reply(sender, await _ask(sess, msg["text"]), code)
        if kind == "audio":
            data, mime = await _download_media(msg["media_id"], msg["mime"])
            try:
                heard = await meta_client.transcribe(data, "voice.ogg", mime)
            except meta_client.AudioNotUnderstood:
                # the spoken language is unknown here, so ask in Telugu, Hindi and English
                return await _send_text(sender, "\n".join(NOT_HEARD[k] for k in ("te", "hi", "en")))
            code = langmod.detect(heard)
            return await _reply(sender, await _ask(sess, heard), code, heard=heard, voice=True)
        if kind == "image":
            data, mime = await _download_media(msg["media_id"], msg["mime"])
            code = langmod.detect(msg["text"]) if msg["text"] else "te"
            return await _reply(sender, await _ask(sess, msg["text"], (data, mime)), code)
        await _send_text(sender, UNSUPPORTED)
    except Exception as e:
        log.exception("WhatsApp message handling failed: %s", type(e).__name__)
        try:
            await _send_text(sender, SORRY.get(code, SORRY["en"]))
        except Exception:
            pass
