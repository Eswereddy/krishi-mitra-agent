"""The eval harness itself works (fake model, no API). Run from backend/: python tests/test_eval.py"""
import asyncio
import os
os.environ["CACHE_TTL_S"] = "0"
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "eval"))
from app import config, meta_client  # noqa: E402
import run_eval  # noqa: E402


def test_harness_scores_tool_choice_verification_and_leaks():
    config.MOCK_MODE = False
    run_eval.CASES[:] = run_eval.CASES[:1] + [c for c in run_eval.CASES if c[1]["country"] == "KE"][:1]
    from app import tools
    tools.TOOL_FUNCS["get_mandi_price"] = lambda **k: {"source": "x", "results": [{"modal_price_per_quintal": 2300}]}
    tools.TOOL_FUNCS["get_market_price"] = lambda **k: {"source": "x", "results": [{"price": 60}]}

    async def fake(messages, use_open_model=False, **kw):
        if not any(m.get("role") == "tool" for m in messages if isinstance(m, dict)):
            name = "get_mandi_price" if "Kurnool" in messages[-1]["content"] else "get_market_price"
            return {"content": None, "tool_calls": [{"id": "c", "function": {"name": name, "arguments": "{}"}}]}
        return {"content": "Price is 2300 per quintal." if "Kurnool" in messages[-1]["content"] else "Price is 60 per kg (see MSP).", "tool_calls": None}
    meta_client.chat_message = fake
    rows = [asyncio.run(run_eval.run_case(*c)) for c in run_eval.CASES]
    assert rows[0]["ok_tool"] and rows[0]["verified"] and rows[0]["rewrites"] == 0
    assert rows[1]["ok_tool"] and rows[1]["leak"] and not rows[1]["verified"]       # "MSP" for a Kenyan farmer is flagged


if __name__ == "__main__":
    test_harness_scores_tool_choice_verification_and_leaks()
    print("ok")
