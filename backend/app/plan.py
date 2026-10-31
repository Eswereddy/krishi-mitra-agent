"""Week plan: the agent looks at the next 7 days and decides what the farmer should do, in priority order.

Autonomous but fully checkable: it calls the same tools as the chat agent (weather, irrigation, spraying, price,
sell/hold, schemes), applies fixed rules to rank the actions (urgent / soon / good to know), and writes them with
fixed templates in Telugu, Hindi or English. No model call: instant, works offline from the model, and every figure
still passes the verification layer. Guidance, not a guarantee.
"""
import asyncio

from . import brief, coach, locale as loc, tools, verify

T = {
    "en": {
        "head": "📅 Your week plan · {place}",
        "need": "Please set your district in your profile (the person icon), then tap This week again.",
        "irr_on": "💧 Next good day to irrigate (only if the soil is dry): {d}.",
        "irr_none": "💧 Rain is coming: no need to irrigate this week.",
        "spray_on": "🧴 Best spraying day: {d}. Ask the agriculture officer for the product and dose.",
        "spray_none": "🧴 No good spraying day this week (rain or wind). Wait.",
        "schemes": "🏛️ Schemes you may qualify for: {names}. Open the Schemes card for documents.",
        "sell": "💰 {crop}: ", "foot": "Guidance only, not a guarantee.",
        "season_dry": "🏜️ Season check: rain in the last 30 days is {pct}% of normal ({mm} mm against {normal} mm). Plan irrigation and sowing carefully.",
        "season_wet": "🌧️ Season check: rain in the last 30 days is {pct}% of normal ({mm} mm against {normal} mm). Watch for waterlogging and delay field work on wet days.",
        "water": "💧 Water plan: your crop needs about {mm} mm of irrigation this week after rain (about {litres} litres per acre){by}. Give only the shortfall: it saves water and pumping cost.",
        "water_by": ", irrigate by {d}",
        "water_none": "💧 Water plan: rain should cover your crop this week, so no irrigation is needed. Rain falling on a 100 m² roof or pond catchment could give about {harvest} litres to store.",
        "disease": "🍄 Disease watch: humid, mild weather on {d} ({h} humid hours) favours fungal disease. Check leaves and avoid watering them late in the evening.",
        "coach": "🌱 {crop}, day {day} · {stage} ({left} days to expected harvest): {tasks}",
        "coach_before": "🌱 {crop}: sowing date is {n} days away. Check the planting window before you sow.",
        "coach_late": "🌱 {crop}: this is past the usual harvest time. Check the crop and plan harvest and storage.",
        "lv": {"urgent": "Do first", "soon": "This week", "info": "Good to know"},
    },
    "te": {
        "head": "📅 మీ వారం ప్లాన్ · {place}",
        "need": "ముందు ప్రొఫైల్ (మనిషి గుర్తు) లో మీ జిల్లా నమోదు చేసి, మళ్లీ 'ఈ వారం' నొక్కండి.",
        "irr_on": "💧 నీరు పెట్టడానికి తర్వాతి మంచి రోజు (నేల పొడిగా ఉంటేనే): {d}.",
        "irr_none": "💧 వర్షం వస్తోంది: ఈ వారం నీరు పెట్టాల్సిన అవసరం లేదు.",
        "spray_on": "🧴 పిచికారీకి మంచి రోజు: {d}. మందు, మోతాదు కోసం వ్యవసాయ అధికారిని అడగండి.",
        "spray_none": "🧴 ఈ వారం పిచికారీకి మంచి రోజు లేదు (వర్షం లేదా గాలి). ఆగండి.",
        "schemes": "🏛️ మీకు వర్తించే పథకాలు: {names}. పత్రాల కోసం పథకాల కార్డు చూడండి.",
        "sell": "💰 {crop}: ", "foot": "మార్గదర్శకం మాత్రమే, హామీ కాదు.",
        "season_dry": "🏜️ సీజన్ పరిశీలన: గత 30 రోజుల్లో వర్షం సాధారణంలో {pct}% ({mm} మి.మీ., సాధారణం {normal} మి.మీ.). నీటి తడులు, విత్తనం జాగ్రత్తగా ప్లాన్ చేయండి.",
        "season_wet": "🌧️ సీజన్ పరిశీలన: గత 30 రోజుల్లో వర్షం సాధారణంలో {pct}% ({mm} మి.మీ., సాధారణం {normal} మి.మీ.). నీరు నిలవకుండా చూడండి.",
        "water": "💧 నీటి ప్లాన్: వర్షం పోగా ఈ వారం మీ పంటకు సుమారు {mm} మి.మీ. నీరు కావాలి (ఎకరాకు సుమారు {litres} లీటర్లు){by}. లోటు మాత్రమే ఇవ్వండి: నీరు, కరెంట్ ఖర్చు ఆదా.",
        "water_by": ", {d} లోపు నీరు పెట్టండి",
        "water_none": "💧 నీటి ప్లాన్: ఈ వారం వర్షమే పంటకు సరిపోతుంది, నీరు పెట్టాల్సిన అవసరం లేదు. 100 చ.మీ. పైకప్పు లేదా కుంటపై పడే వర్షంతో సుమారు {harvest} లీటర్లు నిల్వ చేయవచ్చు.",
        "disease": "🍄 తెగులు హెచ్చరిక: {d} న తేమ, మితమైన వాతావరణం ({h} తేమ గంటలు) శిలీంధ్ర తెగుళ్లకు అనుకూలం. ఆకులను చూడండి, సాయంత్రం ఆలస్యంగా ఆకులపై నీరు పోయవద్దు.",
        "coach": "🌱 {crop}, {day}వ రోజు · {stage} (కోతకు సుమారు {left} రోజులు): {tasks}",
        "coach_before": "🌱 {crop}: విత్తే తేదీకి ఇంకా {n} రోజులు. విత్తే ముందు విత్తే సమయం చూడండి.",
        "coach_late": "🌱 {crop}: సాధారణ కోత సమయం దాటింది. పంటను చూసి కోత, నిల్వ ప్లాన్ చేయండి.",
        "lv": {"urgent": "ముందు చేయండి", "soon": "ఈ వారంలో", "info": "తెలుసుకోండి"},
    },
    "hi": {
        "head": "📅 आपकी हफ़्ते की योजना · {place}",
        "need": "पहले प्रोफ़ाइल (इंसान का आइकन) में अपना ज़िला भरें, फिर 'इस हफ़्ते' दबाएँ।",
        "irr_on": "💧 सिंचाई का अगला अच्छा दिन (मिट्टी सूखी हो तभी): {d}।",
        "irr_none": "💧 बारिश आ रही है: इस हफ़्ते सिंचाई की ज़रूरत नहीं।",
        "spray_on": "🧴 छिड़काव का सबसे अच्छा दिन: {d}। दवा और मात्रा कृषि अधिकारी से पूछें।",
        "spray_none": "🧴 इस हफ़्ते छिड़काव का अच्छा दिन नहीं (बारिश या हवा)। रुकें।",
        "schemes": "🏛️ आपके लिए योजनाएँ: {names}। दस्तावेज़ों के लिए योजना कार्ड देखें।",
        "sell": "💰 {crop}: ", "foot": "सिर्फ़ मार्गदर्शन, गारंटी नहीं।",
        "season_dry": "🏜️ मौसम की जाँच: पिछले 30 दिनों में बारिश सामान्य की {pct}% ({mm} मिमी, सामान्य {normal} मिमी)। सिंचाई और बुवाई सोच-समझकर करें।",
        "season_wet": "🌧️ मौसम की जाँच: पिछले 30 दिनों में बारिश सामान्य की {pct}% ({mm} मिमी, सामान्य {normal} मिमी)। जलभराव पर नज़र रखें।",
        "water": "💧 पानी की योजना: बारिश के बाद इस हफ़्ते फसल को लगभग {mm} मिमी सिंचाई चाहिए (प्रति एकड़ लगभग {litres} लीटर){by}। सिर्फ़ कमी पूरी करें: पानी और बिजली की बचत।",
        "water_by": ", {d} तक सिंचाई करें",
        "water_none": "💧 पानी की योजना: इस हफ़्ते बारिश ही फसल के लिए काफ़ी है, सिंचाई की ज़रूरत नहीं। 100 वर्ग मीटर छत या तालाब पर गिरे पानी से लगभग {harvest} लीटर जमा हो सकता है।",
        "disease": "🍄 रोग चेतावनी: {d} को नम और हल्का मौसम ({h} नम घंटे) फफूँद रोगों के अनुकूल है। पत्तियाँ देखें, शाम को देर से उन पर पानी न डालें।",
        "coach": "🌱 {crop}, दिन {day} · {stage} (अनुमानित कटाई में {left} दिन): {tasks}",
        "coach_before": "🌱 {crop}: बुवाई की तारीख में अभी {n} दिन हैं। बुवाई से पहले बुवाई का समय जाँचें।",
        "coach_late": "🌱 {crop}: सामान्य कटाई का समय निकल चुका है। फसल देखकर कटाई और भंडारण की योजना बनाएँ।",
        "lv": {"urgent": "पहले करें", "soon": "इस हफ़्ते", "info": "जानने लायक"},
    },
}
ORDER = {"urgent": 0, "soon": 1, "info": 2}


def _by_date(res: dict, key: str) -> dict:
    return {d["date"]: d for d in (res.get(key) or [])}


def decide(code: str, profile: dict, res: dict) -> tuple[list[dict], list[dict]]:
    """Rules that turn tool results into (priorities, per-day rows). Pure function, easy to test."""
    L, B = T[code], brief.T[code]
    forecast = (res.get("get_weather") or {}).get("forecast") or []
    irr, spray = _by_date(res.get("irrigation_advice") or {}, "days"), _by_date(res.get("spray_window") or {}, "days")
    days = [{"date": f["date"], "max_c": f.get("max_c"), "min_c": f.get("min_c"), "rain_mm": f.get("rain_mm"),
             "rain_chance_pct": f.get("rain_chance_pct"), "wind_kmh": f.get("wind_kmh"),
             "irrigate": bool((irr.get(f["date"]) or {}).get("irrigate")),
             "spray_ok": bool((spray.get(f["date"]) or {}).get("suitable"))} for f in forecast]
    pr: list[dict] = []

    def add(level, key, text):
        pr.append({"level": level, "key": key, "label": L["lv"][level], "text": text})

    for key, field, limit, rk in (("heavy_rain", "rain_mm", brief.HEAVY_RAIN_MM, "risk_rain"),
                                  ("heat", "max_c", brief.HEAT_C, "risk_heat"),
                                  ("wind", "wind_kmh", brief.STRONG_WIND_KMH, "risk_wind")):
        worst = max((f for f in forecast if (f.get(field) or 0) >= limit), key=lambda f: f[field], default=None)
        if worst:
            add("urgent", key, B[rk].format(n=round(worst[field]), d=worst["date"]))
    hs = res.get("hold_or_sell") or {}
    rec, crop = hs.get("recommendation"), profile.get("main_crop")
    if crop and rec in B["dec"]:
        level = "urgent" if rec in ("sell_now", "use_procurement_or_wait") else "soon" if rec == "hold_short" else "info"
        add(level, "market", L["sell"].format(crop=crop) + B["dec"][rec].replace("⚖️ ", ""))
        gap, msp = hs.get("current_vs_msp_rs_per_quintal"), hs.get("msp_price_per_quintal")
        if msp and gap is not None and gap < 0:
            add("urgent", "below_msp", B["msp"].format(msp=brief._n(msp), gap=brief._n(abs(gap)), dir=B["below"]))
    cg = res.get("crop_guide") or {}
    if cg.get("status") == "growing":
        tasks = " ".join(coach.text(t["code"], code) for t in cg["tasks"][:2])
        add("urgent" if cg.get("dry_week_ahead") else "soon", "coach",
            L["coach"].format(crop=cg["crop"], day=cg["day_of_crop"], stage=coach.stage_label(cg["stage"], code),
                              left=cg["days_to_expected_harvest"], tasks=tasks))
    elif cg.get("status") == "not_sown":
        add("info", "coach", L["coach_before"].format(crop=cg["crop"], n=cg["days_until_sowing"]))
    elif cg.get("status") == "past_expected_harvest":
        add("soon", "coach", L["coach_late"].format(crop=cg["crop"]))
    sc = res.get("season_check") or {}
    if sc.get("rain_band") in ("much_below", "below") and sc.get("rain_vs_normal_pct") is not None:
        add("soon", "season", L["season_dry"].format(pct=sc["rain_vs_normal_pct"], mm=sc["rain_mm"], normal=sc["normal_rain_mm"]))
    elif sc.get("rain_band") in ("much_above", "above"):
        add("soon", "season", L["season_wet"].format(pct=sc["rain_vs_normal_pct"], mm=sc["rain_mm"], normal=sc["normal_rain_mm"]))
    wp = res.get("water_plan") or {}
    if "irrigation_need_week_mm" in wp:
        if wp["irrigation_need_week_mm"] >= 1:
            by = L["water_by"].format(d=wp["irrigate_by"]) if wp.get("irrigate_by") else ""
            add("soon", "water", L["water"].format(mm=round(wp["irrigation_need_week_mm"]), litres=wp["irrigation_need_litres"], by=by))
        else:
            add("info", "water", L["water_none"].format(harvest=wp["rain_harvest_litres_per_100m2"]))
    dr = res.get("disease_risk") or {}
    if dr.get("worst_risk") in ("moderate", "high"):
        hrs = next((d["wet_hours"] for d in dr["days"] if d["date"] == dr["worst_day"]), 0)
        add("urgent" if dr["worst_risk"] == "high" else "soon", "disease", L["disease"].format(d=dr["worst_day"], h=hrs))
    ni = (res.get("irrigation_advice") or {}).get("next_irrigation_day")
    if irr:
        add("soon", "irrigate", L["irr_on"].format(d=ni) if ni else L["irr_none"])
    if spray:
        best = (res.get("spray_window") or {}).get("best_day")
        add("soon" if best else "info", "spray", L["spray_on"].format(d=best) if best else L["spray_none"])
    matched = [s["name"] for s in (res.get("check_schemes") or {}).get("matched") or []]
    if matched:
        add("info", "schemes", L["schemes"].format(names=", ".join(matched[:4])))
    pr.sort(key=lambda p: ORDER[p["level"]])
    return pr, days


def compose(code: str, profile: dict, priorities: list[dict]) -> str:
    L = T[code]
    place = ", ".join(x for x in (profile.get("district"), profile.get("state")) if x)
    out = [L["head"].format(place=place)]
    dot = {"urgent": "🔴", "soon": "🟡", "info": "🟢"}
    out += [f"{dot[p['level']]} {p['text']}" for p in priorities]
    out.append(L["foot"])
    return "\n".join(out)


async def build_plan(profile: dict | None, lang: str = "auto") -> dict:
    profile = {k: v for k, v in (profile or {}).items() if k in ("state", "district", "main_crop", "owns_land", "country", "sowing_date")}
    code = lang if lang in T else ("te" if lang == "auto" else "en")
    district, crop = str(profile.get("district") or "").strip(), str(profile.get("main_crop") or "").strip()
    if not district:
        return {"answer": T[code]["need"], "steps": [], "mock": False,
                "verification": {"passed": True, "unverified": [], "checked": 0, "rewrites": 0}}
    state = profile.get("state") or "Andhra Pradesh"
    plan = [("get_weather", {"place": district, "days": 7}), ("irrigation_advice", {"place": district, "days": 7}),
            ("spray_window", {"place": district, "days": 7}),
            ]
    if loc.is_india(profile):
        plan.append(("check_schemes", {"owns_land": bool(profile.get("owns_land")), "state": state}))
    plan.append(("season_check", {"place": district, "country": profile.get("country") or "IN"}))
    if crop:
        plan.append(("disease_risk", {"crop": crop, "place": district, "country": profile.get("country") or "IN"}))
        plan.append(("water_plan", {"crop": crop, "place": district, "sowing_date": profile.get("sowing_date") or "",
                                    "country": profile.get("country") or "IN"}))
    if crop and profile.get("sowing_date"):
        plan.append(("crop_guide", {"crop": crop, "sowing_date": profile["sowing_date"], "place": district,
                                    "country": profile.get("country") or "IN"}))
    if crop and loc.is_india(profile):
        plan.append(("hold_or_sell", {"commodity": crop, "district": district, "state": state}))
    results = await asyncio.gather(*(asyncio.to_thread(tools.run_tool, n, a) for n, a in plan))
    steps = [{"tool": n, "args": a, "result": r} for (n, a), r in zip(plan, results)]
    res = {s["tool"]: s["result"] for s in steps}
    priorities, days = decide(code, profile, res)
    if not days:                                   # say so instead of silently planning without a forecast
        priorities.insert(0, {"level": "info", "key": "no_weather", "label": T[code]["lv"]["info"], "text": brief.T[code]["wx_fail"]})
    answer = compose(code, profile, priorities)
    v = verify.verify_answer(answer, steps)
    v["rewrites"] = 0
    steps.append({"tool": "week_plan", "args": {}, "result": {"days": days, "priorities": priorities}})
    return {"answer": answer, "steps": steps, "mock": False, "verification": v, "lang": code}
