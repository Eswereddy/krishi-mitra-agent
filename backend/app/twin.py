"""Farm digital twin: one living record of ONE field (place, area, soil, crop, variety, sowing date, irrigation given, cost,
yield) that is combined with the weather it has actually lived through since sowing and the crop calendar, to produce an
explainable progress report. The twin lives on the farmer's phone; the server only does the arithmetic (stateless).
Each line of the report carries its basis: farmer-entered, computed, live archive, or indicative table. Nothing is guessed.
"""
import asyncio
from datetime import timedelta

from . import coach

SOILS = ("sandy", "loam", "clay", "black", "red", "alluvial", "other")
LAG_DAYS, WET_DAY_MM, DRY_SPELL_WARN = 5, 2.5, 10
MAX_IRRIGATION = 200

T = {
    "en": {"head": "Field report", "field": "Field: {crop}{variety}, {acres} acres, {soil} soil{place}", "stage": "Crop day {d}, stage: {s}, {p}% of expected duration",
           "harvest": "Expected harvest around {h} (about {n} days)", "notsown": "Sowing is {n} days away.", "past": "Past the expected harvest time for this crop.",
           "rain": "Rain since sowing: {r} mm over {w} wet days; average temperature {t} C", "dry": "Longest stretch without rain: {n} days",
           "dryirr": "Longest stretch with neither rain nor irrigation: {n} days", "irr": "Irrigation you logged: {n} times, {mm} mm in total, last {last}",
           "noirr": "No irrigation logged.", "cost": "Spent so far: {e} ({pa} per acre)", "yield": "Yield entered: {y} kg ({ya} kg per acre)",
           "warn_dry": "Watch: a long dry stretch happened while the crop was in a water-critical stage. Check soil moisture in the field.",
           "nohist": "Weather since sowing is not available right now.", "soil_note": {"sandy": "Sandy soil drains fast: water in smaller, more frequent amounts.",
           "clay": "Clay soil holds water: avoid water-logging, water less often.", "black": "Black soil cracks when dry and sticks when wet: avoid working it wet."},
           "basis": "Based on: what you entered, a live weather archive (lags about 5 days) and indicative crop tables. Not a forecast or a diagnosis."},
    "te": {"head": "పొలం నివేదిక", "field": "పొలం: {crop}{variety}, {acres} ఎకరాలు, {soil} నేల{place}", "stage": "పంట రోజు {d}, దశ: {s}, అంచనా కాలంలో {p}%",
           "harvest": "కోత సుమారు {h} (సుమారు {n} రోజులు)", "notsown": "విత్తడానికి {n} రోజులు ఉంది.", "past": "ఈ పంట కోత సమయం దాటింది.",
           "rain": "విత్తిన తర్వాత వర్షం: {r} మి.మీ, {w} వర్షపు రోజులు; సగటు ఉష్ణోగ్రత {t} C", "dry": "వర్షం లేని అత్యధిక కాలం: {n} రోజులు",
           "dryirr": "వర్షం, నీటి తడి రెండూ లేని అత్యధిక కాలం: {n} రోజులు", "irr": "మీరు నమోదు చేసిన తడులు: {n} సార్లు, మొత్తం {mm} మి.మీ, చివరిది {last}",
           "noirr": "తడులు నమోదు కాలేదు.", "cost": "ఇప్పటివరకు ఖర్చు: {e} (ఎకరాకు {pa})", "yield": "నమోదు చేసిన దిగుబడి: {y} కిలో (ఎకరాకు {ya} కిలో)",
           "warn_dry": "గమనిక: నీరు కీలకమైన దశలో ఎక్కువ రోజులు పొడిగా ఉంది. పొలంలో తేమ చూడండి.", "nohist": "విత్తిన తర్వాత వాతావరణం ఇప్పుడు అందుబాటులో లేదు.",
           "soil_note": {"sandy": "ఇసుక నేల నీరు త్వరగా ఇంకుతుంది: తక్కువ మోతాదులో, తరచుగా తడి పెట్టండి.", "clay": "బంక నేల నీరు పట్టుకుంటుంది: నీరు నిలవకుండా చూడండి, తడులు తక్కువ.",
                         "black": "నల్ల నేల ఎండితే పగులుతుంది, తడిస్తే అంటుకుంటుంది: తడిగా ఉన్నప్పుడు దున్నకండి."},
           "basis": "ఆధారం: మీరు నమోదు చేసినవి, ప్రత్యక్ష వాతావరణ ఆర్కైవ్ (సుమారు 5 రోజులు ఆలస్యం), సూచనాత్మక పంట పట్టికలు. ఇది అంచనా లేదా నిర్ధారణ కాదు."},
    "hi": {"head": "खेत रिपोर्ट", "field": "खेत: {crop}{variety}, {acres} एकड़, {soil} मिट्टी{place}", "stage": "फसल का दिन {d}, चरण: {s}, अनुमानित अवधि का {p}%",
           "harvest": "कटाई लगभग {h} (करीब {n} दिन)", "notsown": "बुवाई में {n} दिन हैं।", "past": "इस फसल की अनुमानित कटाई का समय निकल चुका है।",
           "rain": "बुवाई के बाद बारिश: {r} मिमी, {w} बरसात के दिन; औसत तापमान {t} C", "dry": "बिना बारिश का सबसे लंबा दौर: {n} दिन",
           "dryirr": "बारिश और सिंचाई दोनों के बिना सबसे लंबा दौर: {n} दिन", "irr": "आपकी दर्ज सिंचाई: {n} बार, कुल {mm} मिमी, आख़िरी {last}",
           "noirr": "कोई सिंचाई दर्ज नहीं।", "cost": "अब तक खर्च: {e} (प्रति एकड़ {pa})", "yield": "दर्ज उपज: {y} किलो (प्रति एकड़ {ya} किलो)",
           "warn_dry": "ध्यान दें: पानी के लिए अहम चरण में लंबा सूखा दौर रहा। खेत की नमी जाँचें।", "nohist": "बुवाई के बाद का मौसम अभी उपलब्ध नहीं।",
           "soil_note": {"sandy": "रेतीली मिट्टी पानी जल्दी सोखती है: कम मात्रा में, बार-बार सिंचाई करें।", "clay": "चिकनी मिट्टी पानी रोकती है: जलभराव से बचें, सिंचाई कम बार।",
                         "black": "काली मिट्टी सूखने पर फटती और गीली होने पर चिपकती है: गीली में जुताई न करें।"},
           "basis": "आधार: आपके दर्ज आँकड़े, लाइव मौसम आर्काइव (लगभग 5 दिन देरी) और सांकेतिक फसल तालिकाएँ। यह पूर्वानुमान या निदान नहीं।"},
}


def _num(v, lo=0.0, hi=1e9):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if lo < x <= hi else None


def _history(place: str, country: str, start, end) -> dict:
    from . import climate, tools
    return tools._cached("twinwx", (place.lower(), country, start.isoformat(), end.isoformat()),
                         lambda: climate._fetch(place, country, start, end), ok=lambda v: "error" not in v)


def _spells(days: list[tuple], irrig: set) -> tuple[int, int]:
    best_rain = best_both = cur_rain = cur_both = 0
    for d, mm in days:
        wet = mm is not None and mm >= WET_DAY_MM
        cur_rain = 0 if wet else cur_rain + 1
        cur_both = 0 if wet or d in irrig else cur_both + 1
        best_rain, best_both = max(best_rain, cur_rain), max(best_both, cur_both)
    return best_rain, best_both


async def report(twin: dict, lang: str = "en") -> dict:
    twin = twin if isinstance(twin, dict) else {}
    lang = lang if lang in T else "en"
    L = T[lang]
    crop, place = str(twin.get("crop") or "").strip()[:40], str(twin.get("place") or "").strip()[:60]
    country = str(twin.get("country") or "").upper()[:3]
    acres = _num(twin.get("acres"), 0, 1000)
    soil = twin.get("soil") if twin.get("soil") in SOILS else "other"
    variety = str(twin.get("variety") or "").strip()[:40]
    if not crop or not acres:
        return {"error": "crop and a sensible area in acres are needed"}
    lines, facts = [], []

    def add(code, text, basis):
        lines.append(text)
        facts.append({"code": code, "text": text, "basis": basis})

    add("field", L["field"].format(crop=crop, variety=f" ({variety})" if variety else "", acres=acres, soil=soil, place=f", {place}" if place else ""), "farmer-entered")
    sown = coach._parse(twin.get("sowing_date")) if twin.get("sowing_date") else None
    guide, critical_stage = None, False
    out = {"crop": crop, "acres": acres, "soil": soil}
    if sown:
        guide = await asyncio.to_thread(coach.crop_guide, crop, sown.isoformat(), "", country)
        if guide.get("status") == "growing":
            critical_stage = bool(guide.get("water_critical"))
            add("stage", L["stage"].format(d=guide["day_of_crop"], s=coach.stage_label(guide["stage"], lang), p=guide["progress_pct"]), "computed from the sowing date + indicative crop table")
            harvest = sown + timedelta(days=guide["expected_duration_days"])
            out["expected_harvest"] = harvest.isoformat()
            add("harvest", L["harvest"].format(h=harvest.isoformat(), n=guide["days_to_expected_harvest"]), "indicative crop duration; varieties and seasons shift it by weeks")
        elif guide.get("status") == "not_sown":
            add("stage", L["notsown"].format(n=guide["days_until_sowing"]), "computed")
        elif guide.get("status") == "past_expected_harvest":
            add("stage", L["past"], "computed from the sowing date + indicative crop table")
        out["stage"] = {k: guide.get(k) for k in ("status", "day_of_crop", "stage", "progress_pct") if k in guide}
    irr = []
    for e in (twin.get("irrigation") if isinstance(twin.get("irrigation"), list) else [])[:MAX_IRRIGATION]:
        d = coach._parse(e.get("date")) if isinstance(e, dict) else None
        mm = _num(e.get("mm"), 0, 500) if isinstance(e, dict) else None
        if d and mm and (not sown or d >= sown):
            irr.append((d, mm))
    if irr:
        add("irrigation", L["irr"].format(n=len(irr), mm=round(sum(m for _, m in irr), 1), last=max(d for d, _ in irr).isoformat()), "farmer-entered")
    elif sown:
        add("irrigation", L["noirr"], "farmer-entered")
    out["irrigation"] = {"count": len(irr), "total_mm": round(sum(m for _, m in irr), 1)}
    today = coach._today()
    end = today - timedelta(days=LAG_DAYS)
    if sown and place and end > sown:
        h = await asyncio.to_thread(_history, place, country, sown, end)
        d = (h.get("daily") or {}) if "error" not in h else {}
        days = [(t, p) for t, p in zip(d.get("time") or [], d.get("precipitation_sum") or [])]
        temps = [x for x in d.get("temperature_2m_mean") or [] if x is not None]
        if days:
            wet = sum(1 for _, p in days if p is not None and p >= WET_DAY_MM)
            rain = round(sum(p for _, p in days if p), 1)
            t = round(sum(temps) / len(temps), 1) if temps else "-"
            add("weather", L["rain"].format(r=rain, w=wet, t=t), f"live open-meteo archive {sown.isoformat()} to {end.isoformat()}")
            sp_rain, sp_both = _spells(days, {x.isoformat() for x, _ in irr})
            add("dry_spell", L["dry"].format(n=sp_rain) if not irr else L["dryirr"].format(n=sp_both), "computed from the archive and your irrigation log")
            out["weather_since_sowing"] = {"rain_mm": rain, "wet_days": wet, "mean_temp_c": t if temps else None, "longest_dry_spell_days": sp_rain,
                                           "longest_unwatered_days": sp_both, "to": end.isoformat()}
            if critical_stage and sp_both >= DRY_SPELL_WARN:
                add("warning", L["warn_dry"], "computed: dry stretch >= 10 days and crop is in a water-critical stage")
        else:
            add("weather", L["nohist"], "unavailable")
    exp, yld = _num(twin.get("expenses")), _num(twin.get("yield_kg"))
    if exp:
        add("cost", L["cost"].format(e=round(exp), pa=round(exp / acres)), "farmer-entered; per acre computed")
        out["cost_per_acre"] = round(exp / acres)
    if yld:
        add("yield", L["yield"].format(y=round(yld), ya=round(yld / acres)), "farmer-entered; per acre computed")
        out["yield_per_acre_kg"] = round(yld / acres)
    if soil in L["soil_note"]:
        add("soil", L["soil_note"][soil], "indicative general guidance for this soil type")
    out.update(facts=facts, text="\n".join([L["head"], *lines, L["basis"]]), note=L["basis"])
    return out
