"""Offline tests for the streaming endpoint, trend tool and TTS errors: python tests/test_stream.py from backend/."""
import json
import os
import sys
from pathlib import Path

os.environ["MOCK_MODE"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient  # noqa: E402

from app import tools  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


def test_agent_stream_emits_steps_then_final():
    with client.stream("POST", "/api/agent/stream", json={"question": "paddy price?", "lang": "en"}) as r:
        events = [json.loads(line) for line in r.iter_lines() if line]
    types = [e["type"] for e in events]
    assert types[0] == "tool" and types[-1] == "final", types
    assert "tool_done" in types
    assert events[-1]["data"]["steps"], "final event carries the steps"


def test_stream_validates_input():
    assert client.post("/api/agent/stream", json={"question": " "}).status_code == 400


def test_tts_validates_and_reports_failure():
    assert client.post("/api/tts", json={"text": ""}).status_code == 400
    from app import tts
    tts.synthesize.cache_clear()
    orig = tts.synthesize
    def boom(text, lang): raise RuntimeError("offline")
    import app.main as m
    m.ttsmod.synthesize = boom
    try:
        assert client.post("/api/tts", json={"text": "hi", "lang": "te"}).status_code == 502
    finally:
        m.ttsmod.synthesize = orig


def test_price_trend_from_live_rows():
    os.environ["DATA_GOV_API_KEY"] = "k"
    rec = lambda d, p, m="Kurnool": {"commodity": "Groundnut", "market": m, "district": "Kurnool",
                                    "arrival_date": d, "modal_price": str(p)}
    rows = [rec("20/10/2026", 6000), rec("24/10/2026", 6200), rec("28/10/2026", 6400), rec("28/10/2026", 5000, "Adoni")]
    orig = tools._fetch_live
    tools._fetch_live = lambda *a: (rows, "")
    try:
        out = tools.get_price_trend("Groundnut", district="Kurnool")
    finally:
        tools._fetch_live = orig
    assert out["market"] == "Kurnool" and out["trend"] == "rising" and out["change_pct"] == 6.7
    assert [x["modal_price_per_quintal"] for x in out["series"]] == [6000, 6200, 6400]


def test_price_trend_without_key_is_an_error_not_invented():
    os.environ.pop("DATA_GOV_API_KEY", None)
    assert "error" in tools.get_price_trend("Groundnut")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
