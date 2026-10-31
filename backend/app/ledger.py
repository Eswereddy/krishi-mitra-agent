"""Khata: a voice farm ledger. The farmer says "bought urea for 1500" or "sold 8 quintals at 7000" in any language;
we turn it into one structured entry, the farmer confirms it, and it is stored ON THE DEVICE (no accounts).
From the entries we compute an exact season report (cost per acre, income, net) a bank or insurer can read.

Safety rules, same spirit as the rest of the app: the model only EXTRACTS what was said; an amount that does not
appear in the farmer's own words is flagged for confirmation, never silently trusted; every total is plain arithmetic.
"""
import json
import re
from datetime import date

from . import config, lang as langmod, meta_client
from .verify import _NUM, _TELUGU_DIGITS

EXPENSE = ("seed", "fertilizer", "pesticide", "labour", "irrigation", "machinery", "transport", "rent", "other")
INCOME = ("sale", "subsidy", "other_income")
MAX_AMOUNT = 100_000_000
MAX_ENTRIES = 500

KEYWORDS = {
    "seed": ("seed", "విత్తన", "बीज"),
    "fertilizer": ("urea", "dap", "fertili", "potash", "manure", "ఎరువు", "యూరియా", "खाद", "उर्वरक", "यूरिया"),
    "pesticide": ("pesticide", "spray", "insecticide", "fungicide", "మందు", "పిచికారీ", "दवा", "छिड़काव", "कीटनाशक"),
    "labour": ("labour", "labor", "wage", "కూలి", "మజూరి", "मज़दूरी", "मजदूरी", "मज़दूर"),
    "irrigation": ("diesel", "water", "motor", "electric", "pump", "డీజిల్", "పంపు", "కరెంట్", "डीजल", "बिजली", "सिंचाई", "पंप"),
    "machinery": ("tractor", "harvester", "rotavator", "ట్రాక్టర్", "కోత యంత్ర", "ट्रैक्टर", "हार्वेस्टर"),
    "transport": ("transport", "vehicle", "freight", "రవాణా", "బండి", "ढुलाई", "भाड़ा", "ट्रांसपोर्ट"),
    "rent": ("rent", "lease", "కౌలు", "किराया", "पट्टा"),
}
SALE_WORDS = ("sold", "sale", "sell", "అమ్మ", "అమ్మాను", "బేచ", "बेचा", "बेच", "बिक्री")
SUBSIDY_WORDS = ("subsidy", "pm-kisan", "pm kisan", "సబ్సిడీ", "సహాయం", "सब्सिडी", "सम्मान निधि")
QUINTAL = r"(?:quintals?|qtl|q\b|క్వింటా\w*|क्विंटल)"
CROPS = {"paddy": ("paddy", "rice", "వరి", "धान"), "groundnut": ("groundnut", "peanut", "వేరుశనగ", "मूंगफली"),
         "cotton": ("cotton", "పత్తి", "कपास"), "chilli": ("chilli", "chili", "మిరప", "मिर्च"),
         "maize": ("maize", "corn", "మొక్కజొన్న", "मक्का"), "tomato": ("tomato", "టమోటా", "టమాటో", "टमाटर"),
         "redgram": ("red gram", "tur", "కంది", "अरहर")}


def _norm(text: str) -> str:
    return str(text or "").translate(_TELUGU_DIGITS)


def _numbers(text: str) -> list[float]:
    out = []
    for m in _NUM.findall(_norm(text)):
        try:
            out.append(float(m.replace(",", "").rstrip(".")))
        except ValueError:
            pass
    return out


def _has(text: str, words) -> bool:
    low = text.lower()
    return any(w in low for w in words)


def guess_crop(text: str, default: str = "") -> str:
    for crop, words in CROPS.items():
        if _has(text, words):
            return crop
    return default


def rule_parse(text: str, default_crop: str = "") -> dict:
    """Deterministic fallback (no model): keyword category, numbers from the text, sale = quantity x price."""
    t = _norm(text)
    nums = _numbers(t)
    qty = None
    m = re.search(rf"(\d[\d,]*(?:\.\d+)?)\s*{QUINTAL}", t, re.I)
    if m:
        qty = float(m.group(1).replace(",", ""))
    others = [n for n in nums if n != qty]
    amount = None
    if _has(t, SALE_WORDS) or _has(t, SUBSIDY_WORDS):
        kind = "income"
        cat = "subsidy" if _has(t, SUBSIDY_WORDS) else "sale"
        if cat == "sale" and qty and others:
            amount = round(qty * max(others))          # "sold 8 quintals at 7000" -> 56000
        elif others or nums:
            amount = max(others or nums)
    else:
        kind = "expense"
        cat = next((c for c, w in KEYWORDS.items() if _has(t, w)), "other")
        amount = max(nums) if nums else None
    return {"type": kind, "category": cat, "amount_rs": amount, "quantity_q": qty,
            "crop": guess_crop(t, default_crop), "note": text.strip()[:80]}


def _clean(d: dict, text: str, default_crop: str) -> dict | None:
    """Validate whatever the model (or the rules) produced. Returns None if it is not a usable entry."""
    kind = "income" if d.get("type") == "income" else "expense"
    allowed = INCOME if kind == "income" else EXPENSE
    cat = d.get("category") if d.get("category") in allowed else ("other_income" if kind == "income" else "other")
    try:
        amount = float(d.get("amount_rs"))
    except (TypeError, ValueError):
        return None
    if not (0 < amount <= MAX_AMOUNT):
        return None
    try:
        qty = float(d.get("quantity_q")) if d.get("quantity_q") not in (None, "") else None
    except (TypeError, ValueError):
        qty = None
    if qty is not None and not (0 < qty <= 100000):
        qty = None
    nums = _numbers(text)
    q = qty if qty else 0
    grounded = any(abs(amount - n) < 0.5 for n in nums) or bool(q and any(abs(amount - q * n) < 0.5 for n in nums))
    return {"type": kind, "category": cat, "amount_rs": round(amount), "quantity_q": qty,
            "crop": str(d.get("crop") or default_crop or "").strip().lower()[:30], "note": str(d.get("note") or text)[:80],
            "amount_in_words": grounded}


PROMPT = (
    "Extract ONE farm money entry from the farmer's sentence (any language). Reply with JSON only, no other text: "
    '{"type":"expense|income","category":"<expense: seed|fertilizer|pesticide|labour|irrigation|machinery|transport|rent|other; '
    'income: sale|subsidy|other_income>","amount_rs":<total rupees as a number or null>,"quantity_q":<quintals sold or null>,'
    '"crop":"<english crop name or empty>","note":"<3-6 words>"}. '
    "Use ONLY numbers the farmer said. If he gives quantity and price per quintal, amount_rs is quantity x price. "
    "If no amount was said, amount_rs is null."
)


def _json_from(text: str) -> dict | None:
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        v = json.loads(m.group(0))
    except ValueError:
        return None
    return v if isinstance(v, dict) else None


async def parse_entry(text: str, default_crop: str = "") -> dict:
    """Sentence -> entry (to be confirmed by the farmer). Model first, rules if the model is unavailable or unsure."""
    text = str(text or "").strip()[:300]
    if not text:
        return {"error": "empty"}
    via = "rules"
    entry = None
    if not config.MOCK_MODE and config.CHAT_KEY:
        try:
            raw = await meta_client.chat([{"role": "system", "content": PROMPT}, {"role": "user", "content": text}], temperature=0)
            entry = _clean(_json_from(raw) or {}, text, default_crop)
            via = "model" if entry else "rules"
        except Exception:
            entry = None
    if entry is None:
        entry = _clean(rule_parse(text, default_crop), text, default_crop)
    if entry is None:
        return {"error": "no_amount"}
    entry["via"] = via
    entry["date"] = date.today().isoformat()
    return entry


# ---------------------------------------------------------------- season report

T = {
    "en": {"head": "🌾 Season report", "acres": "Land: {a} acres", "inc": "Income: ₹{x}", "exp": "Cost of cultivation: ₹{x}",
           "net": "Net {w}: ₹{x}", "profit": "profit", "loss": "loss", "peracre": "Cost per acre: ₹{x}",
           "cats": "Where the money went:", "crop": "{c}: income ₹{i}, cost ₹{e}", "foot": "Prepared from the farmer's own records on Krishi Mitra. Not an audited statement.",
           "cat": {"seed": "Seed", "fertilizer": "Fertiliser", "pesticide": "Spray / pesticide", "labour": "Labour",
                   "irrigation": "Irrigation / fuel", "machinery": "Machinery", "transport": "Transport", "rent": "Land rent", "other": "Other"}},
    "te": {"head": "🌾 సీజన్ నివేదిక", "acres": "భూమి: {a} ఎకరాలు", "inc": "ఆదాయం: ₹{x}", "exp": "సాగు ఖర్చు: ₹{x}",
           "net": "నికర {w}: ₹{x}", "profit": "లాభం", "loss": "నష్టం", "peracre": "ఎకరాకు ఖర్చు: ₹{x}",
           "cats": "డబ్బు ఎక్కడ ఖర్చైంది:", "crop": "{c}: ఆదాయం ₹{i}, ఖర్చు ₹{e}", "foot": "రైతు స్వంత రికార్డుల నుంచి కృషి మిత్ర తయారుచేసింది. ఆడిట్ చేసిన నివేదిక కాదు.",
           "cat": {"seed": "విత్తనాలు", "fertilizer": "ఎరువులు", "pesticide": "మందులు / పిచికారీ", "labour": "కూలీలు",
                   "irrigation": "నీటి తడి / ఇంధనం", "machinery": "యంత్రాలు", "transport": "రవాణా", "rent": "కౌలు", "other": "ఇతరం"}},
    "hi": {"head": "🌾 सीज़न रिपोर्ट", "acres": "ज़मीन: {a} एकड़", "inc": "आमदनी: ₹{x}", "exp": "खेती की लागत: ₹{x}",
           "net": "शुद्ध {w}: ₹{x}", "profit": "मुनाफ़ा", "loss": "नुकसान", "peracre": "प्रति एकड़ लागत: ₹{x}",
           "cats": "पैसा कहाँ गया:", "crop": "{c}: आमदनी ₹{i}, लागत ₹{e}", "foot": "किसान के अपने रिकॉर्ड से कृषि मित्र ने तैयार की। ऑडिट की हुई रिपोर्ट नहीं।",
           "cat": {"seed": "बीज", "fertilizer": "खाद", "pesticide": "दवा / छिड़काव", "labour": "मज़दूरी",
                   "irrigation": "सिंचाई / ईंधन", "machinery": "मशीन", "transport": "ढुलाई", "rent": "ज़मीन का किराया", "other": "अन्य"}},
}


def _n(x) -> str:
    return f"{int(round(x)):,}"


def report(entries, acres: float | None = None, lang: str = "en") -> dict:
    code = lang if lang in T else "en"
    L = T[code]
    clean = []
    for e in (entries if isinstance(entries, list) else [])[:MAX_ENTRIES]:
        if isinstance(e, dict):
            c = _clean(e, str(e.get("note") or ""), str(e.get("crop") or ""))
            if c:
                c["date"] = str(e.get("date") or "")[:10]
                clean.append(c)
    income = sum(e["amount_rs"] for e in clean if e["type"] == "income")
    expense = sum(e["amount_rs"] for e in clean if e["type"] == "expense")
    cats: dict[str, int] = {}
    crops: dict[str, dict] = {}
    for e in clean:
        if e["type"] == "expense":
            cats[e["category"]] = cats.get(e["category"], 0) + e["amount_rs"]
        if e["crop"]:
            c = crops.setdefault(e["crop"], {"income_rs": 0, "expense_rs": 0})
            c["income_rs" if e["type"] == "income" else "expense_rs"] += e["amount_rs"]
    try:
        a = float(acres) if acres not in (None, "") else None
    except (TypeError, ValueError):
        a = None
    if a is not None and not (0 < a <= 1000):
        a = None
    net = income - expense
    by_cat = [{"category": k, "amount_rs": v, "share_pct": round(v / expense * 100)} for k, v in sorted(cats.items(), key=lambda kv: -kv[1])]
    out = {"entries": len(clean), "income_rs": income, "expense_rs": expense, "net_rs": net,
           "acres": a, "cost_per_acre_rs": round(expense / a) if a else None, "by_category": by_cat,
           "by_crop": [{"crop": k, **v, "net_rs": v["income_rs"] - v["expense_rs"]} for k, v in crops.items()]}
    lines = [L["head"]]
    if a:
        lines.append(L["acres"].format(a=a if a != int(a) else int(a)))
    lines += [L["inc"].format(x=_n(income)), L["exp"].format(x=_n(expense)),
              L["net"].format(w=L["profit"] if net >= 0 else L["loss"], x=_n(abs(net)))]
    if out["cost_per_acre_rs"]:
        lines.append(L["peracre"].format(x=_n(out["cost_per_acre_rs"])))
    if by_cat:
        lines.append(L["cats"])
        lines += [f"• {L['cat'][b['category']]}: ₹{_n(b['amount_rs'])} ({b['share_pct']}%)" for b in by_cat]
    lines += [L["crop"].format(c=c["crop"].capitalize(), i=_n(c["income_rs"]), e=_n(c["expense_rs"])) for c in out["by_crop"]]
    lines.append(L["foot"])
    out["text"] = "\n".join(lines)
    return out
