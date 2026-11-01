"""Offline tests for outcome tracking. Run from backend/: python tests/test_outcomes.py"""
import os
os.environ["MOCK_MODE"] = "1"
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient  # noqa: E402
from app import outcomes  # noqa: E402
from app.main import app  # noqa: E402

R = [
    {"id": "a", "kind": "fertilise", "text": "Apply urea", "done": True, "useful": True, "predicted": {"expense": 1000, "yield_kg": 2000}, "actual": {"expense": 1200, "yield_kg": 1800, "price_per_kg": 20}},
    {"id": "b", "kind": "sell", "text": "Hold maize 2 weeks", "done": False, "useful": None},
    {"id": "c", "kind": "weird", "text": "Irrigate", "done": True, "useful": False, "predicted": {"expense": "abc"}, "actual": {"expense": -5}},
    {"text": "  "}, "junk",
]


def test_report_math():
    o = outcomes.report(R)
    assert o["recommendations"] == 3 and o["done"] == 2 and o["followed_pct"] == 67
    assert o["rated"] == 2 and o["useful"] == 1 and o["useful_pct"] == 50
    acc = {a["metric"]: a for a in o["accuracy"]}
    assert acc["expense"]["error_pct"] == 20.0 and acc["yield_kg"]["error_pct"] == -10.0 and "price_per_kg" not in acc
    assert o["actual_spend"] == 1200 and o["harvest_value"] == 36000 and o["net"] == 34800
    assert o["by_kind"]["other"] == {"total": 1, "done": 1}


def test_no_invented_comparison():
    o = outcomes.report([{"text": "x", "done": True, "actual": {"expense": 50}}])
    assert o["accuracy"] == [] and "No predicted-vs-actual" in o["text"]
    assert "No recommendations" in outcomes.report([])["text"]


def test_endpoint_langs():
    c = TestClient(app)
    d = c.post("/api/outcomes/report", json={"records": R, "lang": "te", "currency": "₹"}).json()
    assert "సీజన్" in d["text"] and "34800" in d["text"]
    assert c.post("/api/outcomes/report", json={}).json()["recommendations"] == 0


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f()
            print("ok", n)
