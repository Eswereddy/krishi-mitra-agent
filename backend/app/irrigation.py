"""Irrigation economics: what the water and the pumping actually cost, and how much was saved against the farmer's OWN usual
practice. Volumes use 1 mm over 1 acre = 4,046.86 litres. Energy comes from hours x pump power (electric kW or diesel litres
per hour) or, if hours are missing, from volume / pump flow. Savings exist only when the farmer enters a baseline ("I usually
give N mm per week"); without one the report says so rather than inventing a saving. This week's recommended water (FAO-56
forecast, indicative) is priced at the farmer's own cost per mm. Pure arithmetic on entered numbers; the server stores nothing.
"""
import asyncio
from datetime import date

from . import coach

L_PER_MM_ACRE = 4046.86
MAX_ENTRIES = 200

T = {
    "en": {"head": "Irrigation cost report", "use": "Water applied: {mm} mm over {n} irrigations = {m3} m3 ({l} litres)", "cost": "Pumping cost: {c} {cur} ({cpm} per mm, {cpa} per acre)",
           "nocost": "Pumping cost not calculated: enter pump power or diesel use, the price, and hours or pump flow.", "save": "Against your usual {b} mm per week over {w} weeks: {s} mm {dir} = {m3} m3 and about {sc} {cur}",
           "saved": "saved", "extra": "MORE used", "nobase": "Enter your usual mm per week to see savings.", "rec": "This week the crop needs about {n} mm after rain ({m3} m3){cost}; irrigate by {d}.",
           "rec0": "This week rain covers the crop's need: no irrigation needed by this estimate.", "cost_rec": ", about {c} {cur} at your cost per mm",
           "basis": "Volumes and costs are computed from the numbers you entered. The recommendation is an indicative FAO-56 estimate from a live forecast: check the soil by hand before irrigating."},
    "te": {"head": "నీటి తడి ఖర్చు నివేదిక", "use": "ఇచ్చిన నీరు: {n} తడులకు {mm} మి.మీ = {m3} ఘ.మీ ({l} లీటర్లు)", "cost": "పంపింగ్ ఖర్చు: {c} {cur} (మి.మీకు {cpm}, ఎకరాకు {cpa})",
           "nocost": "పంపింగ్ ఖర్చు లెక్కించలేదు: పంపు శక్తి లేదా డీజిల్ వాడకం, ధర, గంటలు లేదా పంపు ప్రవాహం నమోదు చేయండి.", "save": "మీ సాధారణ వారానికి {b} మి.మీతో పోలిస్తే {w} వారాల్లో: {s} మి.మీ {dir} = {m3} ఘ.మీ, సుమారు {sc} {cur}",
           "saved": "ఆదా", "extra": "ఎక్కువ వాడారు", "nobase": "ఆదా చూడటానికి మీ సాధారణ వారపు మి.మీ నమోదు చేయండి.", "rec": "ఈ వారం వర్షం తర్వాత పంటకు సుమారు {n} మి.మీ ({m3} ఘ.మీ) కావాలి{cost}; {d} లోపు తడి పెట్టండి.",
           "rec0": "ఈ వారం వర్షమే పంట అవసరం తీరుస్తుంది: ఈ అంచనా ప్రకారం తడి అవసరం లేదు.", "cost_rec": ", మీ మి.మీ ఖర్చుతో సుమారు {c} {cur}",
           "basis": "పరిమాణాలు, ఖర్చులు మీరు నమోదు చేసిన సంఖ్యల నుండి లెక్కించబడ్డాయి. సిఫార్సు ప్రత్యక్ష అంచనాపై సూచనాత్మక FAO-56 లెక్క: తడి పెట్టే ముందు చేత్తో నేల చూడండి."},
    "hi": {"head": "सिंचाई लागत रिपोर्ट", "use": "दिया गया पानी: {n} सिंचाई में {mm} मिमी = {m3} घन मीटर ({l} लीटर)", "cost": "पंपिंग खर्च: {c} {cur} (प्रति मिमी {cpm}, प्रति एकड़ {cpa})",
           "nocost": "पंपिंग खर्च नहीं निकला: पंप की शक्ति या डीज़ल खपत, कीमत, और घंटे या पंप प्रवाह दर्ज करें।", "save": "आपके सामान्य {b} मिमी प्रति सप्ताह की तुलना में {w} सप्ताह में: {s} मिमी {dir} = {m3} घन मीटर, लगभग {sc} {cur}",
           "saved": "बचत", "extra": "ज़्यादा लगा", "nobase": "बचत देखने के लिए अपना सामान्य मिमी प्रति सप्ताह दर्ज करें।", "rec": "इस सप्ताह बारिश के बाद फसल को लगभग {n} मिमी ({m3} घन मीटर) चाहिए{cost}; {d} तक सिंचाई करें।",
           "rec0": "इस सप्ताह बारिश फसल की ज़रूरत पूरी करती है: इस अनुमान से सिंचाई नहीं चाहिए।", "cost_rec": ", आपकी प्रति मिमी लागत पर लगभग {c} {cur}",
           "basis": "मात्रा और खर्च आपके दर्ज आँकड़ों से निकले हैं। सिफ़ारिश लाइव पूर्वानुमान पर सांकेतिक FAO-56 अनुमान है: सिंचाई से पहले हाथ से मिट्टी जाँचें।"},
}


def _n(v, hi=1e9):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if 0 < x <= hi else None


async def report(payload: dict, lang: str = "en") -> dict:
    L = T.get(lang, T["en"])
    acres = _n(payload.get("acres"), 1000)
    if not acres:
        return {"error": "acres must be a sensible number above zero"}
    cur = str(payload.get("currency") or "")[:5]
    pump = payload.get("pump") if isinstance(payload.get("pump"), dict) else {}
    kw, lph, price, flow = _n(pump.get("kw"), 500), _n(pump.get("diesel_l_per_h"), 200), _n(pump.get("price"), 1e6), _n(pump.get("flow_m3_per_h"), 5000)
    kind = "diesel" if pump.get("type") == "diesel" else "electric"
    power = lph if kind == "diesel" else kw
    rows, dates = [], []
    for e in (payload.get("entries") if isinstance(payload.get("entries"), list) else [])[:MAX_ENTRIES]:
        mm = _n(e.get("mm"), 500) if isinstance(e, dict) else None
        d = coach._parse(e.get("date")) if isinstance(e, dict) else None
        if not mm or not d:
            continue
        m3 = mm * acres * L_PER_MM_ACRE / 1000
        hours = _n(e.get("hours"), 200) or (m3 / flow if flow else None)
        cost = hours * power * price if (hours and power and price) else None
        rows.append({"date": d.isoformat(), "mm": mm, "m3": round(m3, 1), "hours": round(hours, 2) if hours else None, "cost": round(cost, 2) if cost is not None else None})
        dates.append(d)
    if not rows:
        return {"error": "add at least one irrigation with a date and mm"}
    mm_tot = sum(r["mm"] for r in rows)
    m3_tot = sum(r["m3"] for r in rows)
    priced = [r for r in rows if r["cost"] is not None]
    out = {"irrigations": len(rows), "total_mm": round(mm_tot, 1), "total_m3": round(m3_tot, 1), "total_litres": round(m3_tot * 1000), "entries": rows,
           "pump_type": kind, "currency": cur, "cost_complete": len(priced) == len(rows)}
    lines = [L["head"], L["use"].format(mm=out["total_mm"], n=len(rows), m3=out["total_m3"], l=f"{out['total_litres']:,}")]
    cpm = None
    if priced:
        cost = sum(r["cost"] for r in priced)
        mm_priced = sum(r["mm"] for r in priced)
        cpm = cost / mm_priced
        out.update(total_cost=round(cost, 2), cost_per_mm=round(cpm, 2), cost_per_acre=round(cost / acres, 2))
        lines.append(L["cost"].format(c=round(cost), cur=cur, cpm=round(cpm, 2), cpa=round(cost / acres)))
    else:
        lines.append(L["nocost"])
    base = _n(payload.get("baseline_mm_per_week"), 2000)
    if base:
        weeks = max((max(dates) - min(dates)).days / 7, 1.0)
        saved = base * weeks - mm_tot
        out["savings"] = {"baseline_mm_per_week": base, "weeks": round(weeks, 1), "saved_mm": round(saved, 1), "saved_m3": round(saved * acres * L_PER_MM_ACRE / 1000, 1),
                          "saved_cost": round(saved * cpm, 2) if cpm else None}
        lines.append(L["save"].format(b=base, w=round(weeks, 1), s=abs(round(saved, 1)), dir=L["saved"] if saved >= 0 else L["extra"],
                                      m3=abs(out["savings"]["saved_m3"]), sc=abs(round(saved * cpm)) if cpm else "-", cur=cur))
    else:
        lines.append(L["nobase"])
    crop, place = str(payload.get("crop") or "").strip(), str(payload.get("place") or "").strip()
    if crop and place:
        from . import water
        wp = await asyncio.to_thread(water.water_plan, crop, place, str(payload.get("sowing_date") or ""), str(payload.get("country") or "").upper()[:3], acres)
        if "error" not in wp:
            need = wp["irrigation_need_week_mm"]
            out["recommended_this_week"] = {"mm": need, "m3": round(need * acres * L_PER_MM_ACRE / 1000, 1), "irrigate_by": wp["irrigate_by"],
                                           "cost": round(need * cpm, 2) if cpm else None, "source": wp["source"]}
            lines.append(L["rec"].format(n=need, m3=out["recommended_this_week"]["m3"], d=wp["irrigate_by"] or "-",
                                         cost=L["cost_rec"].format(c=round(need * cpm), cur=cur) if cpm else "") if need > 0 else L["rec0"])
    lines.append(L["basis"])
    out["text"] = "\n".join(lines)
    return out
