"""Multi-step farming agent: model decides which tools to call, we run them, loop."""
import asyncio
import json

from . import config, lang as langmod, meta_client, mock, tools, verify

SYSTEM = (
    "You are Krishi Mitra, an assistant for small farmers anywhere in the world (India by default; the farmer profile may give another country). "
    "Use tools for prices and scheme eligibility instead of guessing. "
    "If price data comes from sample-data, say it is approximate. If its source is agmarknet-snapshot, say it is "
    "saved data from the date in the source, not today's price. "
    "Use get_weather before advising on irrigation, spraying or harvest timing. "
    "If a problem is serious or you are unsure, call get_expert_help and tell the farmer to call the "
    "Kisan Call Centre or the local agriculture officer. Never give exact pesticide doses; say to confirm "
    "with an agriculture officer. If a farmer profile is given, use it for tool arguments and do not ask again. "
    "Be proactive: if the farmer asks about prices without naming a crop, look up the profile main crop, or "
    "paddy, groundnut and cotton, and present the results instead of asking which crop. Only ask a "
    "question when something essential is missing (for example no district and no profile), and ask at most one. "
    "Present prices as a short list: crop, market, price per quintal, date. "
    "To say where to sell, use best_markets. For any income or money calculation, use calculate_revenue "
    "(never do the arithmetic yourself). When the farmer asks about schemes, also list the documents needed. "
    "If a crop photo is attached: name the crop and the most likely problem with your confidence, then use "
    "get_weather to time any spraying, mention crop insurance (PMFBY via check_schemes) if there is real crop "
    "loss, and call get_expert_help when unsure or serious. "
    "For 'sell now or wait' or 'is the price going up', call get_price_trend (and best_markets, get_weather if useful), "
    "then give one clear recommendation with the reason, and say it is guidance, not a guarantee. "
    "Never claim certainty about scheme rules; tell the farmer where to verify. "
    "For 'what is the MSP' or 'is the price above MSP', call get_msp (say the season; MSP applies only to what government "
    "buys). For 'sell now or wait' prefer hold_or_sell, then explain its reason. To compare a near and a far market, "
    "use net_market_value (its commission/loading/transport rates are assumptions: say so and ask for real quotes). "
    "For 'should I water/irrigate', call irrigation_advice. For KCC or crop-loan interest, call kcc_interest "
    "(7% a year, 4% if repaid on time; say the bank confirms). "
    "For spraying, call spray_window (never a dose). For a plant problem described in words, call lookup_problem; "
    "present it as a likely cause, not a diagnosis, give only the checks and steps returned, never name pesticides or doses. "
    "For 'where should I sell' with a quantity or distance, call sell_plan (it ranks markets after transport and fees; "
    "say the cost rates are assumptions and the farmer should get real quotes). For 'which crop should I grow' or "
    "'which crop gives more profit', call compare_crops and say yield and cost per acre are indicative assumptions, "
    "price can change by harvest, and the agriculture officer should confirm. Report only figures the tools returned. "
    "If the farmer profile country is not India (IN): use get_market_price (monthly WFP market data, say how old it is) instead of "
    "get_mandi_price, best_markets, get_price_trend, hold_or_sell, get_msp, sell_plan or compare_crops, which are India-only. "
    "Never mention rupees, MSP, PMFBY, PM-KISAN or the Kisan Call Centre to a farmer outside India; use the farmer's currency "
    "from the profile; for schemes or insurance send him to the local agricultural extension office. If no price data exists, ask what "
    "price he was offered and use calculate_revenue. Weather, irrigation, spraying and crop-problem tools work everywhere. "
    "{lang_instruction}"
)
GIVE_UP = {
    "te": "ఈ ప్రశ్నను పూర్తిగా పరిష్కరించలేకపోయాను. దయచేసి మళ్లీ ప్రయత్నించండి లేదా కిసాన్ కాల్ సెంటర్ 1800-180-1551 కు కాల్ చేయండి.",
    "hi": "मैं इस सवाल को पूरा हल नहीं कर सका। कृपया फिर से कोशिश करें या किसान कॉल सेंटर 1800-180-1551 पर कॉल करें।",
    "en": "I could not finish this question. Please try again, or call the Kisan Call Centre on 1800-180-1551.",
}
MAX_STEPS = 6
MAX_REWRITES = 2


async def run_agent(user_text: str, use_open_model: bool = False, lang: str = "auto",
                    profile: dict | None = None, history: list | None = None,
                    image: tuple[bytes, str] | None = None, on_event=None) -> dict:
    code = langmod.resolve(lang, user_text)
    steps: list[dict] = []

    if config.MOCK_MODE:
        # Deterministic fake plan so the UI can show agent steps without an API key.
        for name, args in [("get_mandi_price", {"commodity": "Paddy", "district": "Kurnool"}),
                           ("check_schemes", {"owns_land": True})]:
            _emit(on_event, {"type": "tool", "tool": name, "args": args})
            await asyncio.sleep(0.6 if on_event else 0)
            steps.append({"tool": name, "args": args, "result": tools.run_tool(name, args)})
            _emit(on_event, {"type": "tool_done", "tool": name, "ok": True})
        return {"answer": mock.ANSWER, "steps": steps, "mock": True,
                "verification": verify.verify_answer(mock.ANSWER, steps)}

    messages = [{"role": "system", "content": SYSTEM.format(lang_instruction=langmod.instruction(code, mirror=(lang not in langmod.NAMES and code == "en"))) + _profile_text(profile)}]
    messages += _clean_history(history)
    messages.append({"role": "user", "content": _user_content(user_text, image)})
    rewrites = 0
    for _ in range(MAX_STEPS):
        msg = await meta_client.chat_message(
            messages, use_open_model=use_open_model, tools=tools.TOOL_SPECS
        )
        calls = msg.get("tool_calls") or []
        if not calls:
            answer = msg.get("content") or ""
            v = verify.verify_answer(answer, steps)
            if not v["passed"] and rewrites < MAX_REWRITES:
                rewrites += 1
                _emit(on_event, {"type": "verify", "status": "retry", "unverified": v["unverified"]})
                messages.append({"role": "assistant", "content": answer})
                messages.append({"role": "user", "content": (
                    "Verification failed: these figures are not in any tool result: "
                    + ", ".join(v["unverified"]) + ". Rewrite your answer using only figures "
                    "returned by tools (call a tool if you need them), or remove those figures.")})
                continue
            if not v["passed"]:
                answer += verify.warning(v["unverified"], code)
            v["rewrites"] = rewrites
            return {"answer": answer, "steps": steps, "mock": False, "verification": v}
        messages.append(msg)
        parsed = []
        for c in calls:
            name = c["function"]["name"]
            try:
                args = json.loads(c["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            if not isinstance(args, dict):
                args = {}
            _emit(on_event, {"type": "tool", "tool": name, "args": args})
            parsed.append((c, name, args))

        async def _run(name, args):
            result = await asyncio.to_thread(tools.run_tool, name, args)
            _emit(on_event, {"type": "tool_done", "tool": name, "ok": "error" not in result})
            return result

        # independent tool calls from one model turn run concurrently (weather + prices + schemes ...)
        results = await asyncio.gather(*(_run(n, a) for _c, n, a in parsed))
        for (c, name, args), result in zip(parsed, results):
            steps.append({"tool": name, "args": args, "result": result})
            messages.append({"role": "tool", "tool_call_id": c["id"],
                             "content": json.dumps(result, ensure_ascii=False)})
    return {"answer": GIVE_UP.get(code, GIVE_UP["en"]),
            "steps": steps, "mock": False,
            "verification": {"passed": False, "unverified": [], "rewrites": rewrites}}


def _emit(on_event, event: dict) -> None:
    """Progress events for the streaming endpoints. Never lets a UI problem break the agent."""
    if on_event:
        try:
            on_event(event)
        except Exception:
            pass


def _profile_text(profile: dict | None) -> str:
    if not profile:
        return ""
    keep = {k: v for k, v in profile.items() if k in ("state", "district", "owns_land", "main_crop", "country", "currency", "sowing_date") and v not in ("", None)}
    return "\nFarmer profile: " + json.dumps(keep, ensure_ascii=False) if keep else ""


def _clean_history(history: list | None) -> list[dict]:
    """Last few chat turns from the client: only plain user/assistant text, length-limited."""
    out = []
    for m in (history or [])[-6:]:
        if isinstance(m, dict) and m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str):
            out.append({"role": m["role"], "content": m["content"][:1000]})
    return out


def _user_content(text: str, image: tuple[bytes, str] | None):
    if not image:
        return text
    import base64
    data, mime = image
    return [
        {"type": "text", "text": text},
        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{base64.b64encode(data).decode()}"}},
                ]
