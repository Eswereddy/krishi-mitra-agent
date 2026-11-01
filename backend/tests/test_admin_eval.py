"""Admin live-eval: invisible without ADMIN_TOKEN, refuses mock mode, reports real rows only, shows failures honestly."""
import asyncio, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["MOCK_MODE"] = "1"
from fastapi.testclient import TestClient
from app import admin_eval, config
from app.main import app

c = TestClient(app)
os.environ.pop("ADMIN_TOKEN", None)
assert c.get("/api/admin/live-eval?token=x").status_code == 404, "must be hidden when ADMIN_TOKEN unset"
assert c.post("/api/admin/live-eval?token=").status_code == 404
os.environ["ADMIN_TOKEN"] = "secret"
assert c.get("/api/admin/live-eval?token=wrong").status_code == 404
assert c.get("/api/admin/live-eval?token=secret").json()["status"] == "idle"
assert c.post("/api/admin/live-eval?token=secret").status_code == 400, "mock mode must refuse"

rows = [{"q": "a", "tools": ["get_weather"], "ok_tool": True, "verified": True, "rewrites": 0, "secs": 2.0},
        {"q": "b", "tools": [], "error": "boom", "ok_tool": False, "verified": False, "rewrites": 1, "secs": 6.0}]
md = admin_eval.format_report(rows, "test")
assert "**1/2**" in md and "median **4.0s**" in md and "| b | boom | NO | NO | 1 |" in md

# a crash inside the run is reported as failed, not hidden
admin_eval.STATE.update(status="running", report=None, error=None)
sys.modules["run_eval"] = None  # makes `import run_eval` raise
asyncio.run(admin_eval._run())
assert admin_eval.STATE["status"] == "failed" and "Error" in admin_eval.STATE["error"] and admin_eval.STATE["report"] is None
print("test_admin_eval OK")
