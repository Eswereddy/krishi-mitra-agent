"""Village early warning: crop-specific heat / cold / heavy-rain / wind alerts and fungal-disease WEATHER conditions for the
next days, from the live Open-Meteo forecast for the farmer's place. Thresholds are indicative per crop and tighter in sensitive
growth stages (flowering, grain filling), and rain thresholds drop near harvest. Every alert carries its value, threshold and
preventive actions (non-chemical). Disease alerts only say the weather favours fungal disease: no disease is predicted and
nothing is sprayed without advice. Computed in code, never by a model.
"""
import asyncio
import json

from . import coach

DATA = coach.DATA
SEVERE = {"heat": 3.0, "cold": 3.0, "rain": 1.5, "wind": 10.0}      # margin beyond the threshold for 'warning'
SENSITIVE_HEAT_DROP = 2.0

T = {
    "en": {"heat": "Heat: up to {v} C on {d} (this crop is stressed above {t} C{s})", "cold": "Cold: night down to {v} C on {d} (this crop is harmed below {t} C)",
           "rain": "Heavy rain: {v} mm on {d} (above {t} mm is a risk for this crop{s})", "wind": "Strong wind: up to {v} km/h on {d} (above {t} km/h can damage this crop)",
           "disease": "Disease weather: {n} humid and warm hours on {d}, conditions favour fungal disease (not a diagnosis)", "stage": ", and it is {st} now",
           "clear": "No crop-specific warning for the next days.", "sev": {"warning": "WARNING", "watch": "WATCH"},
           "note": "Indicative crop thresholds on a live forecast for the whole place; your field can differ. A signal to inspect and prepare, not a damage prediction. Never spray without advice on the product and dose."},
    "te": {"heat": "వేడి: {d} న {v} C వరకు (ఈ పంట {t} C పైన ఒత్తిడికి గురవుతుంది{s})", "cold": "చలి: {d} రాత్రి {v} C వరకు (ఈ పంటకు {t} C కంటే తక్కువ హానికరం)",
           "rain": "భారీ వర్షం: {d} న {v} మి.మీ ({t} మి.మీ పైన ఈ పంటకు ప్రమాదం{s})", "wind": "బలమైన గాలి: {d} న {v} కి.మీ/గం వరకు ({t} పైన ఈ పంటకు నష్టం కలగవచ్చు)",
           "disease": "తెగులు వాతావరణం: {d} న {n} తేమ, వెచ్చని గంటలు, శిలీంధ్ర తెగులుకు అనుకూలం (నిర్ధారణ కాదు)", "stage": ", ఇప్పుడు {st} దశ",
           "clear": "రాబోయే రోజులకు ఈ పంటకు ప్రత్యేక హెచ్చరిక లేదు.", "sev": {"warning": "హెచ్చరిక", "watch": "గమనించండి"},
           "note": "ప్రాంతం మొత్తానికి ప్రత్యక్ష వాతావరణ అంచనాపై సూచనాత్మక పంట పరిమితులు; మీ పొలం భిన్నంగా ఉండవచ్చు. ఇది పరిశీలించి సిద్ధం కావడానికి సంకేతం, నష్టం అంచనా కాదు. సలహా లేకుండా మందు పిచికారీ చేయవద్దు."},
    "hi": {"heat": "गर्मी: {d} को {v} C तक (यह फसल {t} C से ऊपर तनाव में आती है{s})", "cold": "ठंड: {d} की रात {v} C तक (इस फसल को {t} C से नीचे नुकसान)",
           "rain": "भारी बारिश: {d} को {v} मिमी ({t} मिमी से ऊपर इस फसल को जोखिम{s})", "wind": "तेज़ हवा: {d} को {v} किमी/घं तक ({t} से ऊपर इस फसल को नुकसान हो सकता है)",
           "disease": "रोग का मौसम: {d} को {n} नम और गर्म घंटे, फफूँद रोग के अनुकूल (निदान नहीं)", "stage": ", अभी {st} चरण है",
           "clear": "अगले दिनों के लिए इस फसल की कोई विशेष चेतावनी नहीं।", "sev": {"warning": "चेतावनी", "watch": "ध्यान दें"},
           "note": "पूरे इलाके के लाइव पूर्वानुमान पर सांकेतिक फसल सीमाएँ; आपका खेत अलग हो सकता है। यह जाँचने और तैयारी का संकेत है, नुकसान का अनुमान नहीं। सलाह के बिना दवा न छिड़कें।"},
}

A = {  # preventive, non-chemical actions
    "heat": ["irrigate_evening", "mulch", "avoid_midday_work"], "cold": ["cover_young", "no_late_irrigation"],
    "rain": ["clear_drains", "delay_spray_fertiliser", "protect_harvest"], "wind": ["support_tall", "delay_spray"],
    "disease": ["scout_leaves", "avoid_overhead_irrigation_evening", "improve_airflow", "ask_officer_if_spots"],
}
AT = {
    "irrigate_evening": {"en": "Water early morning or evening, not at midday.", "te": "ఉదయం లేదా సాయంత్రం నీరు పెట్టండి, మధ్యాహ్నం కాదు.", "hi": "सुबह या शाम को सिंचाई करें, दोपहर में नहीं।"},
    "mulch": {"en": "Mulch the soil to keep moisture.", "te": "తేమ నిలవడానికి మల్చింగ్ చేయండి.", "hi": "नमी बचाने के लिए मल्चिंग करें।"},
    "avoid_midday_work": {"en": "Protect workers and animals: avoid midday work.", "te": "కూలీలను, పశువులను కాపాడండి: మధ్యాహ్నం పని వద్దు.", "hi": "मज़दूरों और पशुओं को बचाएँ: दोपहर में काम न करें।"},
    "cover_young": {"en": "Cover young plants at night.", "te": "రాత్రి లేత మొక్కలను కప్పండి.", "hi": "रात में छोटे पौधों को ढकें।"},
    "no_late_irrigation": {"en": "Avoid irrigating late in the evening.", "te": "సాయంత్రం ఆలస్యంగా నీరు పెట్టవద్దు.", "hi": "शाम को देर से सिंचाई न करें।"},
    "clear_drains": {"en": "Clear field drains so water does not stand.", "te": "నీరు నిలవకుండా కాలువలు శుభ్రం చేయండి.", "hi": "पानी न रुके, इसलिए नालियाँ साफ़ करें।"},
    "delay_spray_fertiliser": {"en": "Do not spray or fertilise before the rain.", "te": "వర్షానికి ముందు పిచికారీ, ఎరువులు వద్దు.", "hi": "बारिश से पहले छिड़काव या खाद न दें।"},
    "protect_harvest": {"en": "Cover or move harvested produce under shelter.", "te": "కోసిన పంటను కప్పండి లేదా నీడలోకి మార్చండి.", "hi": "कटी उपज को ढकें या छत के नीचे रखें।"},
    "support_tall": {"en": "Support tall crops and staked plants.", "te": "ఎత్తైన పంటలకు, కట్టిన మొక్కలకు ఆసరా ఇవ్వండి.", "hi": "ऊँची और सहारे वाली फसलों को सहारा दें।"},
    "delay_spray": {"en": "Do not spray in strong wind.", "te": "బలమైన గాలిలో పిచికారీ వద్దు.", "hi": "तेज़ हवा में छिड़काव न करें।"},
    "scout_leaves": {"en": "Walk the field and check leaves, especially the underside.", "te": "పొలం తిరిగి ఆకులను, ముఖ్యంగా క్రింది వైపు చూడండి.", "hi": "खेत में घूमकर पत्तियों को, खासकर नीचे की ओर, देखें।"},
    "avoid_overhead_irrigation_evening": {"en": "Avoid sprinkler or overhead watering in the evening.", "te": "సాయంత్రం పైనుండి నీరు చల్లడం వద్దు.", "hi": "शाम को ऊपर से पानी न दें।"},
    "improve_airflow": {"en": "Remove weeds and crowded growth to improve air flow.", "te": "కలుపు తీసి గాలి ఆడేలా చూడండి.", "hi": "खरपतवार हटाकर हवा का संचार बढ़ाएँ।"},
    "ask_officer_if_spots": {"en": "If you see spots or mould, send a photo to the agriculture officer.", "te": "మచ్చలు, బూజు కనిపిస్తే ఫోటో వ్యవసాయ అధికారికి పంపండి.", "hi": "धब्बे या फफूँद दिखें तो कृषि अधिकारी को फ़ोटो भेजें।"},
    "harvest_early": {"en": "If the crop is mature, consider harvesting early.", "te": "పంట పక్వానికి వస్తే ముందే కోయడం ఆలోచించండి.", "hi": "फसल पकी हो तो जल्दी कटाई पर विचार करें।"},
    "no_spray_without_advice": {"en": "Do not spray any chemical without advice on the product and dose.", "te": "ఉత్పత్తి, మోతాదుపై సలహా లేకుండా ఏ మందూ పిచికారీ చేయవద్దు.", "hi": "उत्पाद और मात्रा की सलाह के बिना कोई दवा न छिड़कें।"},
}


def _th(crop_id):
    tb = json.loads((DATA / "crop_thresholds.json").read_text())
    d = tb["default"]
    return {k: (tb[k].get(crop_id, d[k]) if crop_id else d[k]) for k in d}, tb


def _act(kind, lang, extra=()):
    codes = [*A[kind], *extra, "no_spray_without_advice"]
    return [{"code": c, "text": AT[c].get(lang) or AT[c]["en"]} for c in codes]


async def check(crop: str, place: str, country: str = "", sowing_date: str = "", lang: str = "en") -> dict:
    from . import agro, pestwatch, tools
    lang = lang if lang in T else "en"
    L = T[lang]
    place, crop = str(place or "").strip()[:60], str(crop or "").strip()[:40]
    if not place:
        return {"error": "place is needed"}
    c = agro._crop(crop) if crop else None
    cid = c["id"] if c else None
    th, tb = _th(cid)
    wx = await asyncio.to_thread(tools.get_weather, place, 7)
    if "error" in wx:
        return wx
    stage = None
    if cid and sowing_date:
        g = await asyncio.to_thread(coach.crop_guide, cid, str(sowing_date), "", country)
        if g.get("status") == "growing":
            stage = g["stage"]
    sensitive = stage in tb["sensitive_stages"]
    mature = stage == "maturity"
    heat_t = th["heat_c"] - (SENSITIVE_HEAT_DROP if sensitive else 0)
    rain_t = min(th["rain_mm"], tb["harvest_rain_mm"]) if mature else th["rain_mm"]
    sfx = L["stage"].format(st=coach.stage_label(stage, lang)) if (sensitive or mature) and stage else ""
    alerts = []

    def add(kind, day, v, t, sev, extra=()):
        text = L[kind].format(v=round(v), d=day["date"], t=round(t), s=sfx if kind in ("heat", "rain") else "")
        alerts.append({"type": kind, "severity": sev, "date": day["date"], "value": round(v, 1), "threshold": round(t, 1), "crop_specific": bool(cid),
                       "key": f"{kind}|{day['date']}|{sev}", "text": text, "actions": _act(kind, lang, extra)})

    for d in wx["forecast"]:
        if d.get("max_c") is not None and d["max_c"] >= heat_t:
            add("heat", d, d["max_c"], heat_t, "warning" if d["max_c"] >= heat_t + SEVERE["heat"] else "watch")
        if d.get("min_c") is not None and d["min_c"] <= th["cold_c"]:
            add("cold", d, d["min_c"], th["cold_c"], "warning" if d["min_c"] <= th["cold_c"] - SEVERE["cold"] else "watch")
        if d.get("rain_mm") is not None and d["rain_mm"] >= rain_t:
            add("rain", d, d["rain_mm"], rain_t, "warning" if d["rain_mm"] >= rain_t * SEVERE["rain"] else "watch", ("harvest_early",) if mature else ())
        if d.get("wind_kmh") is not None and d["wind_kmh"] >= th["wind_kmh"]:
            add("wind", d, d["wind_kmh"], th["wind_kmh"], "warning" if d["wind_kmh"] >= th["wind_kmh"] + SEVERE["wind"] else "watch")
    dr = await asyncio.to_thread(pestwatch.disease_risk, cid or crop or "crop", place, country)
    if "error" not in dr and dr.get("needs_attention"):
        worst = next(x for x in dr["days"] if x["date"] == dr["worst_day"])
        alerts.append({"type": "disease", "severity": "warning" if dr["worst_risk"] == "high" else "watch", "date": dr["worst_day"], "value": worst["wet_hours"], "threshold": None,
                       "crop_specific": False, "key": f"disease|{dr['worst_day']}|{dr['worst_risk']}", "actions": _act("disease", lang),
                       "text": L["disease"].format(n=worst["wet_hours"], d=dr["worst_day"])})
    for a in alerts:
        a["label"] = L["sev"][a["severity"]]
    alerts.sort(key=lambda a: (a["severity"] != "warning", a["date"]))
    return {"source": "open-meteo.com forecast (live)", "place": wx["place"], "crop": cid or crop or None, "stage": stage, "alerts": alerts,
            "warnings": sum(a["severity"] == "warning" for a in alerts), "all_clear": not alerts, "clear_text": L["clear"] if not alerts else None,
            "thresholds": {**{"heat_c": heat_t, "cold_c": th["cold_c"], "rain_mm": rain_t, "wind_kmh": th["wind_kmh"]}, "indicative": True,
                           "crop_specific": bool(cid)}, "note": L["note"]}
