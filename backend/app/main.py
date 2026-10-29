from pathlib import Path

import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import agent, config, lang as langmod, meta_client

app = FastAPI(title="Krishi Mitra Agent")

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


@app.get("/api/health")
async def health():
    return {"ok": True, "provider": config.PROVIDER, "model": config.CHAT_MODEL, "api_key_set": bool(config.CHAT_KEY), "mock": config.MOCK_MODE}


@app.post("/api/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    """Telugu voice -> text via Muse Voice Transcribe."""
    if not config.CHAT_KEY and not config.MOCK_MODE:
        raise HTTPException(503, "API key for the selected PROVIDER not set in backend/.env")
    data = await audio.read()
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
async def diagnose(image: UploadFile = File(...), question: str = Form(""), lang: str = Form("auto")):
    """Crop photo (+ optional question) -> Telugu diagnosis via Muse Spark vision."""
    if not config.CHAT_KEY and not config.MOCK_MODE:
        raise HTTPException(503, "API key for the selected PROVIDER not set in backend/.env")
    data = await image.read()
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(413, "Image too large (max 8MB)")
    try:
        answer = await meta_client.diagnose_image(
            data, image.content_type or "image/jpeg", question, lang
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"Meta API error: {e.response.text[:300]}")
    return {"answer": answer}


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
                                      payload.get("profile") if isinstance(payload.get("profile"), dict) else None)
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"Meta API error: {e.response.text[:300]}")


@app.get("/api/models")
async def list_models():
    """Debug helper: list model ids the configured provider accepts (ids only, no secrets)."""
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
    from . import tools
    out = tools.get_mandi_price(commodity, district)
    out["live_key_configured"] = bool(__import__("os").getenv("DATA_GOV_API_KEY"))
    return out


@app.get("/api/debug/weather")
def debug_weather(place: str = "Kurnool"):
    from . import tools
    return tools.get_weather(place, 3)


# Serve the built React app (frontend/dist) from the same service in production.
_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _DIST.exists():
    app.mount("/", StaticFiles(directory=_DIST, html=True), name="frontend")
