"""Offline tests for storage, livestock heat, loans, input costs and break-even. Run from backend/: python tests/test_farmtools.py"""
import os
os.environ["CACHE_TTL_S"] = "0"
os.environ["MOCK_MODE"] = "1"
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import farmtools as ft, tools, verify  # noqa: E402


def _wx(daily, place="Nakuru, Rift Valley"):
    ft._forecast = lambda p, c, d, n: {"place": place, "daily": daily}


def test_storage_limits_drying_days_and_damp_air():
    _wx({"time": ["d1", "d2", "d3"], "precipitation_sum": [0, 5, 0.5], "relative_humidity_2m_mean": [60, 85, 69]})
    r = ft.storage_check("maize", 16, "Nakuru", "KE")
    assert not r["safe_to_store"] and r["safe_max_moisture_pct"] == 13 and r["points_to_dry"] == 3.0
    assert r["good_drying_days"] == ["d1", "d3"] and r["average_humidity_pct"] == 71 and not r["damp_air"] and "toxins" in r["warning"]
    assert ft.storage_check("maize", 12.5)["safe_to_store"] and "good_drying_days" not in ft.storage_check("maize", 12.5)
    _wx({"time": ["d1"], "precipitation_sum": [0], "relative_humidity_2m_mean": [80]})
    assert ft.storage_check("groundnut", 8, "Nakuru")["damp_air"] and ft.storage_check("groundnut", 11)["points_to_dry"] == 2.0
    assert ft.storage_check("paddy", 14)["safe_to_store"] and ft.storage_check("beans", 14)["warning"] == ""


def test_storage_bad_inputs():
    assert "known_crops" in ft.storage_check("tomato", 10)
    for bad in ("abc", 0, -3, 80):
        assert "error" in ft.storage_check("maize", bad)
    ft._forecast = lambda *a: {"error": "weather service unavailable (X)"}
    assert "good_drying_days" not in ft.storage_check("maize", 15, "Nowhere")           # forecast failure never blocks the main answer


def test_thi_and_bands_for_cattle_and_poultry():
    assert round(ft.thi(35, 40), 1) == 82.8
    _wx({"time": ["d1", "d2", "d3"], "temperature_2m_max": [24, 35, 44], "relative_humidity_2m_min": [60, 40, 30]})
    r = ft.livestock_heat("cows", "Nakuru", "KE")
    assert [d["stress"] for d in r["days"]] == ["none", "moderate", "severe"] and r["worst_day"] == "d3" and r["needs_action"]
    assert "clean_cool_water" in r["actions"] and "veterinarian" in r["note"]
    p = ft.livestock_heat("chickens", "Nakuru")
    assert [d["stress"] for d in p["days"]] == ["none", "severe", "emergency"] and "thi" not in p["days"][0]
    _wx({"time": ["d1"], "temperature_2m_max": [22], "relative_humidity_2m_min": [50]})
    cool = ft.livestock_heat("buffalo", "Nakuru")
    assert not cool["needs_action"] and cool["actions"] == [] and "supported" in ft.livestock_heat("goat", "Nakuru")


def test_loan_effective_rate_ranks_fairly():
    r = ft.loan_compare([
        {"name": "Bank", "amount": 1000, "rate_pct": 12, "rate_per": "year", "months": 12},
        {"name": "Trader", "amount": 1000, "rate_pct": 3, "rate_per": "month", "months": 12, "method": "flat"},
        {"name": "Coop", "amount": 1000, "rate_pct": 3, "rate_per": "month", "months": 12, "method": "reducing"},
        {"name": "MFI fee", "amount": 1000, "rate_pct": 1, "rate_per": "month", "months": 12, "method": "reducing", "fee_pct": 10}])
    by = {o["name"]: o for o in r["offers"]}
    assert r["cheapest"] == "Bank" and [o["name"] for o in r["offers"]][-1] == "Trader"
    assert by["Bank"]["effective_annual_rate_pct"] == 12.7 and abs(by["Coop"]["effective_annual_rate_pct"] - 42.6) < 0.2
    assert by["Trader"]["total_interest"] == 360 and by["Trader"]["monthly_payment"] == 113.33 and by["Trader"]["effective_annual_rate_pct"] > 70
    assert by["MFI fee"]["fees"] == 100 and by["MFI fee"]["effective_annual_rate_pct"] > 35      # a "cheap" 1% a month plus a fee is not cheap
    assert by["Coop"]["extra_paid_vs_amount"] == by["Coop"]["total_interest"]
    zero = ft.loan_compare([{"amount": 1200, "rate_pct": 0, "months": 12}])["offers"][0]
    assert zero["monthly_payment"] == 100 and zero["effective_annual_rate_pct"] == 0.0


def test_loan_validation():
    assert "error" in ft.loan_compare([]) and "error" in ft.loan_compare("x") and "error" in ft.loan_compare([{"amount": 5}])
    assert "error" in ft.loan_compare([{"amount": -5, "rate_pct": 1, "months": 6}]) and "error" in ft.loan_compare([{"amount": 5, "rate_pct": 1, "months": 0}])
    assert "error" in ft.loan_compare([{"amount": 5, "rate_pct": 1, "months": 6, "fee_pct": 60}])


def test_input_cost_per_nutrient():
    r = ft.compare_inputs([{"name": "Urea", "price": 1000, "bag_kg": 50, "n_pct": 46},
                           {"name": "DAP", "price": 2000, "bag_kg": 50, "n_pct": 18, "p2o5_pct": 46},
                           {"name": "Ammonium sulphate", "price": 800, "bag_kg": 50, "n_pct": 21}])
    by = {p["name"]: p for p in r["products"]}
    assert by["Urea"]["cost_per_kg_n"] == 43.48 and by["DAP"]["cost_per_kg_p2o5"] == 86.96 and by["DAP"]["cost_per_kg_n"] == 222.22
    assert "cost_per_kg_p2o5" not in by["Urea"] and r["cheapest_per_nutrient"] == {"n": "Urea"} and by["Urea"]["price_per_kg_product"] == 20.0
    assert "error" in ft.compare_inputs([{"price": 10, "bag_kg": 50}]) and "error" in ft.compare_inputs([{"price": 0, "bag_kg": 50, "n_pct": 10}])
    assert "error" in ft.compare_inputs([{"price": 10, "bag_kg": 50, "n_pct": 140}]) and "error" in ft.compare_inputs([])


def test_breakeven():
    r = ft.breakeven_price(54000, 1800, "kg")
    assert r["breakeven_price_per_unit"] == 30.0 and r["price_for_margin_per_unit"] == 36.0 and r["target_margin_pct"] == 20
    assert ft.breakeven_price(100, 8, "bag", 0)["price_for_margin_per_unit"] == 12.5
    assert "error" in ft.breakeven_price(0, 5) and "error" in ft.breakeven_price("x", 5) and "error" in ft.breakeven_price(10, 0)


def test_tools_registered_and_answers_verify():
    names = {s["function"]["name"] for s in tools.TOOL_SPECS}
    assert set(ft.FUNCS) <= names
    r = tools.run_tool("breakeven_price", {"total_cost": 54000, "expected_quantity": 1800})
    steps = [{"tool": "breakeven_price", "result": r}]
    assert verify.verify_answer("You need KES 30 per kg to break even and 36 for a 20% margin.", steps)["passed"]
    assert verify.verify_answer("You need KES 45 per kg.", steps)["unverified"] == ["45"]
    lo = tools.run_tool("loan_compare", {"offers": [{"name": "Trader", "amount": 1000, "rate_pct": 3, "rate_per": "month", "months": 12, "method": "flat"}]})
    assert "error" not in lo and lo["offers"][0]["total_interest"] == 360


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok", fn.__name__)
    print(len(fns), "passed")
