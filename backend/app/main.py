import asyncio
import json
import logging
from pathlib import Path

import httpx
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from . import accounts, admin_eval, safety, auth, agent, explain as explainmod, fieldreport, kg, lessons, memory as memmod2, research, rotation, alerts, brief, cases, claim as claimmod, config, evidence, ledger, meta_extras, outcomes, twin, warning, buyers, irrigation, plan as planmod, lang as langmod, meta_client, ratelimit, security, telemetry, tts as ttsmod, whatsapp

MAX_AUDIO_BYTES = 10 * 1024 * 1024
MAX_IMAGE_BYTES = 8 * 1024 * 1024

app = FastAPI(title="Krishi Mitra Agent")


@app.on_event("startup")
async def _accounts_startup():
    import asyncio
    await asyncio.get_running_loop().run_in_executor(None, accounts.startup_check)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)     # outbound URLs can contain a farmer's place name: keep them out of logs
app.middleware("http")(ratelimit.middleware)
app.middleware("http")(security.middleware)
app.include_router(whatsapp.router)
app.include_router(meta_extras.router)
app.include_router(admin_eval.router)

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
    if not security.is_real_image(data):
        raise HTTPException(415, "That file is not a JPEG, PNG or WebP photo")
    return data, mime


def _require_debug() -> None:
    """Debug endpoints are off in production unless DEBUG_ENDPOINTS=1 (they expose upstream error details)."""
    if not config.DEBUG_ENDPOINTS:
        raise HTTPException(404, "Not found")


@app.get("/api/status")
async def status():
    """Aggregate model-call telemetry (counts, latency, error TYPES) for monitoring. No prompts, answers, keys or farmer data."""
    return {"models": telemetry.summary(), "note": "In-memory since the last restart; one row per model that has been called."}


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


@app.post("/api/plan")
async def week_plan(payload: dict):
    """7-day plan with ranked actions (urgent / this week / good to know). No model call: instant and checkable."""
    profile = payload.get("profile") if isinstance(payload.get("profile"), dict) else {}
    return await planmod.build_plan(profile, payload.get("lang") or "auto")


@app.post("/api/ledger/parse")
async def ledger_parse(payload: dict):
    """One spoken or typed sentence -> one farm money entry for the farmer to confirm (model extracts, rules back it up)."""
    return await ledger.parse_entry(payload.get("text") or "", str(payload.get("crop") or ""))


@app.post("/api/ledger/report")
async def ledger_report(payload: dict):
    """Season report (income, cost, net, cost per acre, where the money went) computed exactly from the entries."""
    return ledger.report(payload.get("entries"), payload.get("acres"), payload.get("lang") or "en")


@app.post("/api/outcomes/report")
async def outcomes_report(payload: dict):
    """Followed-rate, usefulness and predicted-vs-actual accuracy from records kept on the device (arithmetic only)."""
    return outcomes.report(payload.get("records"), payload.get("lang") or "en", str(payload.get("currency") or "")[:5])


@app.post("/api/twin/report")
async def twin_report(payload: dict):
    """Explainable field progress report from the on-device farm twin + the weather it has lived through. Stateless."""
    out = await twin.report(payload.get("twin"), payload.get("lang") or "en")
    if "error" in out:
        raise HTTPException(400, out["error"])
    return out


# ---------------------------------------------------------------- explainability, rotation, knowledge graph, lessons, research, field report
@app.post("/api/explain")
async def explain_answer(payload: dict):
    """Why this answer: evidence per tool, figure trace, re-run verification. Pure code over the answer and tool results the phone already holds."""
    return explainmod.build(str(payload.get("answer") or "")[:6000], payload.get("steps") if isinstance(payload.get("steps"), list) else [], payload.get("lang") or "en")


@app.post("/api/safety/check")
def safety_check(payload: dict):
    """Machine safety warnings from what the operator reports (no sensors; see safety.NOTE)."""
    try:
        return safety.check(payload, payload.get("lang") or "en")
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/rotation/simulate")
def rotation_simulate(payload: dict):
    return rotation.simulate(payload, payload.get("lang") or "en")


@app.get("/api/kg/node")
def kg_node(node: str = "", q: str = "", lang: str = "en"):
    nid = node if node in kg.NODES else kg.find(q or node)
    if not nid:
        raise HTTPException(404, "Nothing found for that")
    return kg.neighbors(nid, lang)


@app.get("/api/kg/crops")
def kg_crops(lang: str = "en"):
    return {"crops": [{"id": n["id"], "display": (n.get("te") if lang == "te" else n.get("hi") if lang == "hi" else None) or n["label"]} for n in kg.NODES.values() if n["kind"] == "crop"],
            "nodes": len(kg.NODES), "edges": len(kg.EDGES)}


@app.post("/api/lessons/build")
def lessons_build(payload: dict):
    out = lessons.build(payload, payload.get("lang") or "en")
    if "error" in out:
        raise HTTPException(404, out["error"])
    return out


@app.post("/api/research/ingest")
async def research_ingest(document: UploadFile = File(...)):
    """Split an uploaded PDF/text into passages for the phone to keep. Nothing is stored on the server."""
    data = await document.read(research.MAX_UPLOAD + 1)
    out = await asyncio.to_thread(research.ingest, data, document.filename or "document")
    if "error" in out:
        raise HTTPException(422, out["error"])
    return out


@app.post("/api/research/ask")
async def research_ask(payload: dict):
    q = str(payload.get("question") or "").strip()[:400]
    if not q:
        raise HTTPException(400, "Empty question")
    return await research.ask(q, payload.get("chunks"), payload.get("lang") or "en")


@app.post("/api/fieldreport/build")
async def fieldreport_build(payload: dict):
    out = await fieldreport.build(payload, payload.get("lang") or "en")
    if "error" in out:
        raise HTTPException(400, out["error"])
    return out


@app.post("/api/memory/followups")
def memory_followups(payload: dict):
    return {"followups": memmod2.followups(payload.get("records"), None, payload.get("lang") or "en")}


# ---------------------------------------------------------------- sign-in: email + password accounts (PostgreSQL), optional Google, guest
def _session(u: dict, acct: bool):
    user = {"sub": u["id"] if acct else u["sub"], "email": u["email"], "name": u["name"], "picture": u.get("picture", ""), "acct": acct}
    return {"user": {"email": user["email"], "name": user["name"], "picture": user["picture"], "account": acct}, "token": auth.issue(user)}


def _acct_user(request: Request):
    t = auth.read(auth.bearer(request.headers.get("authorization", "")))
    if not t:
        raise HTTPException(401, "Not signed in")
    return t


@app.get("/api/auth/config")
def auth_config():
    return {"google_client_id": auth.client_id() or None, "accounts": accounts.enabled()}


@app.post("/api/auth/register")
def auth_register(payload: dict):
    if not accounts.enabled():
        raise HTTPException(503, "Accounts are not set up on this server yet")
    try:
        return _session(accounts.register(payload.get("email"), payload.get("password"), payload.get("name")), True)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except LookupError as e:
        raise HTTPException(409, str(e))
    except Exception:
        raise HTTPException(503, "Accounts are temporarily unavailable")


@app.post("/api/auth/login")
def auth_login(payload: dict):
    if not accounts.enabled():
        raise HTTPException(503, "Accounts are not set up on this server yet")
    try:
        return _session(accounts.login(payload.get("email"), payload.get("password")), True)
    except PermissionError as e:
        raise HTTPException(401, str(e))
    except TimeoutError as e:
        raise HTTPException(429, str(e))
    except Exception:
        raise HTTPException(503, "Accounts are temporarily unavailable")


@app.post("/api/auth/google")
async def auth_google(payload: dict):
    try:
        g = await auth.verify_google(str(payload.get("credential") or ""))
    except ValueError as e:
        raise HTTPException(401, str(e))
    if accounts.enabled():
        try:
            return _session({**accounts.google_user(g), "picture": g.get("picture", "")}, True)
        except Exception:
            raise HTTPException(503, "Accounts are temporarily unavailable")
    return _session(g, False)


@app.get("/api/auth/me")
def auth_me(request: Request):
    u = _acct_user(request)
    if u.get("acct"):
        try:
            row = accounts.store().by_id(u["sub"])
        except Exception:
            row = {"email": u.get("email"), "name": u.get("name")}     # database briefly down: keep the session
        if not row:
            raise HTTPException(401, "This account no longer exists")
    return {"user": {**{k: u.get(k) for k in ("email", "name", "picture")}, "account": bool(u.get("acct"))}}


@app.delete("/api/auth/account")
def auth_delete(request: Request):
    u = _acct_user(request)
    if not u.get("acct"):
        raise HTTPException(400, "This sign-in has no stored account")
    try:
        accounts.store().delete(u["sub"])
    except Exception:
        raise HTTPException(503, "Accounts are temporarily unavailable")
    return {"deleted": True}


@app.post("/api/warnings/check")
async def warnings_check(payload: dict):
    """Crop-specific early warnings (heat, cold, heavy rain, wind, disease weather) with preventive actions. Live forecast."""
    out = await warning.check(payload.get("crop") or "", payload.get("place") or "", str(payload.get("country") or "").upper()[:3],
                              payload.get("sowing_date") or "", payload.get("lang") or "en")
    if "error" in out and out["error"] == "place is needed":
        raise HTTPException(400, out["error"])
    return out


@app.post("/api/buyers/compare")
async def buyers_compare(payload: dict):
    """Net income of each buyer offer (price x quantity - commission - transport - other). Verified only if in the registry."""
    out = buyers.compare(payload.get("offers"), payload.get("quantity"), payload.get("unit") or "quintal", payload.get("reference_price"),
                         payload.get("lang") or "en", str(payload.get("currency") or "")[:5])
    if "error" in out:
        raise HTTPException(400, out["error"])
    return out


@app.get("/api/buyers/registry")
async def buyers_registry():
    return {"verified": buyers.verified_list(), "note": "Only buyers marked verified in the registry are listed."}


@app.post("/api/irrigation/report")
async def irrigation_report(payload: dict):
    """Water volume, pumping cost and savings against the farmer's own baseline; this week's need priced at their cost per mm."""
    out = await irrigation.report(payload, payload.get("lang") or "en")
    if "error" in out:
        raise HTTPException(400, out["error"])
    return out


@app.post("/api/claim/evidence")
async def claim_evidence(payload: dict):
    """Printable evidence file (HTML, save as PDF) from the farmer's own evidence, checklist and claim timeline. No approval promises."""
    out = evidence.build(payload, payload.get("lang") or "en")
    if "error" in out:
        raise HTTPException(400, out["error"])
    return out


@app.post("/api/claim/draft")
async def claim_draft(payload: dict):
    """Crop-loss kit: 72-hour deadline, checklist, helplines and a ready message (PMFBY)."""
    return claimmod.build_claim(payload.get("profile") if isinstance(payload.get("profile"), dict) else {},
                                payload.get("loss") if isinstance(payload.get("loss"), dict) else {}, payload.get("lang") or "en")


@app.post("/api/case/build")
async def case_build(payload: dict):
    """Structured expert case from scan + symptoms + weather + profile. Needs the farmer's consent; nothing is stored here."""
    cons = payload.get("consent")
    if not isinstance(cons, dict) or not cons.get("share_details"):
        raise HTTPException(400, "consent.share_details is required to build a case")
    return await cases.build_case(payload, payload.get("lang") or "en")


@app.get("/api/expert/contacts")
async def expert_contacts(lang: str = "en", country: str = "", text: str = ""):
    return cases.contacts(lang, country, text[:3000])


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
                                      payload.get("history") if isinstance(payload.get("history"), list) else None,
                                      None, None, payload.get("memory") if payload.get("memory_consent") is True else None)
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
    memory = payload.get("memory") if payload.get("memory_consent") is True else None
    return _ndjson(lambda emit: agent.run_agent(question, False, payload.get("lang") or "auto", profile, history,
                                                None, emit, memory))


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
