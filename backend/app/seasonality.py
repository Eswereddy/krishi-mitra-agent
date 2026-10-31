"""Price seasonality: in which months does this crop usually sell highest and lowest in my country?

Most smallholders sell at harvest, when prices are lowest. From up to six years of WFP monthly prices we compute, in code,
a seasonal index per calendar month (each month's price divided by that year's average, averaged over the years), then say
which months were highest and lowest and how big the gap is. That turns "should I store and wait?" into a number the
farmer can weigh against his own storage cost and losses. A history, not a forecast: it never promises a price.
"""
from statistics import mean

from . import globalprices as gp, locale as loc

MIN_MONTHS_IN_YEAR = 9       # a year with fewer monthly prices is too patchy to compare
MIN_YEARS = 2


def _series(rows: list[dict], want: str, market: str) -> tuple[list[dict], dict]:
    hits = [r for r in rows if want in r["commodity"].lower() and (not market or market.lower() in r["market"].lower())]
    groups: dict[tuple, list] = {}
    for r in hits:
        groups.setdefault((r["market"], r["unit"], r["pricetype"], r["currency"]), []).append(r)
    if not groups:
        return [], {}
    key = max(groups, key=lambda k: len(groups[k]))          # the market with the longest history
    return groups[key], {"market": key[0], "unit": key[1], "pricetype": key[2], "currency": key[3]}


def price_seasonality(commodity: str, country: str, market: str = "") -> dict:
    iso = str(country or "").upper()
    if iso == "IN":
        return {"error": "for India use get_price_trend and hold_or_sell"}
    if iso not in loc.COUNTRIES or iso == "OTHER":
        return {"error": f"unknown country code {country}; ask the farmer what prices he has seen in past years"}
    try:
        rows = gp._load(iso)
    except Exception as e:
        return {"error": f"price data unavailable ({type(e).__name__})"}
    if not rows:
        return {"error": f"no public price data found for {loc.COUNTRIES[iso][0]}"}
    want = str(commodity or "").lower().strip()
    series, meta = _series(rows, want, market)
    if not series:
        return {"error": f"no price found for {commodity} in {loc.COUNTRIES[iso][0]}",
                "available_commodities": sorted({r["commodity"] for r in rows})[:12]}
    by_year: dict[str, dict[int, float]] = {}
    for r in series:
        by_year.setdefault(r["date"][:4], {})[int(r["date"][5:7])] = r["price"]   # one price per month (the later row wins)
    ratios: dict[int, list[float]] = {m: [] for m in range(1, 13)}
    years_used = []
    for y, months in sorted(by_year.items()):
        if len(months) < MIN_MONTHS_IN_YEAR:
            continue
        avg = mean(months.values())
        if avg <= 0:
            continue
        years_used.append(y)
        for m, p in months.items():
            ratios[m].append(p / avg)
    if len(years_used) < MIN_YEARS:
        return {"error": f"not enough price history for {commodity} in {loc.COUNTRIES[iso][0]} to see a seasonal pattern "
                         f"(need {MIN_YEARS}+ years with {MIN_MONTHS_IN_YEAR}+ months)"}
    idx = {m: round(mean(v) * 100) for m, v in ratios.items() if len(v) >= MIN_YEARS}
    if len(idx) < 6:
        return {"error": "price history has too many gaps to see a seasonal pattern"}
    ranked = sorted(idx, key=idx.get)
    peak, trough = ranked[-1], ranked[0]
    return {"source": "WFP food prices via HDX (monthly history, not live)", "country": loc.COUNTRIES[iso][0], "commodity": commodity,
            **meta, "years_used": years_used, "index_by_month": [{"month": m, "index": idx[m]} for m in sorted(idx)],
            "highest_months": sorted(ranked[-2:]), "lowest_months": sorted(ranked[:2]), "peak_month": peak, "trough_month": trough,
            "peak_vs_trough_pct": round((idx[peak] / idx[trough] - 1) * 100),
            "months_from_trough_to_peak": (peak - trough) % 12,
            "note": ("Index 100 = that year's average price. This is how prices behaved in past years at one market, not a forecast: "
                     "a bad harvest or a policy change can break the pattern. Storing only pays if the gap is bigger than your "
                     "storage cost, losses to damp and pests, and the interest on money you wait for.")}


FUNCS = {"price_seasonality": price_seasonality}
SPECS = [{"type": "function", "function": {
    "name": "price_seasonality",
    "description": ("In which months does a crop usually sell highest and lowest in a country OUTSIDE India (up to 6 years of WFP monthly "
                    "prices, seasonal index per month, gap between the best and worst month). Use for 'should I store and sell later', "
                    "'when is the best month to sell'. History, not a forecast."),
    "parameters": {"type": "object", "properties": {"commodity": {"type": "string"}, "country": {"type": "string"},
                                                    "market": {"type": "string"}}, "required": ["commodity", "country"]}}}]
