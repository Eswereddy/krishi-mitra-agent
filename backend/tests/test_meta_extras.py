"""Offline tests for the Meta Model API extras (SAM 3.1 leaf scan, Muse Image card, Muse Voice Transcribe).
The Meta API is replaced by a mock transport: python tests/test_meta_extras.py from backend/."""
import asyncio
import base64
import io
import json
import os
os.environ["CACHE_TTL_S"] = "0"
os.environ["MOCK_MODE"] = "1"
os.environ.pop("MODEL_API_KEY", None)
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx  # noqa: E402
from PIL import Image  # noqa: E402
from meta_sam_parser._mask_codec import _encode_raster  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from app import meta_extras, meta_models as mm  # noqa: E402
from app.main import app  # noqa: E402

W, H = 400, 300


def _record(oid, x1, y1, x2, y2, fill, conf=0.9):
    """One SAM record: box in source pixels + a box-local mask (here 20x20, `fill` = fraction of columns set)."""
    mw = mh = 20
    ras = [1 if x < mw * fill else 0 for _y in range(mh) for x in range(mw)]
    return f"{oid}<|box;x1={x1};y1={y1};x2={x2};y2={y2};w={W};h={H};c={conf}|><|mask;x=0;y=0;data={mh},{mw},{_encode_raster(ras, mw, mh)}|>"


LEAF = "<0f>" + _record(1, 0, 0, 399, 299, 1.0)                                  # whole photo is leaf
LESIONS = "<0f>" + _record(1, 100, 100, 199, 199, 1.0) + "," + _record(2, 300, 50, 349, 99, 0.5)
LOW_CONF = "<0f>" + _record(1, 100, 100, 199, 199, 1.0, conf=0.1)


def _photo(color=(60, 140, 60)) -> bytes:
    b = io.BytesIO()
    Image.new("RGB", (W, H), color).save(b, "JPEG")
    return b.getvalue()


def test_damage_percentage_is_arithmetic_on_the_masks():
    base = Image.open(io.BytesIO(_photo()))
    r = mm.measure(LESIONS, LEAF, base)
    # lesion 1: 100x100 px fully set = 10000; lesion 2: 50x50 box, half the columns = 1250 px -> 11250 / 120000
    assert r["found"] and r["basis"] == "leaf" and r["spot_count"] == 2
    assert abs(r["severity_pct"] - 9.4) <= 0.2 and r["band"] == "moderate"
    assert r["overlay"].startswith("data:image/jpeg;base64,")
    assert r["spots"][0]["box"] == [100, 100, 200, 200] and r["spots"][0]["confidence"] == 0.9


def test_no_lesions_low_confidence_and_missing_leaf():
    base = Image.open(io.BytesIO(_photo()))
    assert mm.measure("", LEAF, base)["found"] is False
    assert mm.measure(LOW_CONF, LEAF, base)["found"] is False            # below the confidence floor: ignored
    r = mm.measure(LESIONS, "", base)                                    # no leaf found: % of the whole photo, labelled
    assert r["basis"] == "photo" and abs(r["severity_pct"] - 9.4) <= 0.2


def _transport(handler):
    mm._TRANSPORT = httpx.MockTransport(handler)


def test_sam_request_shape_and_sse_parsing():
    seen = {}

    def handler(req: httpx.Request):
        seen["body"], seen["auth"], seen["accept"] = json.loads(req.content), req.headers["authorization"], req.headers["accept"]
        half = len(LESIONS) // 2
        sse = "".join(f"data: {json.dumps({'type': 'response.output_text.delta', 'delta': d})}\n\n" for d in (LESIONS[:half], LESIONS[half:]))
        sse += 'data: {"type": "response.completed"}\n\n'
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, text=sse)
    _transport(handler)
    os.environ["MODEL_API_KEY"] = "test-key"
    raw = asyncio.run(mm.segment(_photo(), "diseased leaf spot"))
    assert raw == LESIONS                                                 # chunks split mid-payload are rejoined
    b = seen["body"]
    assert b["model"] == "sam-3.1" and b["stream"] is True and seen["auth"] == "Bearer test-key" and seen["accept"] == "text/event-stream"
    parts = b["input"][0]["content"]
    assert parts[0] == {"type": "input_text", "text": "diseased leaf spot"} and parts[1]["image_url"].startswith("data:image/jpeg;base64,")


def test_leaf_scan_endpoint_end_to_end_and_errors():
    c = TestClient(app)
    os.environ.pop("MODEL_API_KEY", None)
    assert c.post("/api/leaf-scan", files={"image": ("a.jpg", _photo(), "image/jpeg")}).status_code == 503

    def handler(req: httpx.Request):
        prompt = json.loads(req.content)["input"][0]["content"][0]["text"]
        text = LESIONS if prompt == "diseased leaf spot" else LEAF
        return httpx.Response(200, text=f"data: {json.dumps({'type': 'response.output_text.delta', 'delta': text})}\n\n")
    _transport(handler)
    os.environ["MODEL_API_KEY"] = "test-key"
    r = c.post("/api/leaf-scan", files={"image": ("a.jpg", _photo(), "image/jpeg")})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["found"] and j["band"] == "moderate" and j["needs_expert"] is False and j["model"] == "sam-3.1"
    assert "not a diagnosis" in j["note"] and "pesticide" not in j["note"].lower().replace("never names a pesticide", "")
    assert c.post("/api/leaf-scan", files={"image": ("a.txt", b"hi", "text/plain")}).status_code == 415
    assert c.post("/api/leaf-scan", files={"image": ("a.jpg", b"not an image", "image/jpeg")}).status_code == 400
    _transport(lambda req: httpx.Response(500, text="boom"))
    assert c.post("/api/leaf-scan", files={"image": ("a.jpg", _photo(), "image/jpeg")}).status_code == 502


def test_advice_card_uses_only_the_answers_own_words():
    c = TestClient(app)
    os.environ.pop("MODEL_API_KEY", None)
    assert c.post("/api/advice-card", json={"text": "hi"}).status_code == 503
    seen = {}
    png = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(png, "PNG")

    def handler(req: httpx.Request):
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(png.getvalue()).decode()}]})
    _transport(handler)
    os.environ["MODEL_API_KEY"] = "test-key"
    r = c.post("/api/advice-card", json={"text": "**Sell groundnut now.** Price is ₹7,150 per quintal at Adoni. Rain is likely.", "lang": "en", "crop": "Groundnut"})
    assert r.status_code == 200 and r.json()["image"].startswith("data:image/png;base64,")
    assert r.json()["text"] == "Sell groundnut now."
    b = seen["body"]
    assert b["model"] == "muse-image-1.0" and b["response_format"] == "b64_json" and "Sell groundnut now." in b["prompt"]
    assert "7,150" not in b["prompt"] and "English" in b["prompt"]
    assert c.post("/api/advice-card", json={"text": "  "}).status_code == 400


def test_headline_helper():
    assert meta_extras.headline("• first line. second") == "first line."
    assert len(meta_extras.headline("word " * 100)) <= 110
    assert meta_extras.headline("") == ""


def test_asr_prefers_muse_voice_and_falls_back():
    c = TestClient(app)
    os.environ["MODEL_API_KEY"] = "test-key"
    seen = {}

    async def fake_wav(data):
        return b"RIFFwav", "audio/wav"
    meta_extras.meta_client._to_wav = fake_wav

    def ok(req: httpx.Request):
        seen["ct"] = req.headers["content-type"]
        seen["body"] = req.content
        return httpx.Response(200, json={"sessionId": "s", "transcript": " వేరుశనగ ధర ఎంత? ", "audioDurationMs": 1500, "turns": []})
    _transport(ok)
    r = c.post("/api/asr", files={"audio": ("q.webm", b"x" * 100, "audio/webm")})
    assert r.status_code == 200 and r.json() == {"text": "వేరుశనగ ధర ఎంత?", "engine": "muse-voice-transcribe-1.0"}
    assert seen["ct"].startswith("multipart/form-data") and b"muse-voice-transcribe-1.0" in seen["body"] and b"Telugu" in seen["body"]
    _transport(lambda req: httpx.Response(200, json={"transcript": ""}))
    assert c.post("/api/asr", files={"audio": ("q.webm", b"x" * 100, "audio/webm")}).status_code == 422   # silence: ask to repeat
    # Meta API down -> existing Spark Open path (mock mode here) still answers
    _transport(lambda req: httpx.Response(503, text="down"))
    r = c.post("/api/asr", files={"audio": ("q.webm", b"x" * 100, "audio/webm")})
    assert r.status_code == 200 and r.json()["engine"] != "muse-voice-transcribe-1.0"
    os.environ.pop("MODEL_API_KEY", None)
    assert c.post("/api/asr", files={"audio": ("q.webm", b"x" * (10 * 1024 * 1024 + 5), "audio/webm")}).status_code == 413


def test_meta_models_status():
    c = TestClient(app)
    os.environ.pop("MODEL_API_KEY", None)
    j = c.get("/api/meta-models").json()
    assert j["sam"]["model"] == "sam-3.1" and j["sam"]["configured"] is False and j["muse_image"]["model"] == "muse-image-1.0"
    os.environ["MODEL_API_KEY"] = "k"
    assert c.get("/api/meta-models").json()["muse_voice_transcribe"]["configured"] is True
    os.environ.pop("MODEL_API_KEY", None)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok", fn.__name__)
    mm._TRANSPORT = None
    print(f"{len(fns)} passed")
