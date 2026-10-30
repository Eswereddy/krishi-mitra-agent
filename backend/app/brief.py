"""Daily brief: one tap gives the farmer today's weather, irrigation, spraying, crop price and a sell/hold guide.

Built entirely from tool results with fixed templates (no model call), so it is instant, works without an API key,
and every figure in it comes straight from a tool (it still passes through the same verification layer).
"""
import asyncio

from . import lang as langmod, tools, verify

T = {
    "en": {
        "head": "☀️ Today's brief · {place}",
        "need": "Please set your district and main crop in your profile (the person icon), then tap Today again.",
        "wx": "🌦️ Weather: up to {max}°C, rain chance {chance}% today.",
        "wx_next": "Rain chance in the next days: up to {chance}%.",
        "wx_fail": "🌦️ Weather is not available right now.",
        "irr": {"skip_rain": "Rain is likely: do not irrigate today.",
                "wait_light_rain": "Light rain is possible: wait and watch before irrigating.",
                "evening_hot": "Very hot: irrigate early morning or evening, only if the soil is dry.",
                "if_dry": "Irrigate only if the soil is dry."},
        "irr_head": "💧 Irrigation: {x}",
        "spray": {"good": "good day to spray.", "rain": "rain likely, do not spray.",
                  "wind": "too windy, do not spray.", "rain_wind": "rain and wind, do not spray.",
                  "hot": "very hot: spray only early morning or evening."},
        "spray_head": "🧴 Spraying today: {x} Ask the agriculture officer for the product and dose.",
        "price": "🌾 {crop}: ₹{price} per quintal at {market}.{tag}",
        "price_fail": "🌾 {crop}: no price found right now.",
        "tag_sample": " (sample data, approximate only)", "tag_saved": " (saved data, not today's price)",
        "trend": "📈 Price is {w} ({sign}{n}% recently).",
        "tw": {"rising": "rising", "falling": "falling", "steady": "steady"},
        "dec": {"sell_now": "⚖️ Selling now looks better than waiting.",
                "hold_short": "⚖️ Hold a little and check the price again.",
                "use_procurement_or_wait": "⚖️ Market price is below MSP: ask about government procurement first.",
                "sell_now_or_hold_if_stored": "⚖️ You can sell; hold only if you can store safely."},
        "msp": "🏷️ MSP: ₹{msp} per quintal. Market price is ₹{gap} {dir} MSP.",
        "above": "above", "below": "below",
        "foot": "Guidance only, not a guarantee.",
        "risk_heat": "🔥 Heat alert: up to {n}°C on {d}. Water crops early morning or evening and protect workers and animals.",
        "risk_rain": "⛈️ Heavy rain alert: {n} mm expected on {d}. Do not spray or fertilise before it; clear field drains and protect harvested produce.",
        "risk_wind": "💨 Strong wind alert: up to {n} km/h on {d}. Do not spray; support tall crops.",
    },
    "te": {
        "head": "☀️ ఈ రోజు సమాచారం · {place}",
        "need": "ముందు ప్రొఫైల్ (మనిషి గుర్తు) లో మీ జిల్లా, ప్రధాన పంటను నమోదు చేసి, మళ్లీ 'ఈ రోజు' నొక్కండి.",
        "wx": "🌦️ వాతావరణం: గరిష్ఠం {max}°C, ఈ రోజు వర్షం అవకాశం {chance}%.",
        "wx_next": "రాబోయే రోజుల్లో వర్షం అవకాశం గరిష్ఠంగా {chance}%.",
        "wx_fail": "🌦️ వాతావరణ సమాచారం ఇప్పుడు అందుబాటులో లేదు.",
        "irr": {"skip_rain": "వర్షం వచ్చే అవకాశం ఉంది, ఈ రోజు నీరు పెట్టకండి.",
                "wait_light_rain": "తేలికపాటి వర్షం రావచ్చు, నీరు పెట్టే ముందు కొంచెం ఆగి చూడండి.",
                "evening_hot": "ఎండ చాలా ఎక్కువ: నేల పొడిగా ఉంటే ఉదయం లేదా సాయంత్రం నీరు పెట్టండి.",
                "if_dry": "నేల పొడిగా ఉంటేనే నీరు పెట్టండి."},
        "irr_head": "💧 నీటి తడి: {x}",
        "spray": {"good": "పిచికారీకి మంచి రోజు.", "rain": "వర్షం వచ్చే అవకాశం, పిచికారీ వద్దు.",
                  "wind": "గాలి ఎక్కువ, పిచికారీ వద్దు.", "rain_wind": "వర్షం, గాలి ఉన్నాయి, పిచికారీ వద్దు.",
                  "hot": "ఎండ చాలా ఎక్కువ: ఉదయం లేదా సాయంత్రం మాత్రమే పిచికారీ చేయండి."},
        "spray_head": "🧴 ఈ రోజు పిచికారీ: {x} మందు, మోతాదు కోసం వ్యవసాయ అధికారిని అడగండి.",
        "price": "🌾 {crop}: {market} లో క్వింటాకు ₹{price}.{tag}",
        "price_fail": "🌾 {crop}: ఇప్పుడు ధర దొరకలేదు.",
        "tag_sample": " (నమూనా సమాచారం, సుమారు మాత్రమే)", "tag_saved": " (సేవ్ చేసిన పాత సమాచారం, ఈ రోజు ధర కాదు)",
        "trend": "📈 ధర {w} ({sign}{n}%).",
        "tw": {"rising": "పెరుగుతోంది", "falling": "తగ్గుతోంది", "steady": "స్థిరంగా ఉంది"},
        "dec": {"sell_now": "⚖️ ఆగడం కంటే ఇప్పుడే అమ్మడం మంచిది.",
                "hold_short": "⚖️ కొద్ది రోజులు ఆగి, మళ్లీ ధర చూడండి.",
                "use_procurement_or_wait": "⚖️ మార్కెట్ ధర MSP కంటే తక్కువ: ముందు ప్రభుత్వ కొనుగోలు గురించి అడగండి.",
                "sell_now_or_hold_if_stored": "⚖️ అమ్మవచ్చు; సురక్షితంగా నిల్వ ఉంటేనే ఆగండి."},
        "msp": "🏷️ MSP: క్వింటాకు ₹{msp}. మార్కెట్ ధర MSP కంటే ₹{gap} {dir}.",
        "above": "ఎక్కువ", "below": "తక్కువ",
        "foot": "మార్గదర్శకం మాత్రమే, హామీ కాదు.",
        "risk_heat": "🔥 వేడి హెచ్చరిక: {d} న {n}°C వరకు. ఉదయం లేదా సాయంత్రం నీరు పెట్టండి, కూలీలను, పశువులను కాపాడండి.",
        "risk_rain": "⛈️ భారీ వర్షం హెచ్చరిక: {d} న {n} mm వర్షం వచ్చే అవకాశం. ముందు పిచికారీ, ఎరువులు వద్దు; కాలువలు శుభ్రం చేయండి, కోసిన పంటను కాపాడండి.",
        "risk_wind": "💨 బలమైన గాలి హెచ్చరిక: {d} న {n} km/h వరకు. పిచికారీ వద్దు; ఎత్తైన పంటలకు ఆసరా ఇవ్వండి.",
    },
    "hi": {
        "head": "☀️ आज की जानकारी · {place}",
        "need": "पहले प्रोफ़ाइल (इंसान का आइकन) में अपना ज़िला और मुख्य फ़सल भरें, फिर 'आज' दबाएँ।",
        "wx": "🌦️ मौसम: अधिकतम {max}°C, आज बारिश की संभावना {chance}%।",
        "wx_next": "अगले दिनों में बारिश की संभावना अधिकतम {chance}%।",
        "wx_fail": "🌦️ मौसम की जानकारी अभी उपलब्ध नहीं है।",
        "irr": {"skip_rain": "बारिश की संभावना है, आज सिंचाई न करें।",
                "wait_light_rain": "हल्की बारिश हो सकती है, सिंचाई से पहले थोड़ा रुकें।",
                "evening_hot": "बहुत गर्मी है: मिट्टी सूखी हो तो सुबह या शाम को सिंचाई करें।",
                "if_dry": "मिट्टी सूखी हो तभी सिंचाई करें।"},
        "irr_head": "💧 सिंचाई: {x}",
        "spray": {"good": "छिड़काव के लिए अच्छा दिन।", "rain": "बारिश की संभावना, छिड़काव न करें।",
                  "wind": "हवा तेज़ है, छिड़काव न करें।", "rain_wind": "बारिश और हवा है, छिड़काव न करें।",
                  "hot": "बहुत गर्मी: सिर्फ़ सुबह या शाम को छिड़काव करें।"},
        "spray_head": "🧴 आज छिड़काव: {x} दवा और मात्रा के लिए कृषि अधिकारी से पूछें।",
        "price": "🌾 {crop}: {market} में ₹{price} प्रति क्विंटल।{tag}",
        "price_fail": "🌾 {crop}: अभी भाव नहीं मिला।",
        "tag_sample": " (नमूना डेटा, सिर्फ़ अनुमान)", "tag_saved": " (सहेजा हुआ डेटा, आज का भाव नहीं)",
        "trend": "📈 भाव {w} ({sign}{n}%)।",
        "tw": {"rising": "बढ़ रहा है", "falling": "घट रहा है", "steady": "स्थिर है"},
        "dec": {"sell_now": "⚖️ रुकने से बेहतर अभी बेचना लगता है।",
                "hold_short": "⚖️ थोड़ा रुकें और भाव फिर देखें।",
                "use_procurement_or_wait": "⚖️ बाज़ार भाव MSP से कम है: पहले सरकारी खरीद के बारे में पूछें।",
                "sell_now_or_hold_if_stored": "⚖️ बेच सकते हैं; सुरक्षित भंडारण हो तभी रुकें।"},
        "msp": "🏷️ MSP: ₹{msp} प्रति क्विंटल। बाज़ार भाव MSP से ₹{gap} {dir} है।",
        "above": "ज़्यादा", "below": "कम",
        "foot": "सिर्फ़ मार्गदर्शन, गारंटी नहीं।",
        "risk_heat": "🔥 गर्मी की चेतावनी: {d} को {n}°C तक। सुबह या शाम को सिंचाई करें, मज़दूरों और पशुओं को बचाएँ।",
        "risk_rain": "⛈️ भारी बारिश की चेतावनी: {d} को {n} mm बारिश की संभावना। उससे पहले छिड़काव या खाद न दें; नालियाँ साफ़ करें, कटी फ़सल बचाएँ।",
        "risk_wind": "💨 तेज़ हवा की चेतावनी: {d} को {n} km/h तक। छिड़काव न करें; ऊँची फ़सलों को सहारा दें।",
    },
}


def _n(x) -> str:
    return f"{int(round(x)):,}"


HEAT_C, HEAVY_RAIN_MM, STRONG_WIND_KMH = 40, 25, 40


def risk_lines(L: dict, days: list[dict]) -> list[str]:
    """Warnings for dangerous weather in the forecast (worst day for each kind), so a farmer is told before it hits."""
    out = []
    kinds = (("risk_heat", "max_c", HEAT_C, lambda v: round(v)), ("risk_rain", "rain_mm", HEAVY_RAIN_MM, lambda v: round(v)),
             ("risk_wind", "wind_kmh", STRONG_WIND_KMH, lambda v: round(v)))
    for key, field, limit, fmt in kinds:
        worst = max((d for d in days if (d.get(field) or 0) >= limit), key=lambda d: d[field], default=None)
        if worst:
            out.append(L[key].format(n=fmt(worst[field]), d=worst["date"]))
    return out


def compose(code: str, profile: dict, steps: list[dict]) -> str:
    L = T[code]
    res = {s["tool"]: s["result"] for s in steps}
    place = ", ".join(x for x in (profile.get("district"), profile.get("state")) if x)
    lines = [L["head"].format(place=place)]
    wx = res.get("get_weather", {})
    days = wx.get("forecast") or []
    if days:
        d0 = days[0]
        lines.append(L["wx"].format(max=round(d0["max_c"]), chance=d0.get("rain_chance_pct") or 0))
        later = [d.get("rain_chance_pct") or 0 for d in days[1:]]
        if later and max(later) >= 40:
            lines.append(L["wx_next"].format(chance=max(later)))
    else:
        lines.append(L["wx_fail"])
    lines.extend(risk_lines(L, days))
    irr = (res.get("irrigation_advice", {}).get("days") or [None])[0]
    if irr:
        lines.append(L["irr_head"].format(x=L["irr"][irr["code"]]))
    spray = (res.get("spray_window", {}).get("days") or [None])[0]
    if spray:
        lines.append(L["spray_head"].format(x=L["spray"][spray["code"]]))
    crop = profile.get("main_crop")
    if crop:
        price = res.get("get_mandi_price", {})
        row = (price.get("results") or [None])[0]
        src = str(price.get("source", ""))
        if row and row.get("modal_price_per_quintal"):
            tag = L["tag_sample"] if "sample" in src else L["tag_saved"] if "snapshot" in src else ""
            lines.append(L["price"].format(crop=crop, price=_n(row["modal_price_per_quintal"]),
                                           market=row.get("market") or row.get("district") or "-", tag=tag))
        else:
            lines.append(L["price_fail"].format(crop=crop))
        hs = res.get("hold_or_sell", {})
        tr = (hs.get("trend") or {})
        if tr.get("trend") in L["tw"] and tr.get("change_pct") is not None:
            lines.append(L["trend"].format(w=L["tw"][tr["trend"]], sign="+" if tr["change_pct"] > 0 else "-" if tr["change_pct"] < 0 else "",
                                           n=abs(tr["change_pct"])))
        if hs.get("recommendation") in L["dec"]:
            lines.append(L["dec"][hs["recommendation"]])
        gap, msp = hs.get("current_vs_msp_rs_per_quintal"), hs.get("msp_price_per_quintal")
        if msp and gap is not None:
            lines.append(L["msp"].format(msp=_n(msp), gap=_n(abs(gap)), dir=L["above"] if gap >= 0 else L["below"]))
    lines.append(L["foot"])
    return "\n".join(lines)


async def build_brief(profile: dict | None, lang: str = "auto") -> dict:
    profile = {k: v for k, v in (profile or {}).items() if k in ("state", "district", "main_crop", "owns_land")}
    code = lang if lang in T else "te"
    district, crop = str(profile.get("district") or "").strip(), str(profile.get("main_crop") or "").strip()
    if not district:
        return {"answer": T[code]["need"], "steps": [], "mock": False,
                "verification": {"passed": True, "unverified": [], "checked": 0, "rewrites": 0}}
    state = profile.get("state") or "Andhra Pradesh"
    plan = [("get_weather", {"place": district, "days": 3}), ("irrigation_advice", {"place": district, "days": 3}),
            ("spray_window", {"place": district, "days": 3})]
    if crop:
        plan += [("get_mandi_price", {"commodity": crop, "district": district, "state": state}),
                 ("hold_or_sell", {"commodity": crop, "district": district, "state": state})]
    results = await asyncio.gather(*(asyncio.to_thread(tools.run_tool, n, a) for n, a in plan))
    steps = [{"tool": n, "args": a, "result": r} for (n, a), r in zip(plan, results)]
    answer = compose(code, profile, steps)
    v = verify.verify_answer(answer, steps)
    v["rewrites"] = 0
    return {"answer": answer, "steps": steps, "mock": False, "verification": v, "lang": code}
