"""Model-call telemetry: which Meta model handled a request, how long it took, and whether it failed.
Kept in memory only (a bounded ring per model); no prompts, answers, keys or farmer data are recorded. Exposed as an
aggregate at /api/status so a deployment can be monitored and judges can see which model really served calls.
"""
import contextvars
import functools
import time
from collections import defaultdict, deque

KEEP = 200
_calls: dict[str, deque] = defaultdict(lambda: deque(maxlen=KEEP))
_totals: dict[str, dict] = defaultdict(lambda: {"ok": 0, "error": 0})
served: contextvars.ContextVar = contextvars.ContextVar("km_served_by", default=None)


def record(name: str, ms: float, err: str | None = None) -> None:
    _calls[name].append((ms, err))
    _totals[name]["error" if err else "ok"] += 1


def timed(name: str, mark_served: bool = False):
    """Decorator for async model calls: records latency and the error TYPE (never the message) and re-raises."""
    def deco(fn):
        @functools.wraps(fn)
        async def inner(*a, **k):
            t0 = time.perf_counter()
            try:
                out = await fn(*a, **k)
            except Exception as e:
                record(name, (time.perf_counter() - t0) * 1000, type(e).__name__)
                raise
            record(name, (time.perf_counter() - t0) * 1000)
            if mark_served:
                served.set(name)
            return out
        return inner
    return deco


def summary() -> dict:
    out = {}
    for name, dq in _calls.items():
        ok_ms = sorted(ms for ms, e in dq if not e)
        errs = [e for _ms, e in dq if e]
        t = _totals[name]
        out[name] = {"calls": t["ok"] + t["error"], "ok": t["ok"], "errors": t["error"],
                     "median_ms": round(ok_ms[len(ok_ms) // 2]) if ok_ms else None,
                     "p95_ms": round(ok_ms[max(int(len(ok_ms) * .95) - 1, 0)]) if ok_ms else None,
                     "last_error_type": errs[-1] if errs else None}
    return out


def reset() -> None:
    _calls.clear()
    _totals.clear()
