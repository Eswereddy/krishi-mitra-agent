"""Everyday farm-problem solvers (all computed in code, any country, no medical or chemical advice):

  storage_check    is the grain dry enough to store, and which days are good for drying? (post-harvest loss)
  livestock_heat   heat stress for cattle and poultry from the forecast (temperature-humidity index)
  loan_compare     the true cost of loan offers, including the effective yearly rate (protects against costly credit)
  compare_inputs   cost per kilogram of nutrient for fertiliser products (what to buy, not how much to apply)
  breakeven_price  the selling price needed to cover the cost of growing
"""
import httpx

# ---------------------------------------------------------------- storage

SAFE_MOISTURE = {  # maximum grain moisture (%) for safe storage: commonly cited guide values, indicative
    "maize": 13, "rice": 14, "wheat": 13, "sorghum": 13, "millet": 12, "beans": 13, "soybean": 13,
    "groundnut": 9, "chickpea": 12, "lentil": 12, "pigeonpea": 12, "sunflower": 9, "cotton": 10}
GOOD_DRYING_RAIN_MM, GOOD_DRYING_RH = 1.0, 70
DAMP_AIR_RH = 75


def _tools():
    from . import tools
    return tools


def _forecast(place: str, country: str, daily: str, days: int) -> dict:
    t = _tools()
    try:
        with httpx.Client(timeout=t.HTTP_TIMEOUT) as c:
            params = {"name": place, "count": 1}
            if country and country.upper() not in ("", "OTHER"):
                params["country_code"] = country.upper()
            geo = c.get(t.GEO_URL, params=params).json().get("results") or []
            if not geo:
                return {"error": f"place not found: {place}"}
            g = geo[0]
            f = c.get(t.FORECAST_URL, params={"latitude": g["latitude"], "longitude": g["longitude"], "timezone": "auto",
                                              "forecast_days": days, "daily": daily}).json()
        return {"place": f"{g['name']}, {g.get('admin1', '')}".strip(", "), "daily": f["daily"]}
    except Exception as e:
        return {"error": f"weather service unavailable ({type(e).__name__})"}


def _cached_forecast(key: str, place: str, country: str, daily: str, days: int) -> dict:
    return _tools()._cached(key, (str(place).strip().lower(), str(country).upper()),
                            lambda: _forecast(place, country, daily, days), ok=lambda v: "error" not in v)


def storage_check(crop: str, moisture_pct: float, place: str = "", country: str = "") -> dict:
    from . import agro
    c = agro._crop(crop)
    if not c or c["id"] not in SAFE_MOISTURE:
        return {"error": f"no safe-moisture guide for '{crop}' (it covers dry grains, pulses and oilseeds)", "known_crops": sorted(SAFE_MOISTURE)}
    try:
        m = float(moisture_pct)
    except (TypeError, ValueError):
        return {"error": "moisture_pct must be a number, e.g. 16"}
    if not 0 < m < 60:
        return {"error": "moisture_pct must be between 0 and 60"}
    limit = SAFE_MOISTURE[c["id"]]
    out = {"crop": c["id"], "moisture_pct": m, "safe_max_moisture_pct": limit, "safe_to_store": m <= limit,
           "points_to_dry": round(max(m - limit, 0), 1),
           "warning": ("Mouldy or musty grain can carry toxins: never eat it or sell it as food." if c["id"] in ("maize", "groundnut", "sorghum", "millet") else ""),
           "note": ("Safe-moisture limits are common guide values (indicative). A cheap grain moisture meter, or asking the "
                    "buyer or extension office to test, is better than guessing. Store in clean, dry, airtight containers off the floor.")}
    if place:
        raw = _cached_forecast("storage-wx", place, country, "precipitation_sum,relative_humidity_2m_mean", 5)
        if "error" not in raw:
            d = raw["daily"]
            days = list(zip(d["time"], d["precipitation_sum"], d["relative_humidity_2m_mean"]))
            good = [t for t, r, h in days if (r or 0) < GOOD_DRYING_RAIN_MM and (h if h is not None else 100) < GOOD_DRYING_RH]
            hs = [h for _t, _r, h in days if h is not None]
            out.update({"place": raw["place"], "good_drying_days": good, "average_humidity_pct": round(sum(hs) / len(hs)) if hs else None,
                        "damp_air": bool(hs) and sum(hs) / len(hs) >= DAMP_AIR_RH})
    return out


# ---------------------------------------------------------------- livestock heat

ANIMALS = {"cattle": "cattle", "cow": "cattle", "cows": "cattle", "buffalo": "cattle", "dairy": "cattle", "ox": "cattle", "bull": "cattle",
           "poultry": "poultry", "chicken": "poultry", "chickens": "poultry", "hen": "poultry", "hens": "poultry", "broiler": "poultry"}
THI_BANDS = ((72, "none"), (78, "mild"), (89, "moderate"), (98, "severe"), (10**9, "emergency"))
POULTRY_BANDS = ((28, "none"), (32, "mild"), (35, "moderate"), (38, "severe"), (10**9, "emergency"))


def thi(temp_c: float, rh_pct: float) -> float:
    """Temperature-humidity index (dairy cattle form): THI = 1.8T + 32 - (0.55 - 0.0055 RH)(1.8T - 26)."""
    return 1.8 * temp_c + 32 - (0.55 - 0.0055 * rh_pct) * (1.8 * temp_c - 26)


def livestock_heat(animal: str, place: str, country: str = "") -> dict:
    kind = ANIMALS.get(str(animal or "").strip().lower())
    if not kind:
        return {"error": f"heat guide covers cattle/buffalo and poultry, not '{animal}'", "supported": ["cattle", "buffalo", "poultry"]}
    raw = _cached_forecast("livestock-wx", place, country, "temperature_2m_max,relative_humidity_2m_min", 5)
    if "error" in raw:
        return raw
    d = raw["daily"]
    rows = []
    for day, tmax, rh in zip(d["time"], d["temperature_2m_max"], d["relative_humidity_2m_min"]):
        if tmax is None:
            continue
        if kind == "cattle":
            v = round(thi(tmax, rh if rh is not None else 50), 1)
            band = next(b for lim, b in THI_BANDS if v < lim)
            rows.append({"date": day, "max_c": tmax, "thi": v, "stress": band})
        else:
            band = next(b for lim, b in POULTRY_BANDS if tmax < lim)
            rows.append({"date": day, "max_c": tmax, "stress": band})
    if not rows:
        return {"error": "no temperature forecast available right now"}
    order = [b for _l, b in THI_BANDS]
    worst = max(rows, key=lambda r: order.index(r["stress"]))
    return {"source": "open-meteo.com forecast", "place": raw["place"], "animal": kind, "days": rows, "worst_day": worst["date"],
            "worst_stress": worst["stress"], "needs_action": worst["stress"] != "none",
            "actions": ["shade_and_air", "clean_cool_water", "feed_in_cool_hours", "no_midday_work_or_walking"] if worst["stress"] != "none" else [],
            "note": ("Heat stress is estimated from the forecast daily maximum and minimum humidity (cattle: temperature-humidity index "
                     "bands for dairy cattle; poultry: air temperature). A guide only. If animals pant heavily, stop eating or collapse, "
                     "call a veterinarian or animal health worker at once.")}


# ---------------------------------------------------------------- loans

def _apr_from_payments(principal: float, payment: float, n: int) -> float:
    """Effective yearly rate (%) for `n` equal monthly payments that repay a net amount `principal` (bisection on the monthly rate)."""
    lo, hi = 0.0, 5.0
    for _ in range(200):
        r = (lo + hi) / 2
        pv = payment * n if r == 0 else payment * (1 - (1 + r) ** -n) / r
        lo, hi = (r, hi) if pv > principal else (lo, r)
    r = (lo + hi) / 2
    return round(((1 + r) ** 12 - 1) * 100, 1)


def loan_compare(offers: list) -> dict:
    """Compare loan offers. Each offer: name, amount, rate_pct, rate_per ('month' or 'year'), months, method ('flat' or 'reducing'), fee_pct."""
    if not isinstance(offers, list) or not offers or len(offers) > 5:
        return {"error": "give between 1 and 5 offers"}
    rows = []
    for i, o in enumerate(offers):
        try:
            amt, rate, months = float(o["amount"]), float(o["rate_pct"]), int(o["months"])
            fee = float(o.get("fee_pct") or 0)
        except (KeyError, TypeError, ValueError):
            return {"error": f"offer {i + 1}: amount, rate_pct and months are required numbers"}
        per = "year" if str(o.get("rate_per", "year")).lower().startswith("y") else "month"
        method = "flat" if str(o.get("method", "reducing")).lower().startswith("f") else "reducing"
        if amt <= 0 or months <= 0 or months > 120 or rate < 0 or not 0 <= fee < 50:
            return {"error": f"offer {i + 1}: check amount, months (1-120), rate and fee"}
        mrate = rate / 100 / (12 if per == "year" else 1)
        if method == "flat":
            interest = amt * mrate * months
            pay = (amt + interest) / months
        else:
            pay = amt / months if mrate == 0 else amt * mrate / (1 - (1 + mrate) ** -months)
            interest = pay * months - amt
        fees = amt * fee / 100
        net = amt - fees                                     # money the farmer actually receives
        total = pay * months
        rows.append({"name": str(o.get("name") or f"Offer {i + 1}")[:40], "amount": round(amt), "months": months, "method": method,
                     "monthly_payment": round(pay, 2), "total_interest": round(interest), "fees": round(fees),
                     "total_repay": round(total), "extra_paid_vs_amount": round(total + fees - amt),
                     "effective_annual_rate_pct": _apr_from_payments(net, pay, months)})
    rows.sort(key=lambda r: r["effective_annual_rate_pct"])
    return {"offers": rows, "cheapest": rows[0]["name"],
            "note": ("The effective yearly rate counts fees and equal monthly payments, so offers quoted per month, per year or "
                     "'flat' can be compared fairly. Flat rates cost far more than they look. Check there are no other charges; "
                     "ask for the repayment schedule in writing before signing.")}


# ---------------------------------------------------------------- inputs and break-even

def compare_inputs(products: list) -> dict:
    """Cost per kg of nutrient for fertiliser products: each has name, price, bag_kg and nutrient percentages n_pct, p2o5_pct, k2o_pct."""
    if not isinstance(products, list) or not products or len(products) > 6:
        return {"error": "give between 1 and 6 products"}
    rows = []
    for i, p in enumerate(products):
        try:
            price, bag = float(p["price"]), float(p["bag_kg"])
            n, ph, k = (float(p.get(x) or 0) for x in ("n_pct", "p2o5_pct", "k2o_pct"))
        except (KeyError, TypeError, ValueError):
            return {"error": f"product {i + 1}: price and bag_kg are required numbers"}
        if price <= 0 or bag <= 0 or min(n, ph, k) < 0 or n + ph + k <= 0 or n > 100 or ph > 100 or k > 100:
            return {"error": f"product {i + 1}: check price, bag size and nutrient percentages"}
        row = {"name": str(p.get("name") or f"Product {i + 1}")[:40], "price_per_bag": price, "bag_kg": bag,
               "price_per_kg_product": round(price / bag, 2)}
        for label, pct in (("n", n), ("p2o5", ph), ("k2o", k)):
            if pct > 0:
                row[f"cost_per_kg_{label}"] = round(price / (bag * pct / 100), 2)
        rows.append(row)
    best = {}
    for label in ("n", "p2o5", "k2o"):
        have = [r for r in rows if f"cost_per_kg_{label}" in r]
        if len(have) > 1:
            best[label] = min(have, key=lambda r: r[f"cost_per_kg_{label}"])["name"]
    return {"products": rows, "cheapest_per_nutrient": best,
            "note": ("This compares the price of the nutrient only. It does not say how much your crop needs: that depends on soil, "
                     "crop and yield, so ask the extension officer or use a soil test. Cheapest is not always right if the crop needs a "
                     "different nutrient.")}


def breakeven_price(total_cost: float, expected_quantity: float, unit: str = "kg", margin_pct: float = 20) -> dict:
    try:
        cost, qty, mg = float(total_cost), float(expected_quantity), float(margin_pct)
    except (TypeError, ValueError):
        return {"error": "total_cost and expected_quantity must be numbers"}
    if cost <= 0 or qty <= 0 or not 0 <= mg <= 200:
        return {"error": "total_cost and expected_quantity must be above zero"}
    be = cost / qty
    return {"total_cost": round(cost, 2), "expected_quantity": qty, "unit": str(unit)[:12], "breakeven_price_per_unit": round(be, 2),
            "target_margin_pct": mg, "price_for_margin_per_unit": round(be * (1 + mg / 100), 2),
            "note": "Include seed, labour (also your own), water, inputs, transport and any loan interest in the cost, otherwise the real break-even is higher."}


FUNCS = {"storage_check": storage_check, "livestock_heat": livestock_heat, "loan_compare": loan_compare,
         "compare_inputs": compare_inputs, "breakeven_price": breakeven_price}


def _fn(name, desc, props, required):
    return {"type": "function", "function": {"name": name, "description": desc,
                                              "parameters": {"type": "object", "properties": props, "required": required}}}


SPECS = [
    _fn("storage_check", "Is harvested grain dry enough to store, and which days are good for drying? Use when a farmer gives a moisture "
        "reading or asks about storing, drying or spoilage of grain, pulses or oilseeds. Any country.",
        {"crop": {"type": "string"}, "moisture_pct": {"type": "number", "description": "grain moisture percent, e.g. 16"},
         "place": {"type": "string"}, "country": {"type": "string"}}, ["crop", "moisture_pct"]),
    _fn("livestock_heat", "Heat stress risk for cattle, buffalo or poultry over the next 5 days. Use for 'my cows are suffering in the heat', "
        "'will it be too hot for my chickens'. Never give medicine advice.",
        {"animal": {"type": "string", "description": "cattle, buffalo or poultry"}, "place": {"type": "string"}, "country": {"type": "string"}},
        ["animal", "place"]),
    _fn("loan_compare", "True cost of loan offers: total interest, fees and the effective yearly rate, sorted cheapest first. Use when a farmer "
        "is offered a loan or credit by a bank, trader, moneylender or microfinance and asks which is better or if it is fair.",
        {"offers": {"type": "array", "items": {"type": "object", "properties": {
            "name": {"type": "string"}, "amount": {"type": "number"}, "rate_pct": {"type": "number"},
            "rate_per": {"type": "string", "description": "month or year"}, "months": {"type": "integer"},
            "method": {"type": "string", "description": "flat or reducing"}, "fee_pct": {"type": "number"}},
            "required": ["amount", "rate_pct", "months"]}}}, ["offers"]),
    _fn("compare_inputs", "Cost per kilogram of nutrient (N, P2O5, K2O) for fertiliser products the farmer can buy, to pick the best value. "
        "Says nothing about how much to apply.",
        {"products": {"type": "array", "items": {"type": "object", "properties": {
            "name": {"type": "string"}, "price": {"type": "number"}, "bag_kg": {"type": "number"},
            "n_pct": {"type": "number"}, "p2o5_pct": {"type": "number"}, "k2o_pct": {"type": "number"}}, "required": ["price", "bag_kg"]}}}, ["products"]),
    _fn("breakeven_price", "The selling price per unit needed to cover the cost of growing (and a target margin). Use for 'at what price do I "
        "make a profit'.",
        {"total_cost": {"type": "number"}, "expected_quantity": {"type": "number"}, "unit": {"type": "string"},
         "margin_pct": {"type": "number"}}, ["total_cost", "expected_quantity"]),
]
