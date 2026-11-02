"""Explainable decisions: WHY the assistant said what it said, built in plain code from what actually happened, never written by the model.

For one answer it reports: (1) the evidence behind it, one entry per tool call, with the data source, its date and a plain label (live,
sample, indicative, computed); (2) a figure trace: each number in the answer matched to the tool result field it came from, or marked
as not found; (3) the checks that ran (the verification layer is re-run here on the answer and the tool results, not trusted from the
browser); (4) the inputs used, and what would change the advice. Nothing is invented: a field that a tool did not return is not shown.
"""
import re

from . import verify

MAX_STEPS, MAX_TRACE, MAX_VALUE_LEN = 12, 14, 80
TOOL_NAME = {
    "en": {"get_mandi_price": "Mandi price", "get_market_price": "Market price", "best_markets": "Best markets", "get_price_trend": "Price trend", "hold_or_sell": "Sell or hold",
           "get_msp": "Government support price", "net_market_value": "Take-home value", "sell_plan": "Sell plan", "get_weather": "Weather forecast", "spray_window": "Spray days",
           "irrigation_advice": "Irrigation advice", "water_plan": "Water plan", "season_check": "Season vs normal", "disease_risk": "Disease weather risk", "check_schemes": "Government schemes",
           "kcc_interest": "Kisan Credit Card interest", "loan_compare": "Loan comparison", "calculate_revenue": "Income calculation", "breakeven_price": "Break-even price",
           "lookup_problem": "Crop problem lookup", "crop_guide": "Crop stage guide", "planting_window": "Planting window", "storage_check": "Storage check", "compare_crops": "Crop comparison",
           "livestock_heat": "Livestock heat stress", "get_expert_help": "Expert help contacts", "rotation_compare": "Crop rotation comparison", "crop_knowledge": "Knowledge graph",
           "price_seasonality": "Price seasonality", "compare_inputs": "Input comparison"},
    "te": {"get_mandi_price": "మండి ధర", "get_market_price": "మార్కెట్ ధర", "best_markets": "ఉత్తమ మార్కెట్లు", "get_price_trend": "ధర ధోరణి", "hold_or_sell": "అమ్మాలా ఆపాలా",
           "get_msp": "ప్రభుత్వ మద్దతు ధర", "get_weather": "వాతావరణ అంచనా", "spray_window": "పిచికారీ రోజులు", "irrigation_advice": "నీటి తడి సలహా", "water_plan": "నీటి ప్రణాళిక",
           "check_schemes": "ప్రభుత్వ పథకాలు", "kcc_interest": "కిసాన్ క్రెడిట్ కార్డ్ వడ్డీ", "calculate_revenue": "ఆదాయ లెక్క", "lookup_problem": "పంట సమస్య శోధన", "crop_guide": "పంట దశ గైడ్",
           "get_expert_help": "నిపుణుల సంప్రదింపులు", "rotation_compare": "పంట మార్పిడి పోలిక", "crop_knowledge": "జ్ఞాన గ్రాఫ్"},
    "hi": {"get_mandi_price": "मंडी भाव", "get_market_price": "बाज़ार भाव", "best_markets": "सबसे अच्छी मंडियाँ", "get_price_trend": "भाव का रुझान", "hold_or_sell": "बेचें या रोकें",
           "get_msp": "सरकारी समर्थन मूल्य", "get_weather": "मौसम पूर्वानुमान", "spray_window": "छिड़काव के दिन", "irrigation_advice": "सिंचाई सलाह", "water_plan": "पानी की योजना",
           "check_schemes": "सरकारी योजनाएँ", "kcc_interest": "किसान क्रेडिट कार्ड ब्याज", "calculate_revenue": "आय की गणना", "lookup_problem": "फसल समस्या खोज", "crop_guide": "फसल चरण गाइड",
           "get_expert_help": "विशेषज्ञ संपर्क", "rotation_compare": "फसल चक्र तुलना", "crop_knowledge": "ज्ञान ग्राफ़"},
}
CHANGE = {  # what would change the advice, per tool (generic and true by construction)
    "en": {"get_weather": "A new forecast. Weather advice can change within a day.", "spray_window": "A new forecast (rain chance, wind).", "irrigation_advice": "Rain that actually falls, and soil moisture in your field.",
           "get_mandi_price": "Prices move daily; another mandi may pay differently.", "hold_or_sell": "The next days' prices and your storage cost.", "check_schemes": "Scheme rules and your documents: confirm at the official office.",
           "get_msp": "A new MSP announcement.", "calculate_revenue": "Your actual price, quantity and costs."},
    "te": {"get_weather": "కొత్త వాతావరణ అంచనా. ఒక్క రోజులోనే మారవచ్చు.", "spray_window": "కొత్త అంచనా (వర్షం, గాలి).", "irrigation_advice": "నిజంగా కురిసిన వర్షం, మీ పొలంలో తేమ.",
           "get_mandi_price": "ధరలు రోజూ మారతాయి; వేరే మండిలో వేరుగా ఉండవచ్చు.", "hold_or_sell": "తర్వాతి రోజుల ధరలు, మీ నిల్వ ఖర్చు.", "check_schemes": "పథక నియమాలు, మీ పత్రాలు: అధికారిక కార్యాలయంలో నిర్ధారించుకోండి.",
           "get_msp": "కొత్త మద్దతు ధర ప్రకటన.", "calculate_revenue": "మీ నిజమైన ధర, పరిమాణం, ఖర్చులు."},
    "hi": {"get_weather": "नया पूर्वानुमान। मौसम की सलाह एक दिन में बदल सकती है।", "spray_window": "नया पूर्वानुमान (बारिश, हवा)।", "irrigation_advice": "असल में हुई बारिश और खेत की नमी।",
           "get_mandi_price": "भाव रोज़ बदलते हैं; दूसरी मंडी में अलग हो सकता है।", "hold_or_sell": "अगले दिनों के भाव और आपका भंडारण खर्च।", "check_schemes": "योजना के नियम और आपके दस्तावेज़: सरकारी दफ़्तर में पुष्टि करें।",
           "get_msp": "नई MSP घोषणा।", "calculate_revenue": "आपका असली भाव, मात्रा और खर्च।"},
}
UI = {
    "en": {"live": "live data", "sample": "SAMPLE data (not live)", "indicative": "indicative table", "computed": "computed from your numbers", "unlabelled": "source not labelled by the tool",
           "default_change": "New data, or a different place or crop.", "no_steps": "This answer did not use any tool, so there is no data behind it to show: treat it as general guidance.",
           "failed": "This tool could not return data", "found": "found in {tool}", "notfound": "not found in any tool result"},
    "te": {"live": "ప్రత్యక్ష డేటా", "sample": "నమూనా డేటా (ప్రత్యక్షం కాదు)", "indicative": "సూచనాత్మక పట్టిక", "computed": "మీ సంఖ్యల నుండి లెక్కించినది", "unlabelled": "టూల్ మూలం చెప్పలేదు",
           "default_change": "కొత్త డేటా, లేదా వేరే ప్రదేశం/పంట.", "no_steps": "ఈ జవాబు ఏ టూల్ వాడలేదు, కాబట్టి చూపడానికి డేటా లేదు: సాధారణ సలహాగా చూడండి.",
           "failed": "ఈ టూల్ డేటా ఇవ్వలేకపోయింది", "found": "{tool} లో దొరికింది", "notfound": "ఏ టూల్ ఫలితంలోనూ దొరకలేదు"},
    "hi": {"live": "लाइव डेटा", "sample": "नमूना डेटा (लाइव नहीं)", "indicative": "सांकेतिक तालिका", "computed": "आपकी संख्याओं से गणना", "unlabelled": "टूल ने स्रोत नहीं बताया",
           "default_change": "नया डेटा, या अलग जगह या फसल।", "no_steps": "इस जवाब में कोई टूल नहीं चला, इसलिए दिखाने के लिए डेटा नहीं है: इसे सामान्य सलाह मानें।",
           "failed": "यह टूल डेटा नहीं दे सका", "found": "{tool} में मिला", "notfound": "किसी टूल परिणाम में नहीं मिला"},
}
COMPUTED = {"calculate_revenue", "kcc_interest", "breakeven_price", "loan_compare", "net_market_value", "compare_inputs", "water_plan", "rotation_compare"}


def classify(tool: str, result: dict) -> str:
    text = " ".join(str(result.get(k, "")) for k in ("source", "note", "basis", "disclaimer", "live_note")).lower()
    if "sample" in text and ("sample-data" in text or "sample data" in text):
        return "sample"
    if tool in COMPUTED:
        return "computed"
    if any(w in text for w in ("open-meteo", "live", "data.gov", "agmarknet", "wfp", "forecast")) and "not set" not in text:
        return "live"
    if any(w in text for w in ("indicative", "table", "ccea", "announcement", "guidance")):
        return "indicative"
    return "unlabelled"


def _walk(obj, path, out):
    if isinstance(obj, dict):
        for k, v in obj.items():
            _walk(v, f"{path}.{k}" if path else str(k), out)
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:40]):
            _walk(v, f"{path}[{i}]", out)
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        out.append((path, float(obj)))


def trace_figures(answer: str, steps: list[dict]) -> list[dict]:
    """Match every number in the answer to a numeric field in some tool result (tolerance 0.5). Unmatched numbers are listed too."""
    pool = []
    for s in steps[:MAX_STEPS]:
        if isinstance(s.get("result"), dict) and "error" not in s["result"]:
            vals = []
            _walk(s["result"], "", vals)
            pool += [(s.get("tool", "?"), p, v) for p, v in vals]
    out, seen = [], set()
    for x in verify._floats(answer or ""):
        key = round(x, 2)
        if key in seen or (abs(x) < 10 and x == int(x)):          # 1-9 are usually counts ("3 days"), too ambiguous to trace
            continue
        seen.add(key)
        hit = next(((t, p) for t, p, v in pool if abs(v - x) <= 0.5), None)
        out.append({"figure": x if x != int(x) else int(x), "tool": hit[0] if hit else None, "field": hit[1] if hit else None})
        if len(out) >= MAX_TRACE:
            break
    return out


def build(answer: str, steps: list, lang: str = "en") -> dict:
    lang = lang if lang in UI else "en"
    U, names, change = UI[lang], TOOL_NAME.get(lang, TOOL_NAME["en"]), CHANGE.get(lang, CHANGE["en"])
    steps = [s for s in (steps or []) if isinstance(s, dict)][:MAX_STEPS]
    evidence, changes = [], []
    for s in steps:
        tool, res = str(s.get("tool", "?"))[:40], s.get("result") if isinstance(s.get("result"), dict) else {}
        title = names.get(tool) or TOOL_NAME["en"].get(tool) or tool.replace("_", " ").capitalize()
        if "error" in res or not res:
            evidence.append({"tool": tool, "title": title, "kind": "failed", "label": U["failed"], "source": None, "as_of": None, "inputs": {}})
            continue
        kind = classify(tool, res)
        args = s.get("args") if isinstance(s.get("args"), dict) else {}
        evidence.append({"tool": tool, "title": title, "kind": kind, "label": U[kind], "source": str(res.get("source") or "")[:140] or None,
                         "as_of": str(res.get("checked_on") or res.get("as_of") or res.get("date") or "")[:20] or None,
                         "note": str(res.get("note") or res.get("disclaimer") or res.get("basis") or "")[:220] or None,
                         "inputs": {str(k)[:24]: str(v)[:MAX_VALUE_LEN] for k, v in list(args.items())[:6]}})
        c = change.get(tool, U["default_change"])
        if c not in changes:
            changes.append(c)
    v = verify.verify_answer(answer or "", steps)
    trace = trace_figures(answer or "", steps)
    for t in trace:
        t["label"] = U["found"].format(tool=names.get(t["tool"]) or t["tool"]) if t["tool"] else U["notfound"]
    return {"evidence": evidence, "figure_trace": trace, "checks": {"figures_checked": v.get("checked", 0), "passed": v["passed"], "unverified": v["unverified"][:8]},
            "could_change": changes[:6], "no_tool_note": None if evidence else U["no_steps"], "computed_in_code": True}
