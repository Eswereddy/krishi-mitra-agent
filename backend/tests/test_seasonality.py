"""Offline tests for price seasonality. Run from backend/: python tests/test_seasonality.py"""
import os
os.environ["CACHE_TTL_S"] = "0"
os.environ["MOCK_MODE"] = "1"
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import globalprices as gp, seasonality as sz, tools, verify  # noqa: E402

# Maize: cheap at harvest (Jul, Aug), dearest in the lean season (Feb, Mar)
PATTERN = {1: 110, 2: 125, 3: 130, 4: 120, 5: 105, 6: 95, 7: 80, 8: 80, 9: 90, 10: 95, 11: 100, 12: 100}


def _rows(years=("2023", "2024", "2025"), scale=1.0, market="Nairobi", commodity="Maize", drop=()):
    out = []
    for y in years:
        for m, v in PATTERN.items():
            if (y, m) in drop:
                continue
            out.append({"date": f"{y}-{m:02d}-15", "market": market, "admin1": "x", "commodity": commodity, "unit": "KG", "pricetype": "Retail",
                        "currency": "KES", "price": v * scale, "usdprice": v * scale / 130})
    return out


def _load(rows):
    gp._load = lambda iso: rows


def test_index_and_peak_months():
    _load(_rows())
    r = sz.price_seasonality("maize", "KE")
    by = {x["month"]: x["index"] for x in r["index_by_month"]}
    assert r["years_used"] == ["2023", "2024", "2025"] and len(by) == 12
    assert r["peak_month"] == 3 and r["trough_month"] in (7, 8) and r["highest_months"] == [2, 3] and r["lowest_months"] == [7, 8]
    assert by[3] > 125 and by[7] < 80 and sum(by.values()) // 12 in (99, 100, 101)           # indices average to ~100
    assert r["peak_vs_trough_pct"] == round((by[3] / min(by[7], by[8]) - 1) * 100) and r["market"] == "Nairobi" and r["currency"] == "KES"
    assert r["months_from_trough_to_peak"] == (3 - r["trough_month"]) % 12 and "not a forecast" in r["note"]


def test_inflation_does_not_fake_a_seasonal_pattern():
    rows = _rows(("2023",), 1.0) + _rows(("2024",), 2.0) + _rows(("2025",), 4.0)             # prices double every year, same shape
    _load(_rows())
    plain = {x["month"]: x["index"] for x in sz.price_seasonality("maize", "KE")["index_by_month"]}
    _load(rows)
    r = sz.price_seasonality("maize", "KE")
    assert {x["month"]: x["index"] for x in r["index_by_month"]} == plain and r["peak_month"] == 3   # same shape, inflation removed
    flat = [dict(x, price=100.0) for x in _rows()]
    _load(flat)
    f = sz.price_seasonality("maize", "KE")
    assert f["peak_vs_trough_pct"] == 0


def test_patchy_or_short_history_is_refused_honestly():
    _load(_rows(("2025",)))
    assert "not enough price history" in sz.price_seasonality("maize", "KE")["error"]
    _load(_rows(("2024", "2025"), drop={("2025", m) for m in range(1, 6)}))                    # 2025 has only 7 months: not usable
    assert "not enough price history" in sz.price_seasonality("maize", "KE")["error"]
    _load(_rows())
    assert "available_commodities" in sz.price_seasonality("sorghum", "KE")
    assert "get_price_trend" in sz.price_seasonality("maize", "IN")["error"] and "unknown country" in sz.price_seasonality("maize", "ZZ")["error"]
    _load([])
    assert "no public price data" in sz.price_seasonality("maize", "KE")["error"]
    def boom(iso): raise RuntimeError("down")
    gp._load = boom
    assert "unavailable" in sz.price_seasonality("maize", "KE")["error"]


def test_longest_history_market_is_used_and_filter_works():
    _load(_rows(market="Nakuru") + _rows(("2025",), market="Kisumu"))
    assert sz.price_seasonality("maize", "KE")["market"] == "Nakuru"
    assert sz.price_seasonality("maize", "KE", market="nakuru")["market"] == "Nakuru"


def test_tool_registered_and_answer_verifies():
    _load(_rows())
    assert "price_seasonality" in {s["function"]["name"] for s in tools.TOOL_SPECS}
    r = tools.run_tool("price_seasonality", {"commodity": "maize", "country": "KE"})
    steps = [{"tool": "price_seasonality", "result": r}]
    assert verify.verify_answer(f"Prices are about {r['peak_vs_trough_pct']}% higher at the peak than at the low.", steps)["passed"]
    assert verify.verify_answer("Prices are about 93% higher at the peak.", steps)["unverified"] == ["93"]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("ok", fn.__name__)
    print(len(fns), "passed")
