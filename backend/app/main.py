import asyncio
import json
from pathlib import Path

import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import agent, alerts, brief, config, meta_extras, lang as langmod, meta_client, ratelimit, tts as ttsmod, whatsapp

MAX_AUDIO_BYTES = 10 * 1024 * 1024
MAX_IMAGE_BYTES = 8 * 1024 * 1024

app = FastAPI(title="Krishi Mitra Agent")
app.middleware("http")(ratelimit.middleware)
app.include_router(whatsapp.router)
app.include_router(meta_extras.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(httpx.HTTPError)
async def model_service_error(_request, exc: httpx.HTTPError):
    """Timeouts and connection errors to the model service: friendly 502 instead of a 500 stack trace."""
    return JSONResponse(
        status_code=502,
        content={"detail": f"Model service unavailable ({type(exc).__name__}). Please try again in a moment."},
    )


async def _read_image(image: UploadFile) -> tuple[bytes, str]:
    """Read an uploaded crop photo; only real images, size-capped (reads at most one byte over the limit)."""
    mime = (image.content_type or "image/jpeg").lower()
    if not mime.startswith("image/"):
        raise HTTPException(415, "Please upload a photo (JPEG or PNG)")
    data = await image.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "Image too large (max 8MB)")
    return data, mime


def _require_debug() -> None:
    """Debug endpoints are off in production unless DEBUG_ENDPOINTS=1 (they expose upstream error details)."""
    if not config.DEBUG_ENDPOINTS:
        raise HTTPException(404, "Not found")


@app.get("/api/health")
async def health():
    from . import tools
    return {"ok": True, "provider": config.PROVIDER, "model": config.CHAT_MODEL, "api_key_set": bool(config.CHAT_KEY),
            "mock": config.MOCK_MODE, "tools": len(tools.TOOL_SPECS),
            "live_prices": bool(__import__("os").getenv("DATA_GOV_API_KEY"))}


@app.post("/api/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    """Telugu voice -> text via Muse Voice Transcribe."""
    if not config.CHAT_KEY and not config.MOCK_MODE:
        raise HTTPException(503, "API key for the selected PROVIDER not set in backend/.env")
    data = await audio.read()
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "Audio too long (max 10MB)")
    try:
        text = await meta_client.transcribe(
            data, audio.filename or "audio.webm", audio.content_type or "audio/webm"
        )
    except meta_client.AudioNotUnderstood as e:
        raise HTTPException(422, str(e))
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"Meta API error: {e.response.text[:300]}")
    return {"text": text}


@app.post("/api/diagnose")
async def diagnose(image: UploadFile = File(...), question: str = Form(""), lang: str = Form("auto"),
                   profile: str = Form("")):
    """Crop photo (+ optional question) -> the agent looks at the photo and may call tools
    (weather for spray timing, schemes/insurance, expert help)."""
    if not config.CHAT_KEY and not config.MOCK_MODE:
        raise HTTPException(503, "API key for the selected PROVIDER not set in backend/.env")
    data, mime = await _read_image(image)
    if config.MOCK_MODE:
        answer = await meta_client.diagnose_image(data, mime, question, lang)
        return {"answer": answer, "steps": [], "mock": True, "verification": None}
    try:
        prof = json.loads(profile) if profile else None
    except json.JSONDecodeError:
        prof = None
    text = question.strip() or "Please check this crop photo and tell me what to do."
    try:
        return await agent.run_agent(text, False, lang, prof if isinstance(prof, dict) else None, None, (data, mime))
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"Meta API error: {e.response.text[:300]}")


@app.post("/api/ask")
async def ask(payload: dict):
    """Simple text question -> Muse Spark answer (simple text, no tools)."""
    question = (payload.get("question") or "").strip()
    if not question:
        raise HTTPException(400, "question required")
    messages = [
        {
            "role": "system",
            "content": "You are Krishi Mitra, a helpful farming assistant. "
            + langmod.instruction(langmod.resolve(payload.get("lang"), question)),
        },
        {"role": "user", "content": question},
    ]
    try:
        answer = await meta_client.chat(messages)
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"Meta API error: {e.response.text[:300]}")
    return {"answer": answer}


@app.post("/api/brief")
async def daily_brief(payload: dict):
    """One-tap daily brief (weather, irrigation, spraying, price, sell/hold). No model call: instant, works without an API key."""
    profile = payload.get("profile") if isinstance(payload.get("profile"), dict) else {}
    return await brief.build_brief(profile, payload.get("lang") or "auto")


@app.post("/api/alerts/check")
async def check_price_alerts(payload: dict):
    """Price alerts kept on the device: which targets are reached right now? Live prices only, no model call."""
    results = await alerts.check_alerts(payload.get("alerts"))
    return {"results": results, "count": len(results)}


@app.post("/api/agent")
async def run_agent(payload: dict):
    """Farmer question -> multi-step agent (tools: mandi price, scheme check)."""
    question = (payload.get("question") or "").strip()
    if not question:
        raise HTTPException(400, "question required")
    if not config.CHAT_KEY and not config.MOCK_MODE:
        raise HTTPException(503, "API key for the selected PROVIDER not set in backend/.env")
    try:
        return await agent.run_agent(question, bool(payload.get("use_open_model")), payload.get("lang") or "auto",
                                      payload.get("profile") if isinstance(payload.get("profile"), dict) else None,
                                      payload.get("history") if isinstance(payload.get("history"), list) else None)
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"Meta API error: {e.response.text[:300]}")


def _ndjson(work):
    """Run `work(on_event)` and stream its progress as newline-delimited JSON, so the UI can show each agent step live."""
    async def gen():
        q: asyncio.Queue = asyncio.Queue()

        async def runner():
            try:
                data = await work(q.put_nowait)
                q.put_nowait({"type": "final", "data": data})
            except httpx.HTTPStatusError as e:
                q.put_nowait({"type": "error", "detail": f"Meta API error: {e.response.text[:300]}"})
            except httpx.HTTPError as e:
                q.put_nowait({"type": "error", "detail": f"Model service unavailable ({type(e).__name__}). Please try again in a moment."})
            except Exception as e:  # never leave the stream hanging
                q.put_nowait({"type": "error", "detail": str(e)[:300] or type(e).__name__})
            finally:
                q.put_nowait(None)

        task = asyncio.create_task(runner())
        try:
            while (event := await q.get()) is not None:
                yield json.dumps(event, ensure_ascii=False) + "\n"
        finally:
            task.cancel()

    return StreamingResponse(gen(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/agent/stream")
async def agent_stream(payload: dict):
    """Same as /api/agent, but streams each tool call as it happens (newline-delimited JSON)."""
    question = (payload.get("question") or "").strip()
    if not question:
        raise HTTPException(400, "question required")
    if not config.CHAT_KEY and not config.MOCK_MODE:
        raise HTTPException(503, "API key for the selected PROVIDER not set in backend/.env")
    profile = payload.get("profile") if isinstance(payload.get("profile"), dict) else None
    history = payload.get("history") if isinstance(payload.get("history"), list) else None
    return _ndjson(lambda emit: agent.run_agent(question, False, payload.get("lang") or "auto", profile, history,
                                                None, emit))


@app.post("/api/diagnose/stream")
async def diagnose_stream(image: UploadFile = File(...), question: str = Form(""), lang: str = Form("auto"),
                          profile: str = Form("")):
    """Crop photo -> agent, streaming its steps."""
    if not config.CHAT_KEY and not config.MOCK_MODE:
        raise HTTPException(503, "API key for the selected PROVIDER not set in backend/.env")
    data, mime = await _read_image(image)
    try:
        prof = json.loads(profile) if profile else None
    except json.JSONDecodeError:
        prof = None
    text = question.strip() or "Please check this crop photo and tell me what to do."

    async def work(emit):
        emit({"type": "status", "key": "reading_photo"})
        if config.MOCK_MODE:
            answer = await meta_client.diagnose_image(data, mime, question, lang)
            return {"answer": answer, "steps": [], "mock": True, "verification": None}
        return await agent.run_agent(text, False, lang, prof if isinstance(prof, dict) else None, None,
                                     (data, mime), emit)

    return _ndjson(work)


@app.post("/api/tts")
async def tts(payload: dict):
    """Text -> MP3 for devices whose browser has no voice for the language (Telugu/Hindi on many laptops)."""
    text = (payload.get("text") or "").strip()
    lang = payload.get("lang") if payload.get("lang") in ttsmod.LANGS else "en"
    if not text:
        raise HTTPException(400, "text required")
    try:
        audio = await asyncio.to_thread(ttsmod.synthesize, text[: ttsmod.MAX_CHARS], lang)
    except Exception as e:
        raise HTTPException(502, f"Voice service unavailable ({type(e).__name__})")
    return Response(audio, media_type="audio/mpeg", headers={"Cache-Control": "public, max-age=86400"})


@app.get("/api/models")
async def list_models():
    """Debug helper: list model ids the configured provider accepts (ids only, no secrets)."""
    _require_debug()
    if not config.CHAT_KEY:
        raise HTTPException(503, "API key for the selected PROVIDER not set")
    async with httpx.AsyncClient(timeout=config.REQUEST_TIMEOUT) as client:
        r = await client.get(
            f"{config.CHAT_BASE}/models", headers={"Authorization": f"Bearer {config.CHAT_KEY}"}
        )
    if r.status_code != 200:
        raise HTTPException(502, f"models list failed: {r.status_code} {r.text[:200]}")
    data = r.json().get("data", [])
    return {"configured": config.CHAT_MODEL, "available": [m.get("id") for m in data]}


@app.get("/api/debug/mandi")
def debug_mandi(commodity: str = "Paddy", district: str = "Kurnool"):
    """Check the live mandi source from the deployed server (no secrets in the output)."""
    _require_debug()
    from . import tools
    out = tools.get_mandi_price(commodity, district)
    out["live_key_configured"] = bool(__import__("os").getenv("DATA_GOV_API_KEY"))
    return out


@app.get("/api/debug/weather")
def debug_weather(place: str = "Kurnool"):
    _require_debug()
    from . import tools
    return tools.get_weather(place, 3)


# Serve the built React app (frontend/dist) from the same service in production.
_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _DIST.exists():
    app.mount("/", StaticFiles(directory=_DIST, html=True), name="frontend")
