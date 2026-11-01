"""Offline tests for buyer offer comparison. Run from backend/: python tests/test_buyers.py"""
import os
os.environ["MOCK_MODE"] = "1"
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient  # noqa: E402
from app import buyers  # noqa: E402
from app.main import app  # noqa: E402

REG = {"fpo1": {"id": "fpo1", "name": "Kurnool FPO", "verified": True, "verified_by": "Agri officer visit", "verified_on": "2026-10-01"},
       "x2": {"id": "x2", "name": "Pending", "verified": False}}
buyers.registry = lambda: REG
OFFERS = [
    {"buyer": "Trader A", "price": 2400, "commission_pct": 2, "transport_cost": 500, "other_costs": 100, "payment_days": 15, "asks_advance": True},
    {"buyer": "FPO", "buyer_id": "fpo1", "price": 2300, "commission_pct": 0, "transport_cost": 300, "payment_days": 2},
    {"buyer": "Fake verified", "buyer_id": "x2", "price": 3200},
    {"buyer": "Name only match", "buyer_id": "Kurnool FPO", "price": 2000},
    {"buyer": "no price"},
]


def test_net_math_and_ranking():
    o = buyers.compare(OFFERS, 10, "quintal", reference_price=2500, lang="en", currency="Rs")
    rows = {r["buyer"]: r for r in o["offers"]}
    assert len(rows) == 4
    a = rows["Trader A"]
    assert a["gross"] == 24000 and a["commission"] == 480 and a["net"] == 24000 - 480 - 500 - 100
    assert a["net_per_kg"] == round(22920 / 1000, 2)
    assert rows["FPO"]["net"] == 22700
    assert [r["net"] for r in o["offers"]] == sorted((r["net"] for r in o["offers"]), reverse=True)
    assert o["quantity_kg"] == 1000


def test_verification_never_mislabelled():
    rows = {r["buyer"]: r for r in buyers.compare(OFFERS, 10)["offers"]}
    assert rows["FPO"]["status"] == "verified" and "Agri officer visit" in rows["FPO"]["notes"][0]
    assert rows["Fake verified"]["status"] == "unverified"       # registry entry exists but verified=False
    assert rows["Name only match"]["status"] == "unverified"     # name is not an id
    assert rows["Trader A"]["status"] == "unverified"


def test_risk_flags():
    o = buyers.compare(OFFERS, 10, reference_price=2500)
    rows = {r["buyer"]: r for r in o["offers"]}
    assert {"unverified", "advance", "slow_payment"} <= set(rows["Trader A"]["flags"])
    assert "too_good" in rows["Fake verified"]["flags"] and rows["Fake verified"]["vs_reference_pct"] == 28.0
    assert "slow_payment" not in rows["FPO"]["flags"]
    assert o["best_is_risky"] is True


def test_units_and_errors():
    assert buyers.compare([{"price": 20}], 500, "kg")["offers"][0]["gross"] == 10000
    assert buyers.compare([{"price": 20000}], 2, "tonne")["quantity_kg"] == 2000
    assert "error" in buyers.compare([{"price": 1}], 0)
    assert "error" in buyers.compare([{"buyer": "x"}], 5)


def test_endpoints():
    c = TestClient(app)
    assert c.post("/api/buyers/compare", json={"offers": [{"price": 1}], "quantity": 0}).status_code == 400
    d = c.post("/api/buyers/compare", json={"offers": OFFERS, "quantity": 10, "lang": "te"}).json()
    assert "ధృవీకరించని" in d["offers"][0]["notes"][-1] or any("ధృవీకరించని" in n for r in d["offers"] for n in r["notes"])
    assert [b["id"] for b in c.get("/api/buyers/registry").json()["verified"]] == ["fpo1"]


def test_shipped_registry_has_nobody_verified():
    import importlib
    importlib.reload(buyers)
    assert buyers.verified_list() == []


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f()
            print("ok", n)
