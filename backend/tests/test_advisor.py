"""Offline tests for the advisor tools: python tests/test_advisor.py from backend/."""
import os
os.environ["CACHE_TTL_S"] = "0"
os.environ.pop("DATA_GOV_API_KEY", None)
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import advisor, tools, verify  # noqa: E402


def test_msp_current_and_aliases():
    g = advisor.get_msp("Groundnut")
    assert g["current"]["msp_price_per_quintal"] == 7517 and "Kharif" in g["current"]["season"]
    assert advisor.get_msp("rice")["current"]["msp_price_per_quintal"] == 2441
    w = advisor.get_msp("Wheat")
    assert w["current"]["msp_price_per_quintal"] == 2610 and w["other_seasons"][0]["msp_price_per_quintal"] == 2585
    assert advisor.get_msp("Paddy(Common)")["current"]["msp_price_per_quintal"] == 2441


def test_msp_unknown_crop_is_an_error_not_a_guess():
    assert "error" in advisor.get_msp("tomato")


def test_net_market_value_is_exact():
    r = advisor.net_market_value("Groundnut", 10, 7000, distance_km=100)
    assert r["gross_revenue_rs"] == 70000 and r["commission_rs"] == 1400 and r["loading_rs"] == 100
    assert r["transport_rs"] == 300 and r["net_revenue_rs"] == 68200 and r["net_price_per_quintal"] == 6820
    assert r["net_vs_msp_rs_per_quintal"] == 6820 - 7517 and r["assumed"]["commission_pct"] == 2.0
    assert "error" in advisor.net_market_value("Paddy", 0, 2000)


def test_far_market_can_lose_to_near_market():
    near = advisor.net_market_value("Cotton", 20, 7900, distance_km=10)["net_revenue_rs"]
    far = advisor.net_market_value("Cotton", 20, 8000, distance_km=400)["net_revenue_rs"]
    assert near > far


def _fake_weather(days):
    def fn(place, n=3):
        return {"source": "open-meteo.com", "place": "Kurnool, Andhra Pradesh", "forecast": days}
    return fn


def test_spray_window_rules():
    tools.get_weather = _fake_weather([
        {"date": "2026-10-30", "max_c": 33, "min_c": 22, "rain_mm": 8, "rain_chance_pct": 80, "wind_kmh": 8},
        {"date": "2026-10-31", "max_c": 32, "min_c": 22, "rain_mm": 0, "rain_chance_pct": 10, "wind_kmh": 22},
        {"date": "2026-11-01", "max_c": 36, "min_c": 24, "rain_mm": 0, "rain_chance_pct": 5, "wind_kmh": 9},
        {"date": "2026-11-02", "max_c": 31, "min_c": 23, "rain_mm": 0, "rain_chance_pct": 5, "wind_kmh": None},
    ])
    r = advisor.spray_window("Kurnool", 4)
    ok = [d["suitable"] for d in r["days"]]
    assert ok == [False, False, True, True] and r["best_day"] == "2026-11-01"
    assert "early morning" in r["days"][2]["advice"] and r["days"][3]["advice"] == "good day to spray"


def test_spray_window_passes_weather_error_through():
    tools.get_weather = lambda place, n=3: {"error": "weather service unavailable"}
    assert "error" in advisor.spray_window("Kurnool")


def test_lookup_problem_matches_and_never_names_chemicals():
    r = advisor.lookup_problem("Groundnut", "brown spots with a yellow ring and leaves are falling")
    assert r["matches"][0]["name"].startswith("Leaf spot")
    r2 = advisor.lookup_problem("paddy", "round dry patches, brown insects at the base of the plants")
    assert "planthopper" in r2["matches"][0]["name"].lower() and r2["needs_expert"] is True
    bad = ("mg", " ml", "per litre", "dose of", "imidacloprid", "mancozeb", "chlorpyrifos")
    import json
    blob = json.dumps(r2).lower() + json.dumps(r).lower()
    assert not any(b in blob for b in bad)
    assert advisor.lookup_problem("cotton", "xyz")["needs_expert"] is True
    assert advisor.lookup_problem("paddy", "pink worm in bolls")["matches"] == []   # right words, wrong crop


def test_problem_kb_is_well_formed():
    import json
    kb = json.loads((Path(advisor.DATA) / "problems.json").read_text())
    ids = [p["id"] for p in kb]
    assert len(ids) == len(set(ids)) >= 18
    for p in kb:
        assert p["urgency"] in ("low", "medium", "high") and p["what_to_do"] and p["keywords"] and p["crops"]


def _patch_market(trend, rows):
    tools.get_price_trend = lambda *a, **k: trend
    tools.best_markets = lambda *a, **k: {"source": "agmarknet-live (data.gov.in)", "highest_first": rows}


def _trend(first, last, kind):
    return {"source": "agmarknet-live (data.gov.in)", "market": "Kurnool", "trend": kind, "change_pct": round((last - first) / first * 100, 1),
            "series": [{"date": "01/10/2026", "modal_price_per_quintal": first}, {"date": "28/10/2026", "modal_price_per_quintal": last}]}


def test_hold_or_sell_decisions():
    rows = [{"market": "Adoni", "modal_price_per_quintal": 7800}]
    _patch_market(_trend(7000, 7900, "rising"), rows)
    r = advisor.hold_or_sell("Groundnut")
    assert r["recommendation"] == "hold_short" and r["current_vs_msp_rs_per_quintal"] == 7900 - 7517
    assert r["best_market"]["extra_over_current_rs_per_quintal"] == -100
    _patch_market(_trend(8000, 7600, "falling"), rows)
    assert advisor.hold_or_sell("Groundnut")["recommendation"] == "sell_now"
    _patch_market(_trend(7300, 7300, "steady"), rows)
    assert advisor.hold_or_sell("Groundnut")["recommendation"] == "use_procurement_or_wait"
    _patch_market(_trend(80, 100, "rising"), [])
    assert advisor.hold_or_sell("Tomato")["recommendation"] == "sell_now"          # perishable: never wait
    _patch_market({"error": "no price history found for this crop"}, [])
    assert advisor.hold_or_sell("Groundnut")["recommendation"] == "not_enough_data"
    assert "disclaimer" in advisor.hold_or_sell("Groundnut")


def test_registered_with_agent_and_verification_accepts_msp_gaps():
    names = {s["function"]["name"] for s in tools.TOOL_SPECS}
    assert {"get_msp", "net_market_value", "spray_window", "lookup_problem", "hold_or_sell"} <= names
    assert tools.run_tool("get_msp", {"commodity": "paddy"})["current"]["msp_price_per_quintal"] == 2441
    assert "error" in tools.run_tool("get_msp", {})
    steps = [{"tool": "net_market_value", "args": {}, "result": advisor.net_market_value("Groundnut", 10, 7000, 100)}]
    assert verify.verify_answer("Net Rs 6,820 per quintal, Rs 697 below MSP of Rs 7,517 per quintal.", steps)["passed"]
    assert not verify.verify_answer("Net Rs 9,999 per quintal.", steps)["passed"]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok", fn.__name__)
    print(f"{len(fns)} passed")
