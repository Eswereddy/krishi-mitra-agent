"""Offline tests for field-aware verification and the saved-data snapshot fallback.
Run from backend/: python tests/test_grounding.py"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["CACHE_TTL_S"] = "0"
os.environ.pop("DATA_GOV_API_KEY", None)

from app import tools, verify  # noqa: E402

WEATHER = [{"tool": "get_weather", "args": {}, "result": {"forecast": [
    {"date": "2026-10-29", "max_c": 33.1, "min_c": 22.0, "rain_mm": 4.2, "rain_chance_pct": 60}]}}]
PRICE = [{"tool": "get_mandi_price", "args": {}, "result": {"results": [
    {"market": "Kurnool", "date": "28/10/2026", "modal_price_per_quintal": 6200}]}}]
TREND = [{"tool": "get_price_trend", "args": {}, "result": {"change_pct": 5.3, "highest": 6400, "lowest": 6000}}]
SCHEME = [{"tool": "check_schemes", "args": {}, "result": {"matched": [
    {"benefit": "Central income support of Rs 6,000 per year in three instalments"}]}}]


def ok(answer, steps):
    return verify.verify_answer(answer, steps)["passed"]


def test_money_must_come_from_a_price_field():
    assert ok("Groundnut is ₹6,200 per quintal in Kurnool", PRICE)
    assert ok("ధర 6200 రూపాయలు", PRICE)
    assert not ok("Groundnut is ₹2026 per quintal", PRICE)      # the year exists in the result, but is not a price
    assert not ok("Price is Rs 6500", PRICE)


def test_percent_degrees_millimetres_are_checked_with_rounding():
    assert ok("Rain chance is 60% with about 4 mm of rain, high 33°C", WEATHER)
    assert not ok("Rain chance is 85%", WEATHER)
    assert not ok("High of 41°C expected", WEATHER)
    assert not ok("Expect 25 mm of rain", WEATHER)
    assert ok("The price rose 5% this fortnight", TREND)
    assert not ok("The price rose 12%", TREND)


def test_percent_cannot_borrow_a_price():
    assert not ok("Rain chance is 6200%", WEATHER)


def test_scheme_amount_in_text_is_grounded_and_small_numbers_ignored():
    assert ok("PM-KISAN gives Rs 6,000 per year", SCHEME)
    assert not ok("PM-KISAN gives Rs 8,000 per year", SCHEME)
    v = verify.verify_answer("Steps: 1. Call 2. Wait 3 days", PRICE)
    assert v["passed"] and v["checked"] == 0


def test_checked_count_and_report():
    v = verify.verify_answer("₹6,200 per quintal, rain 60%, price 9999", PRICE + WEATHER)
    assert v["checked"] == 3 and v["unverified"] == ["9999"] and not v["passed"]


def _snapshot(tmp):
    rec = lambda m, d, p: {"state": "Andhra Pradesh", "district": "Kurnool", "market": m, "commodity": "Groundnut",
                           "arrival_date": d, "min_price": str(p - 100), "max_price": str(p + 100), "modal_price": str(p)}
    rows = [rec("Kurnool", f"{day:02d}/10/2026", 6000 + (day - 20) * 50) for day in range(20, 29)]
    rows += [rec("Adoni", "28/10/2026", 6100)]
    path = Path(tmp) / "snap.json"
    path.write_text(json.dumps({"fetched_at": "2026-10-28", "records": rows}))
    return path


def test_snapshot_is_used_and_labelled_when_live_is_unavailable():
    with tempfile.TemporaryDirectory() as tmp:
        old = tools.SNAPSHOT_PATH
        tools.SNAPSHOT_PATH = _snapshot(tmp)
        try:
            out = tools.get_mandi_price("Groundnut", "Kurnool")
            assert out["source"] == "agmarknet-snapshot (saved 2026-10-28)" and "not today's price" in out["note"]
            assert out["results"][0]["date"] == "28/10/2026" and out["results"][0]["modal_price_per_quintal"] == 6400
            best = tools.best_markets("Groundnut")
            assert best["source"].startswith("agmarknet-snapshot") and best["highest_first"][0]["market"] == "Kurnool"
            trend = tools.get_price_trend("Groundnut", market="Kurnool")
            assert trend["source"].startswith("agmarknet-snapshot") and trend["trend"] == "rising"
            assert trend["series"][0]["modal_price_per_quintal"] == 6000 and "not today's price" in trend["note"]
        finally:
            tools.SNAPSHOT_PATH = old


def test_without_snapshot_prices_fall_back_to_labelled_sample_and_trend_errors():
    tools.SNAPSHOT_PATH = Path("/nonexistent/snapshot.json")
    assert tools.get_mandi_price("Paddy", "Kurnool")["source"] == "sample-data"
    assert "error" in tools.get_price_trend("Paddy")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
