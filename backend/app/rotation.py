"""Crop rotation simulator: compare what to grow next given the last crops and the soil. Rule-based and explainable: every point
added or taken away comes with its reason. It is NOT a yield or income forecast and the rules are general agronomic guidance that
has not been reviewed by an agronomist (data/rotation.json says so). Pests and diseases shared by two crops are read from the
repository's problems.json, so the carry-over reasons are the same ones the Farm Doctor shows.
"""
import json
from itertools import product
from pathlib import Path

DATA = Path(__file__).parent / "data"
MAX_HISTORY, MAX_STEPS, MAX_SCENARIOS = 3, 3, 12
SAME_CROP, SAME_FAMILY, SHARED_EACH, SHARED_CAP, LEGUME_GAIN, HEAVY_AFTER_LEGUME, HEAVY_AFTER_HEAVY = -3, -1, -1, 3, 2, 1, -1
SOIL_SUIT, SOIL_CAUTION, OFF_SEASON, REPEAT_RECENT = 1, -1, -5, -1

_RULES = json.loads((DATA / "rotation.json").read_text())
CROPS = _RULES["crops"]
_PROBLEMS = json.loads((DATA / "problems.json").read_text())
_ECON = {c["id"]: c for c in json.loads((DATA / "crop_economics.json").read_text())["crops"]}
_ALIAS = {a.lower(): cid for cid, c in CROPS.items() for a in c["aliases"] + [cid]}

T = {
    "en": {"same": "{c} again right after {c}: the same pests and diseases stay in the field.", "fam": "{c} is in the same crop family as {p}.",
           "shared": "{c} and {p} share: {names}.", "legume": "{c} is a legume and can add nitrogen after {p}.", "afterlegume": "{c} can use nitrogen left by the legume {p}.",
           "heavy": "{c} after {p}: both take a lot of nitrogen, plan the nutrients.", "suit": "{c} generally suits {soil} soil.", "caution": "{c} needs care on {soil} soil (drainage or water holding).",
           "season": "{c} is not a usual {season} crop in our crop table.", "recent": "{c} was also grown in the last {n} seasons.", "water": "{c}: water need {w} in our crop table.",
           "none": "No rule applies: neutral.", "basis": "Rule-based comparison from general agronomic guidance (not reviewed by an agronomist) and the repository's pest and disease table. It is not a yield or income forecast. Soil test and local KVK advice come first.",
           "unknown": "Crop not recognised: {c}"},
    "te": {"same": "{c} వెంటనే మళ్ళీ {c}: అవే చీడపీడలు పొలంలో ఉండిపోతాయి.", "fam": "{c}, {p} ఒకే పంట కుటుంబం.", "shared": "{c}, {p} కి ఉమ్మడి సమస్యలు: {names}.",
           "legume": "{c} పప్పుజాతి పంట; {p} తర్వాత నేలలో నత్రజని పెంచగలదు.", "afterlegume": "{c} పప్పుజాతి {p} మిగిల్చిన నత్రజనిని వాడుకోగలదు.", "heavy": "{p} తర్వాత {c}: రెండూ ఎక్కువ నత్రజని తీసుకుంటాయి, పోషకాలు ప్లాన్ చేయండి.",
           "suit": "{c} సాధారణంగా {soil} నేలకు సరిపోతుంది.", "caution": "{c} కి {soil} నేలలో జాగ్రత్త (నీరు ఇంకడం లేదా నిలవడం).", "season": "మా పంట పట్టికలో {c} ఈ {season} సీజన్ పంట కాదు.",
           "recent": "{c} గత {n} సీజన్లలో కూడా వేశారు.", "water": "{c}: నీటి అవసరం {w} (మా పట్టిక ప్రకారం).", "none": "ఏ నియమం వర్తించదు: తటస్థం.",
           "basis": "సాధారణ వ్యవసాయ మార్గదర్శకాలు (వ్యవసాయ నిపుణుడు సమీక్షించలేదు), తెగుళ్ల పట్టిక ఆధారంగా నియమాల పోలిక. ఇది దిగుబడి లేదా ఆదాయ అంచనా కాదు. మట్టి పరీక్ష, స్థానిక KVK సలహా ముందు.",
           "unknown": "పంట గుర్తించలేదు: {c}"},
    "hi": {"same": "{c} के तुरंत बाद फिर {c}: वही कीट और रोग खेत में रह जाते हैं।", "fam": "{c} और {p} एक ही फसल परिवार के हैं।", "shared": "{c} और {p} में साझा समस्याएँ: {names}।",
           "legume": "{c} दलहन है और {p} के बाद मिट्टी में नाइट्रोजन बढ़ा सकती है।", "afterlegume": "{c} दलहन {p} की छोड़ी नाइट्रोजन का उपयोग कर सकती है।", "heavy": "{p} के बाद {c}: दोनों बहुत नाइट्रोजन लेती हैं, पोषक तत्व सोचकर दें।",
           "suit": "{c} आम तौर पर {soil} मिट्टी में ठीक रहती है।", "caution": "{c} के लिए {soil} मिट्टी में सावधानी (जल निकासी या पानी रोकना)।", "season": "हमारी फसल तालिका में {c} इस {season} मौसम की सामान्य फसल नहीं है।",
           "recent": "{c} पिछले {n} मौसमों में भी उगाई गई थी।", "water": "{c}: पानी की ज़रूरत {w} (हमारी तालिका के अनुसार)।", "none": "कोई नियम लागू नहीं: तटस्थ।",
           "basis": "सामान्य कृषि मार्गदर्शन (कृषि विशेषज्ञ ने समीक्षा नहीं की) और रोग तालिका पर आधारित नियम-तुलना। यह उपज या आय का अनुमान नहीं है। मिट्टी जाँच और स्थानीय KVK सलाह पहले।",
           "unknown": "फसल पहचानी नहीं गई: {c}"},
}


def norm(name) -> str | None:
    return _ALIAS.get(str(name or "").strip().lower()[:40])


def crop_name(cid: str, lang: str = "en") -> str:
    return CROPS[cid].get(lang) or CROPS[cid]["name"] if lang in ("te", "hi") else CROPS[cid]["name"]


def shared_problems(a: str, b: str) -> list[str]:
    """Names of pests/diseases that affect both crops (problems.json crop ids: paddy, groundnut, cotton, ...)."""
    return [p["name"] for p in _PROBLEMS if a in p["crops"] and b in p["crops"] and not p["id"].endswith("deficiency")]


def step(prev: list[str], nxt: str, soil: str, season: str, lang: str = "en") -> dict:
    """Score one crop (nxt) after the crops in prev (most recent first). Returns points and the reasons for each point."""
    L = T.get(lang, T["en"])
    c, info = crop_name(nxt, lang), CROPS[nxt]
    pts, why = 0, []

    def add(delta, key, **kw):
        nonlocal pts
        pts += delta
        why.append({"points": delta, "reason": L[key].format(**kw)})

    last = prev[0] if prev else None
    if last:
        p = crop_name(last, lang)
        if last == nxt:
            add(SAME_CROP, "same", c=c)
        elif CROPS[last]["family"] == info["family"]:
            add(SAME_FAMILY, "fam", c=c, p=p)
        sh = shared_problems(last, nxt) if last != nxt else []
        if sh:
            add(max(SHARED_EACH * len(sh), -SHARED_CAP), "shared", c=c, p=p, names=", ".join(sh[:4]))
        if info["n_role"] == "fixes" and CROPS[last]["n_role"] != "fixes":
            add(LEGUME_GAIN, "legume", c=c, p=p)
        elif info["n_role"] == "heavy" and CROPS[last]["n_role"] == "fixes":
            add(HEAVY_AFTER_LEGUME, "afterlegume", c=c, p=p)
        elif info["n_role"] == "heavy" and CROPS[last]["n_role"] == "heavy":
            add(HEAVY_AFTER_HEAVY, "heavy", c=c, p=p)
        recent = sum(1 for x in prev[1:MAX_HISTORY] if x == nxt)
        if recent and last != nxt:
            add(REPEAT_RECENT, "recent", c=c, n=MAX_HISTORY)
    fit = _RULES["soil_fit"].get(nxt, {})
    if soil in fit.get("suits", []):
        add(SOIL_SUIT, "suit", c=c, soil=soil)
    elif soil in fit.get("caution", []):
        add(SOIL_CAUTION, "caution", c=c, soil=soil)
    econ = _ECON.get(nxt)
    if econ and season in ("kharif", "rabi") and season not in econ["seasons"]:
        add(OFF_SEASON, "season", c=c, season=season)
    if not why:
        why.append({"points": 0, "reason": L["none"]})
    out = {"crop": nxt, "name": c, "points": pts, "reasons": why}
    if econ:
        out["water_need"] = econ["water"]
        out["water_note"] = L["water"].format(c=c, w=econ["water"])
    return out


def simulate(payload: dict, lang: str = "en") -> dict:
    lang = lang if lang in T else "en"
    L = T[lang]
    soil = payload.get("soil") if payload.get("soil") in _RULES["soils"] else "other"
    season = str(payload.get("season") or "").lower()[:10]
    unknown, hist = [], []
    for h in (payload.get("history") or [])[:MAX_HISTORY]:
        n = norm(h)
        (hist.append(n) if n else unknown.append(L["unknown"].format(c=str(h)[:30])))
    seqs = []
    for s in (payload.get("scenarios") or [])[:MAX_SCENARIOS]:
        ids = [norm(x) for x in (s if isinstance(s, list) else [s])[:MAX_STEPS]]
        if all(ids) and ids:
            seqs.append(ids)
        else:
            unknown.append(L["unknown"].format(c=", ".join(str(x)[:20] for x in (s if isinstance(s, list) else [s]))))
    if not seqs:
        seqs = [[c] for c in CROPS]
    out = []
    for ids in seqs:
        prev, steps, total = list(hist), [], 0
        for cid in ids:
            r = step(prev, cid, soil, season, lang)
            steps.append(r)
            total += r["points"]
            prev = [cid] + prev
        out.append({"sequence": [crop_name(i, lang) for i in ids], "ids": ids, "total_points": total, "steps": steps})
    out.sort(key=lambda s: (-s["total_points"], s["sequence"]))
    return {"history": [crop_name(h, lang) for h in hist], "soil": soil, "season": season or None, "scenarios": out, "unrecognised": unknown,
            "reviewed_by_agronomist": _RULES["reviewed"], "soil_note": _RULES["soil_note"], "basis": L["basis"]}


def tool_rotation_compare(previous_crop: str, soil: str = "other", season: str = "") -> dict:
    """Agent tool: rank the next crop after previous_crop, with the reasons."""
    r = simulate({"history": [previous_crop], "soil": soil, "season": season})
    if not r["history"]:
        return {"error": "previous crop not recognised", "known_crops": [c["name"] for c in CROPS.values()]}
    return {"previous_crop": r["history"][0], "soil": r["soil"], "ranking": [{"crop": s["sequence"][0], "points": s["total_points"],
            "reasons": [x["reason"] for x in s["steps"][0]["reasons"]]} for s in r["scenarios"]], "basis": r["basis"]}


SPECS = [{"type": "function", "function": {
    "name": "rotation_compare",
    "description": "Compare which crop to grow NEXT after the previous crop, for the soil, with reasons (shared pests and diseases, nitrogen from legumes, soil fit). "
                   "Rule-based, not a yield forecast; say the basis and that it is general guidance. Use for 'what should I grow after X'.",
    "parameters": {"type": "object", "properties": {"previous_crop": {"type": "string"}, "soil": {"type": "string", "description": "sandy, loam, clay, black, red, alluvial or other"},
                                                     "season": {"type": "string", "description": "kharif or rabi, optional"}}, "required": ["previous_crop"]}}}]
FUNCS = {"rotation_compare": tool_rotation_compare}
