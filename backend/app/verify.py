"""Verification layer (idea from Meta's Agents 102 / legal-agent-workshop):
the agent's final answer is checked by plain code, outside the model's control.

Rules, applied to every figure in the answer:
  * money (after Rs / rupee-sign, or before rupees / "per quintal")  -> must be a price/amount field in a tool result
  * percent, degrees, millimetres                                   -> must match a rain-chance / change / temperature / rain field
                                                                      (small rounding allowed: 5.3 may be said as 5)
  * any other number of 3+ digits                                   -> must appear somewhere in a tool result
Otherwise the answer is sent back for a rewrite, and if it still fails the farmer sees an explicit
"not verified" warning instead of a confident wrong number. A money figure borrowed from the wrong kind of
field (a year, a phone number, a rain percentage) no longer passes just because the digits exist somewhere.
"""
import json
import re

_TELUGU_DIGITS = str.maketrans("౦౧౨౩౪౫౬౭౮౯०१२३४५६७८९", "01234567890123456789")
_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")

_CUR = (r"\$|€|£|₦|₱|₫|฿|৳|R\$|KSh|USh|TSh|GH₵|USD|EUR|GBP|KES|UGX|TZS|NGN|GHS|ZAR|ETB|RWF|XOF|XAF|BDT|PKR|NPR|LKR|IDR|PHP|VND|THB|"
        r"MMK|KHR|BRL|MXN|COP|PEN|ARS|CLP|MAD|EGP|MWK|ZMW|MZN|GTQ|HNL")
_CUR_WORDS = r"dollars?|euros?|pesos?|shillings?|naira|cedis?|francs?|reais|real|rupiah|baht|dong|birr|kwacha"
_MONEY_PRE = rf"(?:₹|Rs\.?|INR|రూ\.?|रु\.?|{_CUR})"
_MONEY_POST = rf"(?:₹|Rs\b\.?|INR|rupees?|రూపాయ\w*|రూ\b\.?|रुपय\w*|रु\b\.?|/-|per\s*quintal|/\s*quintal|{_CUR}|{_CUR_WORDS})"
_CLAIM = re.compile(
    rf"(?P<pre>{_MONEY_PRE}\s*)?(?P<num>\d[\d,]*(?:\.\d+)?)"
    rf"(?P<post>\s*(?:%|°\s*[CcFf]?|mm\b|మి\.?\s?మీ|मिमी|{_MONEY_POST}))?",
    re.I,
)
_MONEY_KEYS = ("price", "revenue", "profit", "expenses", "highest", "lowest", "rs")
_PCT_KEYS = ("pct", "chance", "percent")
_TEMP_KEYS = ("max_c", "min_c", "temp")
_MM_KEYS = ("rain_mm", "precip", "_mm")
_TOLERANCE = {"pct": 1.0, "temp": 0.5, "mm": 0.5}


def _norm(n: str) -> str:
    n = n.replace(",", "").rstrip(".")
    return n.split(".")[0] if n.endswith(".0") else n


def numbers(text: str) -> set[str]:
    text = text.translate(_TELUGU_DIGITS)
    return {n for n in (_norm(m) for m in _NUM.findall(text)) if n}


def _floats(text: str) -> list[float]:
    out = []
    for m in _NUM.findall(text.translate(_TELUGU_DIGITS)):
        try:
            out.append(float(m.replace(",", "").rstrip(".")))
        except ValueError:
            pass
    return out


def _collect(obj, key: str, sets: dict) -> None:
    """Walk a tool result and file each number under the kind of field it came from."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            _collect(v, str(k).lower(), sets)
    elif isinstance(obj, list):
        for v in obj:
            _collect(v, key, sets)
    elif isinstance(obj, bool) or obj is None:
        return
    elif isinstance(obj, (int, float)):
        vals = [float(obj), abs(float(obj))]   # a gap of -50 may be said as "Rs 50 below"
        _file(vals, key, sets)
    elif isinstance(obj, str):
        # amounts written in text, e.g. "Rs 6,000 per year"
        for m in re.finditer(rf"{_MONEY_PRE}\s*(\d[\d,]*(?:\.\d+)?)", obj, re.I):
            sets["money"].extend(_floats(m.group(1)))


def _file(vals: list[float], key: str, sets: dict) -> None:
    if any(k in key for k in _MONEY_KEYS):
        sets["money"].extend(vals)
    if any(k in key for k in _PCT_KEYS):
        sets["pct"].extend(vals)
    if any(k in key for k in _TEMP_KEYS):
        sets["temp"].extend(vals)
    if any(k in key for k in _MM_KEYS):
        sets["mm"].extend(vals)


def _kind(pre: str | None, post: str | None) -> str:
    p = (post or "").strip().lower()
    if pre or re.fullmatch(_MONEY_POST, p, re.I):
        return "money"
    if p == "%":
        return "pct"
    if p.startswith("°"):
        return "temp"
    if p:
        return "mm"
    return "plain"


def verify_answer(answer: str, steps: list[dict]) -> dict:
    """Return {"passed": bool, "unverified": [figures that failed], "checked": number of figures checked}."""
    results = [s.get("result") for s in steps]
    allowed = numbers(json.dumps(results, ensure_ascii=False))
    sets: dict = {"money": [], "pct": [], "temp": [], "mm": []}
    _collect(results, "", sets)

    unverified, checked = [], 0
    for m in _CLAIM.finditer(answer.translate(_TELUGU_DIGITS)):
        raw = m.group("num")
        kind = _kind(m.group("pre"), m.group("post"))
        if kind == "plain":
            if len(_norm(raw).split(".")[0]) < 3:
                continue                                   # small plain numbers (list items, "3 days") are not claims
            checked += 1
            ok = _norm(raw) in allowed
        else:
            checked += 1
            try:
                val = float(raw.replace(",", "").rstrip("."))
            except ValueError:
                continue
            tol = _TOLERANCE.get(kind, 0.0)
            ok = any(abs(val - a) <= tol for a in sets[kind]) if kind != "money" else \
                any(abs(val - a) < 0.5 for a in sets["money"])
        if not ok:
            unverified.append(_norm(raw))
    unverified = sorted(set(unverified))
    return {"passed": not unverified, "unverified": unverified, "checked": checked}


def warning(unverified: list[str], lang: str = "te") -> str:
    from .lang import WARNING
    return WARNING.get(lang, WARNING["en"]).format(n=", ".join(unverified))
