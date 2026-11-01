"""Offline tests for the insurance evidence file. Run from backend/: python tests/test_evidence.py"""
import os
os.environ["MOCK_MODE"] = "1"
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient  # noqa: E402
from app import evidence, security  # noqa: E402
from app.main import app  # noqa: E402

IMG = "data:image/jpeg;base64,/9j/4AAQSkZJRg=="
P = {"profile": {"country": "IN", "district": "Kurnool", "state": "Andhra Pradesh", "main_crop": "Groundnut"},
     "loss": {"cause": "hailstorm", "occurred_at": "2026-10-20T10:00:00+00:00", "crop": "Groundnut", "acres": 2},
     "policy_no": "POL123", "complaint_no": "C-9",
     "checklist": [{"text": "Photos of the field", "done": True}, {"text": "Land records", "done": False}],
     "evidence": [{"kind": "photo", "label": "Field east side", "taken_at": "2026-10-20T11:00:00+00:00", "data_url": IMG}, {"kind": "note", "label": "Neighbour also lost crop"}],
     "timeline": [{"stage": "documents_submitted", "date": "2026-10-23T09:00:00+00:00", "note": "Gave to bank"}, {"stage": "reported", "date": "2026-10-21T08:00:00+00:00", "note": "Called 14447"}],
     "include_photos": True}


def test_report_content_and_72h_arithmetic():
    o = evidence.build(P)
    assert o["window"] == {"hours_to_report": 22.0, "within_72h": True}
    assert o["current_stage"] == "documents_submitted" and o["checklist_done"] == 1 and o["checklist_total"] == 2 and o["photos_embedded"] == 1
    h = o["html"]
    assert "POL123" in h and "within the 72-hour window" in h and h.index("Loss reported") < h.index("Documents submitted")
    assert "does not guarantee any claim" in h and "✖ Land records" in h and IMG in h
    late = evidence.build({**P, "timeline": [{"stage": "reported", "date": "2026-10-25T10:00:00+00:00"}]})
    assert late["window"]["within_72h"] is False and "after the 72-hour window" in late["html"]
    area = evidence.build({**P, "loss": {**P["loss"], "cause": "other"}})
    assert area["window"] is None and "does not apply" in area["html"]


def test_escaping_and_photo_validation():
    bad = {**P, "policy_no": "<script>alert(1)</script>", "evidence": [
        {"kind": "photo", "label": "<img src=x onerror=1>", "data_url": "javascript:alert(1)"},
        {"kind": "photo", "label": "big", "data_url": "data:image/jpeg;base64," + "A" * 200000},
        {"kind": "photo", "label": "svg", "data_url": "data:image/svg+xml;base64,PHN2Zz4="}]}
    o = evidence.build(bad)
    assert "<script>" not in o["html"] and "&lt;script&gt;" in o["html"] and "onerror=1>" not in o["html"]
    assert o["photos_embedded"] == 0 and "javascript:" not in o["html"] and "svg+xml" not in o["html"]
    assert evidence.build({**P, "include_photos": False})["photos_embedded"] == 0


def test_photo_cap_and_validation_errors():
    many = {**P, "evidence": [{"kind": "photo", "label": str(i), "data_url": IMG} for i in range(10)]}
    assert evidence.build(many)["photos_embedded"] == evidence.MAX_PHOTOS
    assert "error" in evidence.build({"loss": {}})
    c = TestClient(app)
    assert c.post("/api/claim/evidence", json={"loss": {"cause": "fire"}}).status_code == 400
    ok = c.post("/api/claim/evidence", json={**P, "lang": "te"}).json()
    assert "పంట నష్టం ఆధారాల ఫైల్" in ok["html"] and ok["filename"] == "krishi-mitra-claim-20261020.html" and ok["stage_text"]


def test_bigger_json_allowed_only_for_evidence():
    assert not security.too_big("/api/claim/evidence", str(1_500_000)) and security.too_big("/api/claim/draft", str(1_500_000))
    assert security.too_big("/api/claim/evidence", str(3_000_000))


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f()
            print("ok", n)
