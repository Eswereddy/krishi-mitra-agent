"""Multi-step farming agent: model decides which tools to call, we run them, loop."""
import asyncio
import json

from . import config, lang as langmod, meta_client, mock, tools, verify

SYSTEM = (
    "You are Krishi Mitra, an assistant for small farmers in Andhra Pradesh. "
    "Use tools for prices and scheme eligibility instead of guessing. "
    "If price data comes from sample-data, say it is approximate. "
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
    "Never claim certainty about scheme rules; tell the farmer where to verify. "
    "{lang_instruction}"
)
MAX_STEPS = 6
MAX_REWRITES = 2


async def run_agent(user_text: str, use_open_model: bool = False, lang: str = "auto",
                    profile: dict | None = None, history: list | None = None,
                    image: tuple[bytes, str] | None = None) -> dict:
    code = langmod.resolve(lang, user_text)
    steps: list[dict] = []

    if config.MOCK_MODE:
        # Deterministic fake plan so the UI can show agent steps without an API key.
        for name, args in [("get_mandi_price", {"commodity": "Paddy", "district": "Kurnool"}),
                           ("check_schemes", {"owns_land": True})]:
            steps.append({"tool": name, "args": args, "result": tools.run_tool(name, args)})
        return {"answer": mock.ANSWER, "steps": steps, "mock": True,
                "verification": verify.verify_answer(mock.ANSWER, steps)}

    messages = [{"role": "system", "content": SYSTEM.format(lang_instruction=langmod.instruction(code)) + _profile_text(profile)}]
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
        for c in calls:
            name = c["function"]["name"]
            try:
                args = json.loads(c["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            result = await asyncio.to_thread(tools.run_tool, name, args)
            steps.append({"tool": name, "args": args, "result": result})
            messages.append({"role": "tool", "tool_call_id": c["id"],
                             "content": json.dumps(result, ensure_ascii=False)})
    return {"answer": "Konni steps lo purtiga cheyaleka poyanu. Malli prayatninchandi.",
            "steps": steps, "mock": False,
            "verification": {"passed": False, "unverified": [], "rewrites": rewrites}}


def _profile_text(profile: dict | None) -> str:
    if not profile:
        return ""
    keep = {k: v for k, v in profile.items() if k in ("state", "district", "owns_land", "main_crop") and v not in ("", None)}
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
