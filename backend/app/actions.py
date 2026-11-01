"""Proposed actions: after an answer, the app may OFFER to do something useful (save the advice to 'My results', set a price alert).
Nothing is ever executed by the server or the model: each proposal is built in code from tool results and needs the farmer's
explicit tap on the phone. Declining changes nothing.
"""
import hashlib
import re

from . import locale as loc

KIND = (("hold_or_sell", "sell"), ("sell_plan", "sell"), ("best_markets", "sell"), ("net_market_value", "sell"), ("get_price_trend", "sell"), ("price_seasonality", "sell"),
        ("water_plan", "irrigate"), ("irrigation_advice", "irrigate"), ("spray_window", "protect"), ("disease_risk", "protect"), ("lookup_problem", "protect"),
        ("planting_window", "sow"), ("storage_check", "store"), ("compare_inputs", "fertilise"))
T = {
    "en": {"log": "Save this advice to My results so you can track whether it helped?", "alert": "Alert me when {crop} reaches {target} per quintal (5% above today's {cur})?"},
    "te": {"log": "ఈ సలహా పనిచేసిందో చూడటానికి 'నా ఫలితాలు'లో సేవ్ చేయాలా?", "alert": "{crop} ధర క్వింటాలుకు {target} కు చేరినప్పుడు చెప్పాలా (ఈ రోజు {cur} కంటే 5% ఎక్కువ)?"},
    "hi": {"log": "यह सलाह 'मेरे नतीजे' में सेव करें ताकि देख सकें कि काम आई?", "alert": "{crop} का भाव प्रति क्विंटल {target} पर पहुँचे तो बताएँ (आज के {cur} से 5% ऊपर)?"},
}


def _plain(text: str) -> str:
    return re.sub(r"[*_`#>\[\]]", "", text or "").strip()[:280]


def propose(steps: list[dict], answer: str, lang: str, profile: dict | None) -> list[dict]:
    L = T.get(lang, T["en"])
    ok = [s for s in steps if isinstance(s.get("result"), dict) and "error" not in s["result"]]
    used = {s["tool"] for s in ok}
    out = []
    kind = next((k for t, k in KIND if t in used), None)
    crop = str((profile or {}).get("main_crop") or "")[:40]
    if kind and answer.strip():
        text = _plain(answer)
        out.append({"id": "log-" + hashlib.sha1(text.encode()).hexdigest()[:8], "type": "log_recommendation", "label": L["log"], "requires_confirmation": True,
                    "payload": {"kind": kind, "text": text, "crop": crop}})
    if loc.is_india(profile or {}) and (profile or {}).get("district"):
        for s in ok:
            if s["tool"] == "get_mandi_price":
                rows = s["result"].get("results") or []
                price = next((r.get("modal_price_per_quintal") for r in rows if isinstance(r.get("modal_price_per_quintal"), (int, float)) and r["modal_price_per_quintal"] > 0), None)
                if price:
                    name = str(s.get("args", {}).get("commodity") or crop or "")[:40]
                    target = int(round(price * 1.05 / 10.0) * 10)
                    out.append({"id": f"alert-{name.lower()}-{target}", "type": "set_price_alert", "requires_confirmation": True,
                                "label": L["alert"].format(crop=name, target=target, cur=int(price)),
                                "payload": {"crop": name, "district": str(profile["district"])[:40], "target": target, "direction": "above", "current": price}})
                break
    return out[:2]
