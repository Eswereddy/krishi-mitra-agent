"""Advisor tools: MSP, net market value, spray window, crop problem lookup, hold-or-sell.

Same rules as tools.py: plain JSON results, numbers come from data or exact arithmetic (never from the
model), and anything uncertain is labelled. No pesticide names or doses are ever returned: the problem
lookup gives symptoms, field checks and cultural steps, then sends the farmer to the agriculture officer.
This module imports tools.py lazily (tools.py registers these functions at its bottom).
"""
import json
import re
from pathlib import Path

DATA = Path(__file__).parent / "data"
PERISHABLE = ("tomato", "onion", "potato", "banana", "brinjal", "okra", "cabbage", "cauliflower", "green chilli",
              "vegetable", "mango", "papaya", "watermelon")
MSP_PROCUREMENT = ("paddy", "groundnut", "cotton", "tur", "urad", "moong", "maize", "jowar", "bajra", "ragi",
                   "gram", "wheat", "mustard", "lentil", "safflower", "sunflower", "soyabean", "sesamum", "nigerseed", "barley")


def _tools():
    from . import tools
    return tools


def _msp_data() -> dict:
    return json.loads((DATA / "msp.json").read_text())


def _norm_crop(name: str) -> str:
    n = re.sub(r"\(.*?\)", "", str(name or "")).strip().lower()
    n = re.sub(r"\s+", " ", n)
    aliases = _msp_data()["aliases"]
    return aliases.get(n, aliases.get(str(name or "").strip().lower(), n))


def get_msp(commodity: str) -> dict:
    """Government Minimum Support Price per quintal for a crop: the current season first, older season also shown."""
    data = _msp_data()
    crop = _norm_crop(commodity)
    found = []
    for sid, s in data["seasons"].items():
        price = s["crops"].get(crop)
        if price is not None:
            found.append({"season": s["label"], "type": s["type"], "msp_price_per_quintal": price, "_id": sid})
    if not found:
        return {"error": f"no MSP is announced for {commodity}", "note": "MSP covers 22 mandated crops; "
                "vegetables and most fruits have no MSP."}
    # Current seasons first: Rabi 2027-28 (sowing now) then Kharif 2026-27 (this season's harvest), then older.
    order = {"rabi-2027-28": 0, "kharif-2026-27": 1, "rabi-2026-27": 2}
    found.sort(key=lambda r: order.get(r["_id"], 9))
    for r in found:
        r.pop("_id")
    return {"source": "CCEA MSP announcements (agriculture.gov.in / PIB)", "commodity": commodity,
            "current": found[0], "other_seasons": found[1:], "checked_on": data["checked"],
            "note": "MSP is the government's floor price. It applies only to what is actually bought "
                    "at procurement centres, not to every mandi sale. Verify at the village Rythu Seva Kendram."}


def net_market_value(commodity: str, quintals: float, price_per_quintal: float, distance_km: float = 0,
                     commission_pct: float = 2.0, loading_rs_per_quintal: float = 10,
                     transport_rs_per_quintal_per_100km: float = 30) -> dict:
    """What the farmer really takes home from one market after transport, commission and loading.
    The cost rates are ASSUMED defaults (flagged in the result): the farmer should replace them with real quotes."""
    q, p = float(quintals), float(price_per_quintal)
    if q <= 0 or p <= 0:
        return {"error": "quintals and price must be above zero"}
    gross = q * p
    commission = gross * float(commission_pct) / 100
    loading = q * float(loading_rs_per_quintal)
    transport = q * float(transport_rs_per_quintal_per_100km) * float(distance_km) / 100
    net = gross - commission - loading - transport
    out = {"commodity": commodity, "quintals": q, "price_per_quintal": p, "distance_km": distance_km,
           "gross_revenue_rs": round(gross), "commission_rs": round(commission), "loading_rs": round(loading),
           "transport_rs": round(transport), "net_revenue_rs": round(net),
           "net_price_per_quintal": round(net / q),
           "assumed": {"commission_pct": commission_pct, "loading_rs_per_quintal": loading_rs_per_quintal,
                       "transport_rs_per_quintal_per_100km": transport_rs_per_quintal_per_100km},
           "note": "Commission, loading and transport rates are assumptions, not market data. "
                   "Replace them with the real quotes from your trader or vehicle owner."}
    msp = get_msp(commodity)
    if "current" in msp:
        m = msp["current"]["msp_price_per_quintal"]
        out["msp_price_per_quintal"] = m
        out["net_vs_msp_rs_per_quintal"] = round(net / q) - m
    return out


def spray_window(place: str, days: int = 3) -> dict:
    """Which of the next days are suitable for spraying, from the weather forecast. General rule of thumb only."""
    wx = _tools().get_weather(place, days)
    if "error" in wx:
        return wx
    out = []
    for d in wx["forecast"]:
        rain, chance, wind, hot = d.get("rain_mm") or 0, d.get("rain_chance_pct") or 0, d.get("wind_kmh"), (d.get("max_c") or 0) >= 35
        reasons, wet, windy = [], chance >= 40 or rain >= 2, wind is not None and wind > 15
        if wet:
            reasons.append("rain likely: spray would wash off")
        if windy:
            reasons.append("too windy: spray will drift")
        suitable = not reasons
        code = "rain_wind" if wet and windy else "rain" if wet else "wind" if windy else "hot" if hot else "good"
        out.append({"date": d["date"], "suitable": suitable, "code": code, "rain_chance_pct": chance, "rain_mm": rain,
                    "wind_kmh": wind, "max_c": d.get("max_c"),
                    "advice": (reasons[0] if len(reasons) == 1 else "; ".join(reasons)) if reasons else
                    ("spray only in the early morning or late evening: very hot day" if hot else "good day to spray")})
    good = [x["date"] for x in out if x["suitable"]]
    return {"source": wx.get("source"), "place": wx.get("place"), "days": out,
            "best_day": good[0] if good else None,
            "note": "Rule of thumb: spray on a dry, calm day (rain chance under 40%, wind under 15 km/h), "
                    "in the early morning or evening. Product and dose: ask the agriculture officer."}


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z]{3,}", str(text or "").lower()))


def lookup_problem(crop: str, symptoms: str) -> dict:
    """Match what the farmer sees against a small knowledge base. Never gives a pesticide name or dose."""
    crop_n = _norm_crop(crop)
    text = str(symptoms or "").lower()
    toks = _tokens(text)
    scored = []
    for p in json.loads((DATA / "problems.json").read_text()):
        if crop_n and crop_n not in p["crops"]:
            continue
        score = 0
        for kw in p["keywords"]:
            kw_l = kw.lower()
            if kw_l in text:
                score += 2
            elif _tokens(kw_l) and _tokens(kw_l) <= toks:
                score += 1
        if score:
            scored.append((score, p))
    scored.sort(key=lambda sp: -sp[0])
    if not scored:
        return {"matches": [], "needs_expert": True,
                "note": "I could not match these signs. Send a clear photo of the leaf and the whole plant, or "
                        "call the Kisan Call Centre / agriculture officer."}
    top = scored[0][0]
    matches = [{"name": p["name"], "looks_like": p["looks_like"], "favoured_by": p["favoured_by"],
                "what_to_do": p["what_to_do"], "urgency": p["urgency"], "expert_note": p["expert_note"],
                "confidence": "medium" if s >= 4 and s >= top else "low"} for s, p in scored[:3]]
    return {"crop": crop, "matches": matches,
            "needs_expert": any(m["urgency"] == "high" for m in matches) or matches[0]["confidence"] == "low",
            "note": "Photo-based and symptom-based matches are a first guess only. No pesticide name or dose is given here: "
                    "confirm with the agriculture officer before spending money on any spray."}


def hold_or_sell(commodity: str, state: str = "Andhra Pradesh", district: str = "", market: str = "",
                 quintals: float = 0) -> dict:
    """One clear sell-now / hold-a-little / use-procurement guide from price trend, best markets and MSP.
    The rules are fixed code so the answer is repeatable; it is guidance, not a guarantee."""
    t = _tools()
    crop = _norm_crop(commodity)
    trend = t.get_price_trend(commodity, market=market, district=district, state=state)
    markets = t.best_markets(commodity, state)
    msp = get_msp(commodity)
    out = {"commodity": commodity, "trend": {k: trend.get(k) for k in ("market", "trend", "change_pct", "source", "note") if k in trend}}
    if "error" in trend:
        out["trend_error"] = trend["error"]
    cur = trend["series"][-1]["modal_price_per_quintal"] if trend.get("series") else None
    if cur:
        out["current_price_per_quintal"] = cur
    best = (markets.get("highest_first") or [None])[0]
    if best:
        out["best_market"] = {"market": best.get("market"), "modal_price_per_quintal": best.get("modal_price_per_quintal"),
                              "source": markets.get("source")}
        if cur:
            out["best_market"]["extra_over_current_rs_per_quintal"] = (best.get("modal_price_per_quintal") or 0) - cur
    m = msp["current"]["msp_price_per_quintal"] if "current" in msp else None
    if m:
        out["msp_price_per_quintal"] = m
        out["msp_season"] = msp["current"]["season"]
        if cur:
            out["current_vs_msp_rs_per_quintal"] = cur - m
    reasons = []
    perishable = any(w in crop for w in PERISHABLE)
    tr = trend.get("trend")
    if perishable:
        rec = "sell_now"
        reasons.append("perishable crop: waiting causes spoilage and loss")
    elif tr is None:
        rec = "not_enough_data"
        reasons.append("no price history available: compare best_market and MSP, or ask the market committee")
    elif m and cur and cur < m and crop in MSP_PROCUREMENT:
        rec = "use_procurement_or_wait"
        reasons.append("market price is below MSP: ask about government procurement before selling in the open market")
    elif tr == "falling":
        rec = "sell_now"
        reasons.append("price has been falling")
    elif tr == "rising":
        rec = "hold_short"
        reasons.append("price is rising: waiting a week or two may help if you can store safely")
        reasons.append("check the price again before deciding; do not hold if rain or storage is a risk")
    else:
        rec = "sell_now_or_hold_if_stored"
        reasons.append("price is steady: no strong reason to wait unless you can store safely and do not need cash")
    out["recommendation"] = rec
    out["reasons"] = reasons
    if quintals and cur:
        out["income_at_current_price_rs"] = round(float(quintals) * cur)
    out["disclaimer"] = "Guidance from recent prices, not a guarantee. Prices can change quickly."
    return out


def irrigation_advice(place: str, days: int = 3) -> dict:
    """Irrigate or wait? From the rain forecast only (the farmer's soil is not known, so dry-soil is assumed to be checked by hand)."""
    wx = _tools().get_weather(place, days)
    if "error" in wx:
        return wx
    out = []
    for d in wx["forecast"]:
        rain, chance, hot = d.get("rain_mm") or 0, d.get("rain_chance_pct") or 0, (d.get("max_c") or 0) >= 38
        if rain >= 5 or chance >= 60:
            code = "skip_rain"
        elif rain >= 1 or chance >= 40:
            code = "wait_light_rain"
        elif hot:
            code = "evening_hot"
        else:
            code = "if_dry"
        out.append({"date": d["date"], "code": code, "irrigate": code in ("evening_hot", "if_dry"),
                    "rain_chance_pct": chance, "rain_mm": rain, "max_c": d.get("max_c")})
    nxt = next((x["date"] for x in out if x["irrigate"]), None)
    return {"source": wx.get("source"), "place": wx.get("place"), "days": out, "next_irrigation_day": nxt,
            "note": "Forecast-based guide only. Check the soil by hand: irrigate only if the root zone is dry. "
                    "Water need changes with crop stage and soil type."}


def kcc_interest(amount_rs: float, months: float = 6) -> dict:
    """Kisan Credit Card short-term crop loan interest: 7% a year, effectively 4% with the 3% prompt repayment
    incentive when repaid within one year. The interest benefit applies on up to Rs 3 lakh per farmer
    (MISS rules, checked Oct 2026: the rules are renewed yearly, so confirm with the bank). Simple interest."""
    amt, mths = float(amount_rs), float(months)
    if amt <= 0 or mths <= 0:
        return {"error": "amount and months must be above zero"}
    cap = 300000
    eligible = min(amt, cap)
    full = eligible * 0.07 * mths / 12
    out = {"loan_amount_rs": round(amt), "months": mths, "interest_rate_pct": 7, "effective_rate_pct": 4,
           "interest_at_7_pct_rs": round(full), "benefit_limit_rs": cap,
           "note": "Simple-interest estimate. Interest benefit applies on up to Rs 3 lakh; any part above that "
                   "is charged at the bank's own rate. The bank decides the exact amount: confirm with it."}
    if mths <= 12:
        prompt = eligible * 0.04 * mths / 12
        out.update({"interest_if_repaid_on_time_rs": round(prompt), "interest_saved_rs": round(full - prompt),
                    "prompt_repayment": "applies if the loan is repaid within one year"})
    else:
        out["prompt_repayment"] = "not available: the 3% incentive needs repayment within one year"
    if amt > cap:
        out["above_limit_rs"] = round(amt - cap)
    return out


FUNCS = {"get_msp": get_msp, "net_market_value": net_market_value, "spray_window": spray_window,
         "lookup_problem": lookup_problem, "hold_or_sell": hold_or_sell,
         "irrigation_advice": irrigation_advice, "kcc_interest": kcc_interest}


def _fn(name, desc, props=None, required=None):
    return {"type": "function", "function": {
        "name": name, "description": desc,
        "parameters": {"type": "object", "properties": props or {}, "required": required or []}}}


SPECS = [
    _fn("get_msp", "Government Minimum Support Price (MSP) per quintal for a crop, with the season. "
        "Use for 'what is the MSP' and to compare a mandi price with the support price.",
        {"commodity": {"type": "string", "description": "e.g. Paddy, Groundnut, Cotton, Wheat, Gram"}}, ["commodity"]),
    _fn("net_market_value", "Take-home money from selling in a market after commission, loading and transport. "
        "Use it to compare a near market with a far market that pays more. Always use it for such maths.",
        {"commodity": {"type": "string"}, "quintals": {"type": "number"}, "price_per_quintal": {"type": "number"},
         "distance_km": {"type": "number"}, "commission_pct": {"type": "number"},
         "loading_rs_per_quintal": {"type": "number"}, "transport_rs_per_quintal_per_100km": {"type": "number"}},
        ["commodity", "quintals", "price_per_quintal"]),
    _fn("spray_window", "Which of the next days (1-7) are suitable for spraying, from rain chance, wind and heat.",
        {"place": {"type": "string"}, "days": {"type": "integer"}}, ["place"]),
    _fn("lookup_problem", "Look up likely crop problems from what the farmer sees (symptoms) for a crop. "
        "Returns symptoms, checks and non-chemical steps; never pesticide names or doses.",
        {"crop": {"type": "string"}, "symptoms": {"type": "string", "description": "the farmer's own description"}},
        ["crop", "symptoms"]),
    _fn("hold_or_sell", "One recommendation for 'should I sell now or hold': combines price trend, best market and MSP. "
        "Use for sell-or-wait questions; then explain the reason.",
        {"commodity": {"type": "string"}, "district": {"type": "string"}, "market": {"type": "string"},
         "state": {"type": "string"}, "quintals": {"type": "number"}}, ["commodity"]),
    _fn("irrigation_advice", "Should the farmer irrigate in the next 1-7 days or wait for rain? From the forecast.",
        {"place": {"type": "string"}, "days": {"type": "integer"}}, ["place"]),
    _fn("kcc_interest", "Kisan Credit Card crop-loan interest at 7% (4% effective if repaid on time within a year): "
        "exact amounts and the saving. Use for any KCC or crop-loan interest question.",
        {"amount_rs": {"type": "number"}, "months": {"type": "number"}}, ["amount_rs"]),
]
