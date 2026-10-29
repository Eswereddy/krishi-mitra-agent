"""Offline tests for rate limiting, hidden debug endpoints, the TTL cache and parallel tool calls.
Run from backend/: python tests/test_hardening.py"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["MOCK_MODE"] = "1"

from fastapi.testclient import TestClient  # noqa: E402

from app import agent, config, main, ratelimit, tools  # noqa: E402


def test_rate_limit_blocks_then_recovers():
    ratelimit._hits.clear()
    limit = ratelimit.LIMITS["/api/agent"]
    for i in range(limit):
        assert ratelimit.check("1.2.3.4", "/api/agent/stream", now=100.0 + i * 0.01) is None
    wait = ratelimit.check("1.2.3.4", "/api/agent", now=101.0)
    assert wait is not None and wait >= 1
    assert ratelimit.check("5.6.7.8", "/api/agent", now=101.0) is None        # other IPs unaffected
    assert ratelimit.check("1.2.3.4", "/api/health", now=101.0) is None        # cheap routes unlimited
    assert ratelimit.check("1.2.3.4", "/api/agent", now=100.0 + ratelimit.WINDOW_S + 1) is None  # window passed


def test_rate_limit_returns_429_over_http():
    ratelimit._hits.clear()
    client = TestClient(main.app)
    codes = [client.post("/api/agent", json={"question": "hi"}).status_code
             for _ in range(ratelimit.LIMITS["/api/agent"] + 1)]
    assert codes[-1] == 429 and 429 not in codes[:-1]
    ratelimit._hits.clear()


def test_debug_endpoints_hidden_by_default():
    client = TestClient(main.app)
    config.DEBUG_ENDPOINTS = False
    assert client.get("/api/debug/mandi").status_code == 404
    assert client.get("/api/debug/weather").status_code == 404
    assert client.get("/api/models").status_code == 404
    config.DEBUG_ENDPOINTS = True
    assert client.get("/api/debug/weather").status_code != 404
    config.DEBUG_ENDPOINTS = False


def test_cache_serves_repeat_calls_and_skips_errors():
    os.environ["CACHE_TTL_S"] = "600"
    tools.cache_clear()
    calls = {"n": 0}

    def good():
        calls["n"] += 1
        return {"ok": calls["n"]}

    assert tools._cached("t", "k", good) == {"ok": 1}
    assert tools._cached("t", "k", good) == {"ok": 1}          # served from cache
    assert calls["n"] == 1

    bad = {"n": 0}

    def failing():
        bad["n"] += 1
        return {"error": "down"}

    ok = lambda v: "error" not in v
    tools._cached("t", "e", failing, ok=ok)
    tools._cached("t", "e", failing, ok=ok)
    assert bad["n"] == 2                                       # errors are retried, never cached

    os.environ["CACHE_TTL_S"] = "0"                            # TTL 0 disables caching
    tools._cached("t", "k", good)
    assert calls["n"] == 2
    tools.cache_clear()


def test_parallel_tool_calls_run_concurrently_in_order():
    """Three tool calls in one model turn take ~1 slow call, not 3, and results keep call order."""
    config.MOCK_MODE = False
    tools_orig, chat_orig = tools.run_tool, agent.meta_client.chat_message

    def slow_tool(name, args):
        time.sleep(0.4)
        return {"tool_name": name, "n": args.get("n")}

    turn = {"i": 0}

    async def fake_chat(messages, use_open_model=False, **extra):
        turn["i"] += 1
        if turn["i"] == 1:
            calls = [{"id": f"c{i}", "function": {"name": "get_weather", "arguments": json.dumps({"n": i})}}
                     for i in range(3)]
            return {"role": "assistant", "content": None, "tool_calls": calls}
        return {"role": "assistant", "content": "done", "tool_calls": None}

    tools.run_tool, agent.meta_client.chat_message = slow_tool, fake_chat
    try:
        t0 = time.monotonic()
        out = asyncio.run(agent.run_agent("weather?", lang="en"))
        took = time.monotonic() - t0
    finally:
        tools.run_tool, agent.meta_client.chat_message = tools_orig, chat_orig
        config.MOCK_MODE = True
    assert took < 1.0, f"tool calls ran sequentially ({took:.2f}s)"
    assert [s["result"]["n"] for s in out["steps"]] == [0, 1, 2]
    assert out["answer"] == "done"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
