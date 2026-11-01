"""The offline evaluation suite v2 passes (run in its own process because it stubs network functions).
Run from backend/: python tests/test_eval_v2.py"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_suite_all_pass():
    r = subprocess.run([sys.executable, str(ROOT / "eval" / "suite_v2.py")], capture_output=True, text=True, cwd=ROOT, timeout=300)
    assert r.returncode == 0, r.stderr[-800:]
    assert "FAIL:" not in r.stdout and " checks passed" in r.stdout


def test_crashing_tool_does_not_crash_agent():
    sys.path.insert(0, str(ROOT))
    from app import tools
    tools.TOOL_FUNCS["boom"] = lambda **k: 1 / 0
    assert "ZeroDivisionError" in tools.run_tool("boom", {})["error"]
    del tools.TOOL_FUNCS["boom"]


if __name__ == "__main__":
    test_suite_all_pass()
    test_crashing_tool_does_not_crash_agent()
    print("ok")
