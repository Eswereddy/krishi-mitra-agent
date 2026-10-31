"""Offline tests for sell_plan, compare_crops, price alerts, weather risk alerts and upload/rate-limit hardening.
Run from backend/: python tests/test_planner.py"""
import asyncio
import os
os.environ["CACHE_TTL_S"] = "0"
os.environ.pop("DATA_GOV_API_KEY", None)
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import advisor, alerts, brief, planner, ratelimit, tools, verify  # noqa: E402

COORDS = {"kurnool": (15.83, 78.04), "adoni": (15.63, 77.27), "guntur": (16.31, 80.44), "nandyal": (15.48, 78.48)}


def _setup(prices):
    planner._geocode = lambda name, state="": COORDS.get(str(name).lower())
    tools.best_markets = lambda c, s="Andhra Pradesh": {"source": "agmarknet-live (data.gov.in)", "highest_first": prices}
    tools.get_mandi_price = lambda c, d="", s="Andhra Pradesh", market="": {
        "source": "agmarknet-live (data.gov.in)",
        "results": [{"commodity": c, "market": "Kurnool", "district": "Kurnool", "modal_price_per_quintal": 7000, "date": "30/10/2026"}]}


def test_sell_plan_ranks_by_money_in_hand_not_headline_price():
    # Guntur pays Rs 100 more per quintal than Kurnool but is ~370 road km away: transport must make the near market win for a small lot.
    _setup([{"market": "Guntur", "district": "Guntur", "modal_price_per_quintal": 7100, "date": "30/10/2026"},
            {"market": "Adoni", "district": "Kurnool", "modal_price_per_quintal": 7150, "date": "30/10/2026"}])
    r = planner.sell_plan("Groundnut", "Kurnool", 10)
    names = [o["market"] for o in r["options"]]
    assert set(names) == {"Guntur", "Adoni", "Kurnool"}
    assert r["options"] == sorted(r["options"], key=lambda o: -o["net_revenue_rs"])
    guntur = next(o for o in r["options"] if o["market"] == "Guntur")
    assert guntur["distance_km"] > 200 and guntur["transport_rs"] > 800
    assert r["best"]["market"] != "Guntur"
    # arithmetic is exact: net = gross - 2% - Rs10/q loading - transport
    o = r["best"]
    gross = o["price_per_quintal"] * 10
    assert o["net_revenue_rs"] == round(gross - gross * 0.02 - 100 - o["transport_rs"])
    assert "assumptions" in r["note"]
    assert verify.verify_answer(f"Best: {o['market']}, you receive ₹{o['net_revenue_rs']:,}.", [{"tool": "sell_plan", "result": r}])["passed"]


def test_sell_plan_errors_are_honest():
    _setup([])
    assert "error" in planner.sell_plan("Groundnut", "Kurnool", 0)
    planner._geocode = lambda name, state="": None
    assert "error" in planner.sell_plan("Groundnut", "Nowhereville", 5)


def _fake_prices(m):
    def fn(commodity, district="", state="Andhra Pradesh", market=""):
        for k, (price, src) in m.items():
            if k in commodity.lower():
                return {"source": src, "results": [{"commodity": commodity, "market": "Kurnool", "modal_price_per_quintal": price}]}
        return {"source": "sample-data", "results": []}
    return fn


def test_compare_crops_profit_math_and_ranking():
    tools.get_mandi_price = _fake_prices({"groundnut": (7000, "agmarknet-live (data.gov.in)"), "paddy": (2300, "agmarknet-live (data.gov.in)"),
                                          "cotton": (7000, "agmarknet-live (data.gov.in)"), "maize": (2200, "agmarknet-live (data.gov.in)"),
                                          "arhar": (7500, "agmarknet-live (data.gov.in)"), "dry chillies": (15000, "agmarknet-live (data.gov.in)")})
    r = planner.compare_crops("Kurnool", "kharif", 2)
    by = {o["crop"]: o for o in r["options"]}
    g = by["Groundnut"]
    assert g["revenue_rs"] == 9 * 7000 * 2 and g["cost_rs"] == 28000 * 2 and g["profit_rs"] == 126000 - 56000
    assert g["profit_per_acre_rs"] == 35000 and g["profit_if_price_falls_10pct_rs"] == round(126000 * 0.9) - 56000
    assert r["options"] == sorted(r["options"], key=lambda o: -o["profit_rs"]) and r["best"] == r["options"][0]
    assert "Bengal gram (Chana)" not in by            # rabi crop is not offered for kharif
    assert verify.verify_answer("Groundnut profit ₹70,000 for 2 acres at ₹7,000 per quintal, if price falls 10%.",
                                [{"tool": "compare_crops", "result": r}])["passed"]


def test_compare_crops_never_uses_sample_prices_as_if_real():
    tools.get_mandi_price = _fake_prices({})                  # everything is sample / empty
    r = planner.compare_crops("Kurnool", "kharif", 1)
    assert all(o["price_basis"] == "msp" for o in r["options"])   # falls back to the government MSP, labelled
    assert "Dry chilli" not in {o["crop"] for o in r["options"]}   # no MSP and no price: skipped, not invented
    assert "error" in planner.compare_crops("Kurnool", "summer", 1) and "error" in planner.compare_crops("Kurnool", "rabi", 0)


def test_alerts_trigger_only_on_live_data():
    live = {"source": "agmarknet-live (data.gov.in)", "results": [{"market": "Kurnool", "modal_price_per_quintal": 7600, "date": "30/10/2026"}]}
    tools.get_mandi_price = lambda c, d="", s="Andhra Pradesh", market="": live
    a = {"id": "a1", "crop": "Groundnut", "district": "Kurnool", "target": 7500, "direction": "above"}
    out = asyncio.run(alerts.check_alerts([a, dict(a, id="a2", target=7700), dict(a, id="a3", target=7700, direction="below"), {"bad": 1}, "x"]))
    assert [(r["id"], r["status"], r["triggered"]) for r in out] == [("a1", "reached", True), ("a2", "waiting", False), ("a3", "reached", True)]
    saved = {"source": "agmarknet-snapshot (saved 2026-10-01)", "results": live["results"]}
    tools.get_mandi_price = lambda c, d="", s="Andhra Pradesh", market="": saved
    r = asyncio.run(alerts.check_alerts([a]))[0]
    assert r["triggered"] is False and r["status"] == "not_live"       # stale data must never say "reached"
    tools.get_mandi_price = lambda c, d="", s="Andhra Pradesh", market="": {"source": "sample-data", "results": []}
    assert asyncio.run(alerts.check_alerts([a]))[0]["status"] == "no_price"
    assert len(asyncio.run(alerts.check_alerts([a] * 20))) == alerts.MAX_ALERTS


def test_alerts_endpoint():
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    r = c.post("/api/alerts/check", json={"alerts": [{"crop": "Paddy", "district": "Kurnool", "target": 2500}]})
    assert r.status_code == 200 and r.json()["count"] == 1 and r.json()["results"][0]["triggered"] is False
    assert c.post("/api/alerts/check", json={}).json() == {"results": [], "count": 0}


def test_weather_risk_alerts_in_all_languages_and_verified():
    days = [{"date": "2026-11-01", "max_c": 41.2, "min_c": 27, "rain_mm": 31.4, "rain_chance_pct": 90, "wind_kmh": 12},
            {"date": "2026-11-02", "max_c": 30, "min_c": 24, "rain_mm": 0, "rain_chance_pct": 5, "wind_kmh": 44}]
    wx = {"source": "open-meteo.com", "place": "Kurnool, Andhra Pradesh", "forecast": days}
    for code in ("en", "te", "hi"):
        lines = brief.risk_lines(brief.T[code], days)
        assert len(lines) == 3, code
        text = "\n".join(lines)
        assert verify.verify_answer(text, [{"tool": "get_weather", "result": wx}])["passed"], (code, text)
    assert brief.risk_lines(brief.T["en"], [{"date": "2026-11-01", "max_c": 33, "rain_mm": 2, "wind_kmh": 10}]) == []


def test_rate_limit_cannot_be_dodged_with_a_fake_forwarded_header():
    class Req:
        def __init__(self, h): self.headers, self.client = h, None
    assert ratelimit.client_ip(Req({"x-forwarded-for": "6.6.6.6, 203.0.113.9"})) == "203.0.113.9"   # proxy-added, not client-supplied
    assert ratelimit.client_ip(Req({"x-forwarded-for": "203.0.113.9"})) == "203.0.113.9"
    ratelimit._hits.clear()
    ratelimit._last_sweep = 0
    ratelimit.check("1.1.1.1", "/api/agent", now=1000.0)
    ratelimit.check("2.2.2.2", "/api/agent", now=1200.0)          # 1.1.1.1 idle for > window: swept
    assert ("1.1.1.1", "/api/agent") not in ratelimit._hits


def test_uploads_are_validated():
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    os.environ["MOCK_MODE"] = "1"
    from app import config
    config.MOCK_MODE = True
    r = c.post("/api/diagnose", files={"image": ("x.txt", b"hello", "text/plain")})
    assert r.status_code == 415
    r = c.post("/api/diagnose", files={"image": ("x.jpg", b"0" * (8 * 1024 * 1024 + 5), "image/jpeg")})
    assert r.status_code == 413
    r = c.post("/api/transcribe", files={"audio": ("a.webm", b"0" * (10 * 1024 * 1024 + 5), "audio/webm")})
    assert r.status_code == 413
    assert c.get("/api/health").json()["tools"] == 27


def test_agent_gives_up_in_the_farmers_language():
    from app import agent, config, meta_client
    config.MOCK_MODE = False

    async def loop_forever(messages, use_open_model=False, tools=None):
        return {"role": "assistant", "content": None, "tool_calls": [{"id": "1", "type": "function",
                "function": {"name": "get_expert_help", "arguments": "{}"}}]}
    orig = meta_client.chat_message
    meta_client.chat_message = loop_forever
    try:
        for code, needle in (("te", "కిసాన్"), ("hi", "किसान"), ("en", "Kisan")):
            r = asyncio.run(agent.run_agent("help", False, code))
            assert needle in r["answer"] and r["verification"]["passed"] is False
    finally:
        meta_client.chat_message = orig
        config.MOCK_MODE = True


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok", fn.__name__)
    print(f"{len(fns)} passed")
