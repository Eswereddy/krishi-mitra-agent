"""Offline tests (no API): python -m pytest or python tests/test_verify.py from backend/."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import agent, config, meta_client, verify  # noqa: E402

STEPS = [{"tool": "get_mandi_price", "args": {}, "result": {"results": [{"modal_price_per_quintal": 2300}]}}]


def test_numbers_match_tool_result():
    assert verify.verify_answer("ధర క్వింటాలుకు 2,300 రూపాయలు", STEPS)["passed"]
    assert verify.verify_answer("ధర ౨౩౦౦", STEPS)["passed"]  # Telugu digits


def test_invented_number_fails():
    v = verify.verify_answer("ధర 2500 రూపాయలు", STEPS)
    assert not v["passed"] and v["unverified"] == ["2500"]


def test_agent_retries_then_warns():
    config.MOCK_MODE = False
    replies = iter([
        {"content": "ధర 2500", "tool_calls": None},   # unverified -> rewrite requested
        {"content": "ధర 2500", "tool_calls": None},   # still unverified
        {"content": "ధర 2500", "tool_calls": None},   # still unverified -> warning appended
    ])

    async def fake(messages, use_open_model=False, **kw):
        return next(replies)

    meta_client.chat_message = fake
    out = asyncio.run(agent.run_agent("ధర ఎంత"))
    assert out["verification"]["rewrites"] == 2 and "⚠️" in out["answer"]


def test_agent_accepts_grounded_answer():
    config.MOCK_MODE = False
    out_steps = []

    async def fake(messages, use_open_model=False, **kw):
        if not any(m.get("role") == "tool" for m in messages if isinstance(m, dict)):
            return {"content": None, "tool_calls": [{"id": "c1", "function": {
                "name": "get_mandi_price", "arguments": '{"commodity": "Paddy", "market": "Kurnool"}'}}]}
        return {"content": "ధర 2300", "tool_calls": None}

    meta_client.chat_message = fake
    out = asyncio.run(agent.run_agent("ధర ఎంత"))
    assert out["verification"]["passed"] and "⚠️" not in out["answer"] and len(out["steps"]) == 1


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
