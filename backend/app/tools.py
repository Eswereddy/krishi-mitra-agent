"""Tools the farming agent can call. Each returns plain JSON-serialisable data."""
import json
from pathlib import Path

DATA = Path(__file__).parent / "data"


def get_mandi_price(commodity: str, market: str = "") -> dict:
    """Look up mandi price. Currently reads SAMPLE data (see data/mandi_sample.json)."""
    raw = json.loads((DATA / "mandi_sample.json").read_text())
    rows = [
        p for p in raw["prices"]
        if p["commodity"].lower() == commodity.lower()
        and (not market or p["market"].lower() == market.lower())
    ]
    return {"source": "sample-data", "note": raw["_note"], "results": rows}


def check_schemes(owns_land: bool = False, grows_notified_crop: bool = True,
                  state: str = "Andhra Pradesh") -> dict:
    """Return schemes whose simple eligibility rules match the farmer's profile."""
    schemes = json.loads((DATA / "schemes.json").read_text())
    profile = {"owns_land": owns_land, "grows_notified_crop": grows_notified_crop,
               "is_farmer": True, "state": state}
    matched = []
    for s in schemes:
        if all(profile.get(k) == v for k, v in s["rules"].items()):
            matched.append({k: s[k] for k in ("name", "benefit", "how_to_apply", "verify_at")})
    return {"matched": matched, "disclaimer": "Indicative only; confirm with the official office."}


TOOL_FUNCS = {"get_mandi_price": get_mandi_price, "check_schemes": check_schemes}

TOOL_SPECS = [
    {"type": "function", "function": {
        "name": "get_mandi_price",
        "description": "Get the current mandi (market) price per quintal for a crop.",
        "parameters": {"type": "object", "properties": {
            "commodity": {"type": "string"}, "market": {"type": "string"}},
            "required": ["commodity"]}}},
    {"type": "function", "function": {
        "name": "check_schemes",
        "description": "Find government schemes a farmer may be eligible for.",
        "parameters": {"type": "object", "properties": {
            "owns_land": {"type": "boolean"},
            "grows_notified_crop": {"type": "boolean"},
            "state": {"type": "string"}},
            "required": ["owns_land"]}}},
]


def run_tool(name: str, args: dict) -> dict:
    fn = TOOL_FUNCS.get(name)
    if not fn:
        return {"error": f"unknown tool {name}"}
    try:
        return fn(**args)
    except TypeError as e:
        return {"error": str(e)}
