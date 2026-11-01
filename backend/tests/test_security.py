"""Offline tests for request hardening and model telemetry. Run from backend/: python tests/test_security.py"""
import os
os.environ["CACHE_TTL_S"] = "0"
os.environ["MOCK_MODE"] = "1"
import asyncio
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402
from app import agent, config, meta_client, security, telemetry  # noqa: E402
from app.main import app  # noqa: E402

c = TestClient(app)


def test_security_headers_everywhere():
    r = c.get("/api/health")
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["x-frame-options"] == "DENY"
    assert "camera=(self)" in r.headers["permissions-policy"] and r.headers["referrer-policy"] == "no-referrer"


def test_request_size_caps():
    assert security.too_big("/api/outcomes/report", str(2 * 1024 * 1024)) and not security.too_big("/api/outcomes/report", "5000")
    assert not security.too_big("/api/diagnose", str(9 * 1024 * 1024)) and security.too_big("/api/diagnose", str(13 * 1024 * 1024))
    assert security.too_big("/api/x", "abc")
    r = c.post("/api/outcomes/report", content=b"{}", headers={"content-length": str(2 * 1024 * 1024), "content-type": "application/json"})
    assert r.status_code in (413, 400)


def test_upload_must_be_a_real_image_by_bytes():
    assert security.is_real_image(b"\xff\xd8\xff\xe0" + b"x" * 20) and security.is_real_image(b"\x89PNG\r\n\x1a\n" + b"x")
    assert security.is_real_image(b"RIFF\x00\x00\x00\x00WEBPVP8 ") and not security.is_real_image(b"<html>evil</html>")
    buf = io.BytesIO()
    Image.new("RGB", (50, 50), "green").save(buf, "JPEG")
    ok = c.post("/api/diagnose", files={"image": ("a.jpg", buf.getvalue(), "image/jpeg")})
    bad = c.post("/api/diagnose", files={"image": ("a.jpg", b"<script>alert(1)</script>", "image/jpeg")})
    assert bad.status_code == 415 and ok.status_code != 415


def test_telemetry_records_model_calls_without_content():
    telemetry.reset()

    @telemetry.timed("test-model")
    async def good():
        return 1

    @telemetry.timed("test-model")
    async def bad():
        raise TimeoutError("secret prompt text")
    asyncio.run(good())
    try:
        asyncio.run(bad())
    except TimeoutError:
        pass
    s = c.get("/api/status").json()["models"]["test-model"]
    assert s["calls"] == 2 and s["ok"] == 1 and s["errors"] == 1 and s["last_error_type"] == "TimeoutError"
    assert "secret" not in str(c.get("/api/status").json())


def test_agent_reports_which_model_served():
    config.MOCK_MODE = False
    config.CHAT_KEY = "k"
    telemetry.reset()

    async def fake_post(base, key, model, messages, extra):
        return {"content": "Hello there", "tool_calls": None}
    meta_client._raw_chat = fake_post
    out = asyncio.run(agent.run_agent("hi", lang="en", profile={"country": "IN"}))
    assert out["served_by"] == config.CHAT_MODEL
    assert telemetry.summary()[config.CHAT_MODEL]["ok"] >= 1
    config.MOCK_MODE = True


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f()
            print("ok", n)
