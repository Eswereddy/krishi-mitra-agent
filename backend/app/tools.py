"""Tools the farming agent can call. Each returns plain JSON-serialisable data.

Live sources (used when reachable): Open-Meteo (weather, no key) and Agmarknet via
data.gov.in (mandi prices, needs DATA_GOV_API_KEY). If a live source fails, the tool says so
and, for prices, falls back to clearly-labelled SAMPLE data so the agent never invents numbers.
"""
import json
import os
from pathlib import Path

import httpx

DATA = Path(__file__).parent / "data"
GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
AGMARKNET_URL = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
HTTP_TIMEOUT = 10


def _sample_prices(commodity: str, district: str) -> dict:
    raw = json.loads((DATA / "mandi_sample.json").read_text())
    rows = [
        p for p in raw["prices"]
        if commodity.lower() in p["commodity"].lower()
        and (not district or district.lower() in p["market"].lower())
    ]
    return {"source": "sample-data", "note": raw["_note"], "results": rows}


def _to_int(v) -> int | None:
    try:
        return int(float(str(v).replace(",", "")))
    except (TypeError, ValueError):
        return None


def _field(rec: dict, name: str):
    """Agmarknet field names vary in case/spacing between dataset versions."""
    low = {str(k).lower(): v for k, v in rec.items()}
    return low.get(name) if name in low else low.get(name.replace("_", "_x0020_"))


def _date_key(d) -> tuple:
    try:
        dd, mm, yy = str(d).split("/")
        return (int(yy), int(mm), int(dd))
    except ValueError:
        return (0, 0, 0)


def _fetch_live(key: str, state: str, district: str, commodity: str) -> tuple[list[dict], str]:
    """Try the plain and ".keyword" filter styles; return (rows, note)."""
    note = ""
    with httpx.Client(timeout=HTTP_TIMEOUT) as c:
        for suffix in ("", ".keyword"):
            for use_district in ((True, False) if district else (False,)):
                params = {"api-key": key, "format": "json", "limit": 500, f"filters[state{suffix}]": state}
                if use_district:
                    params[f"filters[district{suffix}]"] = district
                r = c.get(AGMARKNET_URL, params=params)
                r.raise_for_status()
                rows = [rec for rec in r.json().get("records", [])
                        if commodity.lower() in str(_field(rec, "commodity") or "").lower()]
                if rows:
                    if district and not use_district:
                        note = f"no rows for district {district}; showing other markets in {state}"
                    return rows, note
    return [], "no live rows for this commodity"


def get_mandi_price(commodity: str, district: str = "", state: str = "Andhra Pradesh", market: str = "") -> dict:
    """Latest mandi price per quintal (Rs). Live Agmarknet data if configured, else sample."""
    district = district or market  # models sometimes say "market" instead of "district"
    key = os.getenv("DATA_GOV_API_KEY", "")
    if not key:
        out = _sample_prices(commodity, district)
        out["live_note"] = "DATA_GOV_API_KEY not set"
        return out
    try:
        rows, note = _fetch_live(key, state, district, commodity)
    except Exception as e:  # network, quota, bad key: fall back, but say so
        out = _sample_prices(commodity, district)
        out["live_error"] = type(e).__name__
        return out
    if not rows:
        out = _sample_prices(commodity, district)
        out["live_note"] = note
        return out
    rows.sort(key=lambda rec: _date_key(_field(rec, "arrival_date")), reverse=True)
    results = [{
        "commodity": _field(rec, "commodity"), "market": _field(rec, "market"),
        "district": _field(rec, "district"), "date": _field(rec, "arrival_date"),
        "min_price_per_quintal": _to_int(_field(rec, "min_price")),
        "max_price_per_quintal": _to_int(_field(rec, "max_price")),
        "modal_price_per_quintal": _to_int(_field(rec, "modal_price")),
    } for rec in rows[:5]]
    out = {"source": "agmarknet-live (data.gov.in)", "results": results}
    if note:
        out["note"] = note
    return out


def _result_rows(rows: list[dict]) -> list[dict]:
    return [{
        "commodity": _field(rec, "commodity"), "market": _field(rec, "market"),
        "district": _field(rec, "district"), "date": _field(rec, "arrival_date"),
        "min_price_per_quintal": _to_int(_field(rec, "min_price")),
        "max_price_per_quintal": _to_int(_field(rec, "max_price")),
        "modal_price_per_quintal": _to_int(_field(rec, "modal_price")),
    } for rec in rows]


def best_markets(commodity: str, state: str = "Andhra Pradesh") -> dict:
    """Which markets in the state pay the most for a crop (latest price per market), highest first."""
    key = os.getenv("DATA_GOV_API_KEY", "")
    results, source, note = [], "sample-data", "DATA_GOV_API_KEY not set"
    if key:
        try:
            rows, note = _fetch_live(key, state, "", commodity)
            if rows:
                rows.sort(key=lambda rec: _date_key(_field(rec, "arrival_date")), reverse=True)
                latest = {}
                for rec in rows:                       # newest record per market
                    latest.setdefault(_field(rec, "market"), rec)
                results = [r for r in _result_rows(list(latest.values())) if r["modal_price_per_quintal"]]
                source = "agmarknet-live (data.gov.in)"
        except Exception as e:
            note = f"live lookup failed ({type(e).__name__})"
    if not results:
        results = _sample_prices(commodity, "")["results"]
        source = "sample-data"
    results.sort(key=lambda r: r.get("modal_price_per_quintal") or 0, reverse=True)
    out = {"source": source, "highest_first": results[:5]}
    if source == "sample-data":
        out["note"] = f"SAMPLE data ({note}); approximate only"
    return out


def calculate_revenue(quintals: float, price_per_quintal: float, expenses: float = 0) -> dict:
    """Exact arithmetic for the farmer's expected income (do not let the model do the maths)."""
    revenue = round(float(quintals) * float(price_per_quintal))
    expenses = round(float(expenses or 0))
    return {"quintals": quintals, "price_per_quintal": price_per_quintal, "revenue_rs": revenue,
            "expenses_rs": expenses, "profit_rs": revenue - expenses}


def get_weather(place: str, days: int = 3) -> dict:
    """Short forecast (temperature, rain) for a place, from Open-Meteo."""
    try:
        with httpx.Client(timeout=HTTP_TIMEOUT) as c:
            geo = c.get(GEO_URL, params={"name": place, "count": 1}).json().get("results") or []
            if not geo:
                return {"error": f"place not found: {place}"}
            g = geo[0]
            f = c.get(FORECAST_URL, params={
                "latitude": g["latitude"], "longitude": g["longitude"], "timezone": "auto",
                "forecast_days": min(max(int(days), 1), 7),
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max",
            }).json()
        d = f["daily"]
        days_out = [
            {"date": d["time"][i], "max_c": d["temperature_2m_max"][i], "min_c": d["temperature_2m_min"][i],
             "rain_mm": d["precipitation_sum"][i], "rain_chance_pct": d["precipitation_probability_max"][i]}
            for i in range(len(d["time"]))
        ]
        return {"source": "open-meteo.com", "place": f"{g['name']}, {g.get('admin1', '')}", "forecast": days_out}
    except Exception as e:
        return {"error": f"weather service unavailable ({type(e).__name__})"}


def get_expert_help() -> dict:
    """Where to get a human expert when the problem is serious or the agent is unsure."""
    return {
        "kisan_call_centre": "1800-180-1551",
        "note": "Toll-free Kisan Call Centre: farm experts answer in regional languages.",
        "local": "Your village Rythu Seva Kendram / agriculture officer, or the nearest Krishi Vigyan Kendra (KVK).",
    }


def check_schemes(owns_land: bool = False, grows_notified_crop: bool = True,
                  state: str = "Andhra Pradesh") -> dict:
    """Return schemes whose simple eligibility rules match the farmer's profile."""
    schemes = json.loads((DATA / "schemes.json").read_text())
    profile = {"owns_land": owns_land, "grows_notified_crop": grows_notified_crop,
               "is_farmer": True, "state": state}
    matched = []
    for s in schemes:
        if all(profile.get(k) == v for k, v in s["rules"].items()):
            matched.append({k: s[k] for k in ("name", "benefit", "documents", "how_to_apply", "verify_at")})
    return {"matched": matched, "disclaimer": "Indicative only; documents and rules can change. Confirm with the official office."}


TOOL_FUNCS = {
    "get_mandi_price": get_mandi_price, "get_weather": get_weather,
    "get_expert_help": get_expert_help, "check_schemes": check_schemes,
    "best_markets": best_markets, "calculate_revenue": calculate_revenue,
}


def _fn(name, desc, props=None, required=None):
    return {"type": "function", "function": {
        "name": name, "description": desc,
        "parameters": {"type": "object", "properties": props or {}, "required": required or []}}}


TOOL_SPECS = [
    _fn("get_mandi_price", "Get the latest mandi (market) price per quintal for a crop.",
        {"commodity": {"type": "string", "description": "e.g. Paddy, Groundnut, Cotton, Tomato"},
         "district": {"type": "string"}, "state": {"type": "string"}}, ["commodity"]),
    _fn("get_weather", "Get a 1-7 day weather forecast (temperature, rain) for a village/town/district.",
        {"place": {"type": "string"}, "days": {"type": "integer"}}, ["place"]),
    _fn("check_schemes", "Find government schemes a farmer may be eligible for.",
        {"owns_land": {"type": "boolean"}, "grows_notified_crop": {"type": "boolean"},
         "state": {"type": "string"}}, ["owns_land"]),
    _fn("best_markets", "Find which markets in the state pay the highest price for a crop (where to sell).",
        {"commodity": {"type": "string"}, "state": {"type": "string"}}, ["commodity"]),
    _fn("calculate_revenue", "Exact income calculation: quintals x price per quintal minus expenses. "
        "Always use this for money maths.",
        {"quintals": {"type": "number"}, "price_per_quintal": {"type": "number"},
         "expenses": {"type": "number"}}, ["quintals", "price_per_quintal"]),
    _fn("get_expert_help", "Get the Kisan Call Centre number and local expert contacts. Use when the problem "
        "is serious, uncertain, or needs a human expert."),
]


def run_tool(name: str, args: dict) -> dict:
    fn = TOOL_FUNCS.get(name)
    if not fn:
        return {"error": f"unknown tool {name}"}
    try:
        return fn(**args)
    except TypeError as e:
        return {"error": str(e)}
