"""Multi-step farming agent: model decides which tools to call, we run them, loop."""
import json

from . import config, meta_client, mock, tools

SYSTEM = (
    "You are Krishi Mitra, an assistant for small farmers in Andhra Pradesh. "
    "Use tools for prices and scheme eligibility instead of guessing. "
    "If price data comes from sample-data, say it is approximate. "
    "Never claim certainty about scheme rules; tell the farmer where to verify. "
    "Answer in simple Telugu, short and practical."
)
MAX_STEPS = 5


async def run_agent(user_text: str, use_open_model: bool = False) -> dict:
    steps: list[dict] = []

    if config.MOCK_MODE:
        # Deterministic fake plan so the UI can show agent steps without an API key.
        for name, args in [("get_mandi_price", {"commodity": "Paddy", "market": "Kurnool"}),
                           ("check_schemes", {"owns_land": True})]:
            steps.append({"tool": name, "args": args, "result": tools.run_tool(name, args)})
        return {"answer": mock.ANSWER, "steps": steps, "mock": True}

    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user_text}]
    for _ in range(MAX_STEPS):
        msg = await meta_client.chat_message(
            messages, use_open_model=use_open_model, tools=tools.TOOL_SPECS
        )
        calls = msg.get("tool_calls") or []
        if not calls:
            return {"answer": msg.get("content") or "", "steps": steps, "mock": False}
        messages.append(msg)
        for c in calls:
            name = c["function"]["name"]
            try:
                args = json.loads(c["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            result = tools.run_tool(name, args)
            steps.append({"tool": name, "args": args, "result": result})
            messages.append({"role": "tool", "tool_call_id": c["id"],
                             "content": json.dumps(result, ensure_ascii=False)})
    return {"answer": "Konni steps lo purtiga cheyaleka poyanu. Malli prayatninchandi.",
            "steps": steps, "mock": False}
