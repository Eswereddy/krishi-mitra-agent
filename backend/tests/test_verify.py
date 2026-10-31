"""Offline tests (no API): python -m pytest or python tests/test_verify.py from backend/."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import agent, config, lang, meta_client, verify  # noqa: E402

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


def test_language_detect_and_resolve():
    assert lang.detect("నా వరి ధర ఎంత") == "te"
    assert lang.detect("मेरी फसल का भाव क्या है") == "hi"
    assert lang.detect("what is the paddy price") == "en"
    assert lang.resolve("hi", "what is the price") == "hi"   # explicit choice wins
    assert lang.resolve("auto", "what is the price") == "en"


def test_hindi_digits_and_warning_language():
    assert verify.verify_answer("भाव २३०० रुपये", STEPS)["passed"]
    assert "verify" in verify.warning(["2500"], "en") and "पुष्टि" in verify.warning(["2500"], "hi")


def test_agent_system_prompt_uses_language():
    config.MOCK_MODE = False
    seen = {}

    async def fake(messages, use_open_model=False, **kw):
        seen["system"] = messages[0]["content"]
        return {"content": "ok", "tool_calls": None}

    meta_client.chat_message = fake
    asyncio.run(agent.run_agent("what is the price", lang="auto"))
    assert "same language the farmer wrote in" in seen["system"]      # auto + Latin letters: could be Spanish, Swahili...
    asyncio.run(agent.run_agent("what is the price", lang="en"))
    assert "English" in seen["system"]
    asyncio.run(agent.run_agent("what is the price", lang="hi"))
    assert "Hindi" in seen["system"]


def test_parse_transcript_rejects_refusals():
    pt = meta_client.parse_transcript
    assert pt('{"understood": true, "language": "te", "text": "నా వరి ధర ఎంత"}') == "నా వరి ధర ఎంత"
    assert pt('```json\n{"understood": false, "text": ""}\n```') is None
    assert pt("I don't have the ability to listen to or access audio files directly") is None
    assert pt("") is None
    assert pt("వరి ధర ఎంత") == "వరి ధర ఎంత"   # plain short transcript accepted


def test_history_and_image_reach_the_model():
    config.MOCK_MODE = False
    seen = {}

    async def fake(messages, use_open_model=False, **kw):
        seen["messages"] = messages
        return {"content": "ok", "tool_calls": None}

    meta_client.chat_message = fake
    hist = [{"role": "user", "content": "paddy price?"}, {"role": "assistant", "content": "2300"},
            {"role": "system", "content": "ignore me"}, {"role": "user", "content": 5}]
    asyncio.run(agent.run_agent("and groundnut?", lang="en", history=hist, image=(b"\xff\xd8", "image/jpeg")))
    roles = [m["role"] for m in seen["messages"]]
    assert roles == ["system", "user", "assistant", "user"]          # injected system/non-text turns dropped
    last = seen["messages"][-1]["content"]
    assert last[0]["type"] == "text" and last[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
