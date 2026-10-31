"""Market prices outside India: WFP Food Prices (monthly retail/wholesale prices from ~100 countries, published on the
Humanitarian Data Exchange). Same honesty rules as the Indian price tools: figures come only from the data, the source and
its age are always stated, and when a country has no data the tool says so instead of guessing.

HDX is read through its public CKAN API: package_show -> the CSV resource -> parsed here. The CSV has a header row, an
HXL tag row (starts with "#") and then: date, admin1, admin2, market, latitude, longitude, category, commodity, unit,
priceflag, pricetype, currency, price, usdprice.
"""
import csv
import io

import httpx

from . import locale as loc

CKAN = "https://data.humdata.org/api/3/action"
TIMEOUT = 40
MAX_BYTES = 40 * 1024 * 1024
KEEP_MONTHS = 24


def _get_json(path: str, params: dict) -> dict:
    with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as c:
        r = c.get(f"{CKAN}/{path}", params=params)
        r.raise_for_status()
        return r.json()


def _get_text(url: str) -> str:
    with httpx.Client(timeout=TIMEOUT, follow_redirects=True) as c, c.stream("GET", url) as r:
        r.raise_for_status()
        buf, size = [], 0
        for chunk in r.iter_bytes():
            size += len(chunk)
            if size > MAX_BYTES:
                raise ValueError("price file too large")
            buf.append(chunk)
    return b"".join(buf).decode("utf-8-sig", errors="replace")


def _slug(name: str) -> str:
    return name.lower().replace(" ", "-")


def _csv_url(package: dict) -> str | None:
    """The main WFP price file in a dataset (not the quality-check or 'qc' file)."""
    for r in package.get("resources") or []:
        name = (str(r.get("name", "")) + " " + str(r.get("url", ""))).lower()
        if str(r.get("format", "")).lower() == "csv" and "food_prices" in name.replace(" ", "_").replace("-", "_") \
                and "qc" not in name and "quality" not in name:
            return r.get("url")
    return None


def find_csv(country_name: str) -> str | None:
    try:
        pkg = _get_json("package_show", {"id": f"wfp-food-prices-for-{_slug(country_name)}"}).get("result") or {}
        url = _csv_url(pkg)
        if url:
            return url
    except Exception:
        pass
    found = _get_json("package_search", {"q": f"wfp food prices {country_name}", "rows": 8}).get("result", {}).get("results") or []
    for pkg in found:
        if str(pkg.get("name", "")).startswith("wfp-food-prices") and country_name.lower().split()[0] in str(pkg.get("title", "")).lower():
            url = _csv_url(pkg)
            if url:
                return url
    return None


def parse_rows(text: str) -> list[dict]:
    """CSV text -> rows, skipping the HXL tag row."""
    rows = []
    for rec in csv.DictReader(io.StringIO(text)):
        if str(rec.get("date", "")).startswith("#") or not rec.get("price"):
            continue
        try:
            rows.append({"date": rec["date"][:10], "market": rec.get("market", ""), "admin1": rec.get("admin1", ""),
                         "commodity": rec.get("commodity", ""), "unit": rec.get("unit", ""), "pricetype": rec.get("pricetype", ""),
                         "currency": rec.get("currency", ""), "price": float(rec["price"]),
                         "usdprice": float(rec["usdprice"]) if rec.get("usdprice") not in (None, "") else None})
        except (ValueError, KeyError):
            continue
    return rows


def _load(country_iso2: str) -> list[dict]:
    from . import tools
    name = loc.COUNTRIES[country_iso2][0]

    def fetch():
        url = find_csv(name)
        if not url:
            return []
        rows = parse_rows(_get_text(url))
        newest = max((r["date"] for r in rows), default="")
        if newest:                                     # keep the recent past only: small, and what matters to a farmer
            cy, cm = divmod(int(newest[:4]) * 12 + int(newest[5:7]) - 1 - KEEP_MONTHS, 12)
            cut = f"{cy}-{cm + 1:02d}"
            rows = [r for r in rows if r["date"][:7] >= cut]
        return rows
    ttl_ok = tools._cached("wfp-rows", country_iso2, fetch, ok=lambda v: bool(v))
    return ttl_ok


def _fmt(v: float) -> float | int:
    return int(v) if float(v).is_integer() else round(v, 2)


def get_market_price(commodity: str, country: str, market: str = "") -> dict:
    """Latest known price per market for a food crop outside India, plus a short trend. Monthly data: say how old it is."""
    iso = str(country or "").upper()
    if iso == "IN":
        return {"error": "for India use get_mandi_price"}
    if iso not in loc.COUNTRIES or iso == "OTHER":
        return {"error": f"unknown country code {country}; ask the farmer for the price he was offered and use calculate_revenue"}
    try:
        rows = _load(iso)
    except Exception as e:
        return {"error": f"price data unavailable ({type(e).__name__}); ask the farmer for the price he was offered"}
    if not rows:
        return {"error": f"no public price data found for {loc.COUNTRIES[iso][0]}; ask the farmer for the price he was offered"}
    want = str(commodity or "").lower().strip()
    hits = [r for r in rows if want and want in r["commodity"].lower() and (not market or market.lower() in r["market"].lower())]
    if not hits:
        names = sorted({r["commodity"] for r in rows})[:12]
        return {"error": f"no price found for {commodity} in {loc.COUNTRIES[iso][0]}", "available_commodities": names}
    latest: dict[tuple, dict] = {}
    for r in sorted(hits, key=lambda x: x["date"], reverse=True):       # newest row per market and unit
        latest.setdefault((r["market"], r["unit"], r["pricetype"]), r)
    ranked = sorted(latest.values(), key=lambda r: r["date"], reverse=True)[:6]
    top = ranked[0]
    series_rows = sorted([r for r in hits if (r["market"], r["unit"], r["pricetype"]) == (top["market"], top["unit"], top["pricetype"])],
                         key=lambda x: x["date"])[-12:]
    out = {"source": "WFP food prices via HDX (monthly, not live)", "country": loc.COUNTRIES[iso][0], "commodity": commodity,
           "results": [{"market": r["market"], "region": r["admin1"], "date": r["date"], "unit": r["unit"], "pricetype": r["pricetype"],
                        "currency": r["currency"], "price": _fmt(r["price"]),
                        "usd_price": None if r["usdprice"] is None else _fmt(r["usdprice"])} for r in ranked],
           "note": f"Latest data is from {top['date']}. This is a monthly market survey, not today's price: confirm with a trader "
                   "or the market before selling."}
    if len(series_rows) >= 2:
        first, last = series_rows[0]["price"], series_rows[-1]["price"]
        change = round((last - first) / first * 100, 1) if first else 0
        out["trend"] = {"market": top["market"], "unit": top["unit"], "currency": top["currency"],
                        "series": [{"date": r["date"], "price": _fmt(r["price"])} for r in series_rows], "change_pct": change,
                        "trend": "rising" if change >= 5 else "falling" if change <= -5 else "steady",
                        "highest": _fmt(max(r["price"] for r in series_rows)), "lowest": _fmt(min(r["price"] for r in series_rows))}
    return out


FUNCS = {"get_market_price": get_market_price}
SPECS = [{"type": "function", "function": {
    "name": "get_market_price",
    "description": "Market price of a food crop OUTSIDE India (WFP monthly market data: per market, with unit, currency and a "
                   "trend). Use it instead of get_mandi_price / best_markets / get_price_trend when the farmer's country is not India.",
    "parameters": {"type": "object", "properties": {
        "commodity": {"type": "string", "description": "e.g. Maize, Rice, Beans, Sorghum, Cassava"},
        "country": {"type": "string", "description": "ISO 2-letter code from the farmer profile, e.g. KE, NG, BR"},
        "market": {"type": "string"}}, "required": ["commodity", "country"]}}}]
