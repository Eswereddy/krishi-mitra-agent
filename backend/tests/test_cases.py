"""Offline tests for expert escalation cases. Run from backend/: python tests/test_cases.py"""
import os
os.environ["CACHE_TTL_S"] = "0"
os.environ["MOCK_MODE"] = "1"
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient  # noqa: E402
from app import cases, ratelimit, tools  # noqa: E402
from app.main import app  # noqa: E402

c = TestClient(app)
SCAN = {"severity_pct": 31.0, "band": "severe", "reliability": "clear", "confidence": {"mean": 0.9},
        "escalation": {"needed": True, "reasons": ["severe_damage"]}}


def fake_wx(place, days=5):
    return {"forecast": [{"max_c": 33, "rain_mm": 2.0}] * 5}


def test_urgency_rules():
    assert cases.urgency([], SCAN)[0] == "high"
    assert cases.urgency(["spreading_fast"], {})[0] == "high"
    assert cases.urgency([], {"reliability": "retake", "escalation": {"needed": True, "reasons": ["not_reliable"]}})[0] == "medium"
    assert cases.urgency(["yellowing"], {"reliability": "clear", "escalation": {"needed": False}})[0] == "low"


def test_consent_required():
    r = c.post("/api/case/build", json={"symptoms": ["wilting"], "consent": {}})
    assert r.status_code == 400
    r = c.post("/api/case/build", json={"symptoms": ["wilting"]})
    assert r.status_code == 400


def test_case_privacy_and_content():
    tools.get_weather = fake_wx
    body = {"lang": "te", "symptoms": ["spots_on_leaves", "bogus", "whole_field"], "note": "x" * 900, "scan": SCAN,
            "profile": {"crop": "tomato", "place": "Kurnool", "country": "IN", "name": "Ravi", "phone": "9999999999", "sowing_date": "2026-09-01"},
            "consent": {"share_details": True, "share_location": False, "share_photo": False}}
    d = c.post("/api/case/build", json=body).json()
    assert d["id"].startswith("KM-") and d["urgency"] == "high"
    assert d["symptoms"] == ["spots_on_leaves", "whole_field"] and len(d["note"]) == 500
    blob = json.dumps(d, ensure_ascii=False)
    assert "Ravi" not in blob and "9999999999" not in blob and "Kurnool" not in blob
    assert d["weather"] is None and d["photo_consented"] is False
    assert "31.0%" in d["summary_text"] and "నిర్ధారణ కాదు" in d["summary_text"]
    body["consent"]["share_location"] = True
    d2 = c.post("/api/case/build", json=body).json()
    assert d2["farmer"]["place"] == "Kurnool" and d2["weather"]["rain_next_5_days_mm"] == 10.0
    assert "Kurnool" in d2["summary_text"]


def test_contacts():
    os.environ["EXPERT_CONTACTS"] = json.dumps([{"name": "Dr Rao", "type": "whatsapp", "value": "+91 98765 43210", "languages": ["te"]},
                                                {"name": "Hindi desk", "type": "email", "value": "a@b.org", "languages": ["hi"]}])
    d = c.get("/api/expert/contacts", params={"lang": "te", "text": "hello world", "country": "IN"}).json()
    assert [e["name"] for e in d["experts"]] == ["Dr Rao"] and d["experts"][0]["link"] == "https://wa.me/919876543210?text=hello%20world"
    os.environ["EXPERT_CONTACTS"] = "not json"
    d = c.get("/api/expert/contacts", params={"lang": "en", "country": "KE"}).json()
    assert d["experts"] == [] and not d["configured"] and "local" in d["fallback"]
    del os.environ["EXPERT_CONTACTS"]


def test_rate_limit_registered():
    assert "/api/case" in ratelimit.LIMITS


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f()
            print("ok", n)
