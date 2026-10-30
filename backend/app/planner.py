"""Planning tools: where to sell for the most take-home money, and which crop to grow.

Same rules as the rest of the agent: every figure is computed here in code from tool data (never by the model),
and anything that is an assumption is labelled as one in the result so the answer can say so.
"""
import json
import math
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

DATA = Path(__file__).parent / "data"
ROAD_FACTOR = 1.3          # road distance is roughly 30% longer than the straight line
MAX_QUINTALS = 100000


def _tools():
    from . import tools
    return tools


def _advisor():
    from . import advisor
    return advisor


# ---------------------------------------------------------------- where to sell (net of transport)

def _geocode(name: str, state: str = "") -> tuple[float, float] | None:
    """Latitude/longitude of a town or market (Open-Meteo geocoding, cached). None if not found."""
    t = _tools()

    def fetch():
        try:
            with httpx.Client(timeout=t.HTTP_TIMEOUT) as c:
                res = c.get(t.GEO_URL, params={"name": name, "count": 5, "country_code": "IN"}).json().get("results") or []
        except Exception:
            return None
        if not res:
            return None
        pick = next((g for g in res if state and str(g.get("admin1", "")).lower() == state.lower()), res[0])
        return (float(pick["latitude"]), float(pick["longitude"]))

    return t._cached("geocode", (name.strip().lower(), state.lower()), fetch, ok=lambda v: v is not None)


def _km(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Straight-line distance (haversine) in km."""
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def sell_plan(commodity: str, from_place: str, quintals: float = 10, state: str = "Andhra Pradesh") -> dict:
    """Where should the farmer sell? Ranks the best-paying markets by money in hand AFTER estimated transport,
    commission and loading, so a far market that pays a little more does not win on paper only."""
    q = float(quintals or 0)
    if q <= 0 or q > MAX_QUINTALS:
        return {"error": "quintals must be a sensible quantity above zero"}
    t, adv = _tools(), _advisor()
    origin = _geocode(from_place, state)
    if not origin:
        return {"error": f"could not find the place: {from_place}"}
    best = t.best_markets(commodity, state)
    cands = [dict(r, _src=best.get("source")) for r in (best.get("highest_first") or [])]
    local = t.get_mandi_price(commodity, from_place, state)
    for r in (local.get("results") or [])[:1]:        # the farmer's own district market is always an option
        if r.get("modal_price_per_quintal") and not any(c.get("market") == r.get("market") for c in cands):
            cands.append(dict(r, _src=local.get("source")))
    options = []
    for r in cands:
        price = r.get("modal_price_per_quintal")
        name = r.get("market") or r.get("district")
        if not price or not name:
            continue
        where = _geocode(name, state) or (_geocode(r["district"], state) if r.get("district") else None)
        if not where:
            continue
        dist = round(_km(origin, where) * ROAD_FACTOR)
        nm = adv.net_market_value(commodity, q, price, distance_km=dist)
        if "error" in nm:
            continue
        options.append({"market": name, "district": r.get("district"), "price_per_quintal": price,
                        "distance_km": dist, "transport_rs": nm["transport_rs"],
                        "net_revenue_rs": nm["net_revenue_rs"], "net_price_per_quintal": nm["net_price_per_quintal"],
                        "date": r.get("date")})
    if not options:
        return {"error": "no market with a known price and location for this crop",
                "source": best.get("source"), "note": best.get("note", "")}
    options.sort(key=lambda o: -o["net_revenue_rs"])
    top = options[0]
    nearest = min(options, key=lambda o: o["distance_km"])
    out = {"source": best.get("source"), "commodity": commodity, "from_place": from_place, "quintals": q,
           "options": options[:5], "best": top,
           "note": ("Road distance is estimated as straight-line x 1.3. Commission 2%, loading Rs 10 per quintal and "
                    "transport Rs 30 per quintal per 100 km are assumptions: ask your trader or vehicle owner for "
                    "real quotes. Prices change daily.")}
    if nearest["market"] != top["market"]:
        out["extra_over_nearest_rs"] = top["net_revenue_rs"] - nearest["net_revenue_rs"]
        out["nearest_market"] = nearest["market"]
    if best.get("note"):
        out["price_note"] = best["note"]
    return out


# ---------------------------------------------------------------- which crop to grow

def _crop_price(c: dict, district: str, state: str) -> dict | None:
    t, adv = _tools(), _advisor()
    res = t.get_mandi_price(c["mandi_keyword"], district, state)
    row = next((r for r in (res.get("results") or []) if r.get("modal_price_per_quintal")), None)
    src = str(res.get("source", ""))
    if row and "sample" not in src:
        basis = "market-live" if "live" in src else "market-saved"
        return {"price": row["modal_price_per_quintal"], "basis": basis, "market": row.get("market")}
    if c.get("msp_key"):
        m = adv.get_msp(c["msp_key"])
        if "current" in m:
            return {"price": m["current"]["msp_price_per_quintal"], "basis": "msp", "market": None}
    return None


def compare_crops(district: str, season: str = "kharif", acres: float = 1, state: str = "Andhra Pradesh") -> dict:
    """Rank crops for the coming season by expected profit per acre: indicative yield x current price - indicative cost.
    Also shows the profit if the price falls 10%, water need and crop duration, so risk is visible, not hidden."""
    season = (season or "kharif").lower()
    if season not in ("kharif", "rabi"):
        return {"error": "season must be kharif or rabi"}
    a = float(acres or 0)
    if a <= 0 or a > 1000:
        return {"error": "acres must be a sensible number above zero"}
    crops = [c for c in json.loads((DATA / "crop_economics.json").read_text())["crops"] if season in c["seasons"]]
    with ThreadPoolExecutor(max_workers=6) as pool:
        prices = list(pool.map(lambda c: _crop_price(c, district, state), crops))
    rows = []
    for c, p in zip(crops, prices):
        if not p:
            continue
        revenue = c["yield_q_per_acre"] * p["price"] * a
        cost = c["cost_rs_per_acre"] * a
        low = c["yield_q_per_acre"] * p["price"] * 0.9 * a
        rows.append({"crop": c["name"], "yield_q_per_acre": c["yield_q_per_acre"], "price_per_quintal": p["price"],
                     "price_basis": p["basis"], "revenue_rs": round(revenue), "cost_rs": round(cost),
                     "profit_rs": round(revenue - cost), "profit_per_acre_rs": round((revenue - cost) / a),
                     "profit_if_price_falls_10pct_rs": round(low - cost),
                     "duration_days": c["duration_days"], "water_need": c["water"]})
    if not rows:
        return {"error": "no price available for any crop right now"}
    rows.sort(key=lambda r: -r["profit_rs"])
    return {"district": district, "season": season, "acres": a, "options": rows, "best": rows[0],
            "price_drop_tested_pct": 10,
            "source": "indicative crop economics + latest mandi price / MSP",
            "note": ("Yield and cost per acre are indicative state-level assumptions, not your field's real numbers. "
                     "Price is the latest mandi price (or MSP where no market price is available) and can change by "
                     "harvest time. Profit ignores your own labour, rent and weather loss. Confirm with the "
                     "agriculture officer before choosing a crop.")}


FUNCS = {"sell_plan": sell_plan, "compare_crops": compare_crops}


def _fn(name, desc, props=None, required=None):
    return {"type": "function", "function": {
        "name": name, "description": desc,
        "parameters": {"type": "object", "properties": props or {}, "required": required or []}}}


SPECS = [
    _fn("sell_plan", "Where to sell for the most money in hand: ranks the best-paying markets after transport, "
        "commission and loading from the farmer's village/district. Use for 'where should I sell' when the farmer "
        "has a quantity or distance matters. Never compute this yourself.",
        {"commodity": {"type": "string"}, "from_place": {"type": "string", "description": "farmer's village or district"},
         "quintals": {"type": "number"}, "state": {"type": "string"}}, ["commodity", "from_place"]),
    _fn("compare_crops", "Which crop to grow next season: ranks crops by expected profit per acre (indicative yield "
        "and cost x latest price), with downside if the price falls 10%, water need and duration. Use for 'what should "
        "I grow / which crop gives more profit'. Say the yield and cost are assumptions.",
        {"district": {"type": "string"}, "season": {"type": "string", "description": "kharif or rabi"},
         "acres": {"type": "number"}, "state": {"type": "string"}}, ["district"]),
]
