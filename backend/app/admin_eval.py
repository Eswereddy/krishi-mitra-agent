"""Run the live agent evaluation ON the deployed server and read the result from a phone browser.

Why: Render's free plan has no Shell, and the live numbers must be measured against the real model and real
networks. Off unless ADMIN_TOKEN is set (then every route answers 404). One run at a time; the run is a background
task because 28 live questions take longer than a request should.

    POST /api/admin/live-eval?token=...   start a run   (409 if one is already running)
    GET  /api/admin/live-eval?token=...   status + markdown report when done

The report only contains numbers computed from the run; nothing is invented. Costs real model credits.
"""
import asyncio
import hmac
import os
import statistics
import sys
import time
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from . import config

router = APIRouter()
STATE: dict = {"status": "idle", "started": None, "finished": None, "report": None, "error": None, "done": 0, "total": 0}


def _authorised(token: str) -> None:
    secret = os.getenv("ADMIN_TOKEN", "")
    if not secret or not hmac.compare_digest(token or "", secret):
        raise HTTPException(404, "Not found")          # 404, not 403: do not reveal the route exists


def format_report(rows: list[dict], where: str) -> str:
    n = len(rows)
    tool_ok, ver_ok = sum(r["ok_tool"] for r in rows), sum(r["verified"] for r in rows)
    secs = sorted(r["secs"] for r in rows)
    out = [f"Live agent run on the deployed server ({where}); mock mode: {config.MOCK_MODE}; model: {config.CHAT_MODEL}.", "",
           f"- Right tool called (tool selection): **{tool_ok}/{n}**",
           f"- Every figure verified, no India-only terms abroad: **{ver_ok}/{n}**",
           f"- Latency: median **{statistics.median(secs):.1f}s**, p95 {secs[max(int(n * .95) - 1, 0)]:.1f}s, slowest {secs[-1]:.1f}s", "",
           "| Question | Tools | Tool OK | Verified | Rewrites |", "|---|---|---|---|---|"]
    out += [f"| {r['q']} | {', '.join(r['tools']) or r.get('error', '-')} | {'yes' if r['ok_tool'] else 'NO'} | "
            f"{'yes' if r['verified'] else 'NO'} | {r['rewrites']} |" for r in rows]
    return "\n".join(out)


async def _run() -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "eval"))
    try:
        import run_eval
        STATE["total"] = len(run_eval.CASES)
        rows = []
        for c in run_eval.CASES:
            rows.append(await run_eval.run_case(*c))
            STATE["done"] = len(rows)
        STATE["report"] = format_report(rows, "Render, free plan, Oregon")
        STATE["status"] = "done"
    except Exception as e:                              # report the failure, never a made-up result
        STATE["status"], STATE["error"] = "failed", f"{type(e).__name__}: {str(e)[:300]}"
    STATE["finished"] = time.time()


@router.post("/api/admin/live-eval")
async def start(background: BackgroundTasks, token: str = Query("")):
    _authorised(token)
    if config.MOCK_MODE:
        raise HTTPException(400, "MOCK_MODE is on: a live evaluation would be meaningless")
    if STATE["status"] == "running":
        raise HTTPException(409, "A run is already in progress")
    STATE.update(status="running", started=time.time(), finished=None, report=None, error=None, done=0, total=0)
    background.add_task(_run)
    return {"status": "running"}


@router.get("/api/admin/live-eval")
def status(token: str = Query("")):
    _authorised(token)
    return STATE
