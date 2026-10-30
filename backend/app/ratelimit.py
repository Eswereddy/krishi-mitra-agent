"""Small in-memory per-IP rate limiter for the expensive endpoints (model calls, TTS, transcription).

Protects the hackathon API credits when the public demo URL is shared. One process only, which is
enough for a single Render service. Limits come from env vars so they can be raised for the demo.
"""
import os
import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse

WINDOW_S = 60
# path prefix -> max requests per IP per minute
LIMITS = {
    "/api/agent": int(os.getenv("RATE_AGENT_PER_MIN", "12")),
    "/api/diagnose": int(os.getenv("RATE_AGENT_PER_MIN", "12")),
    "/api/brief": int(os.getenv("RATE_AGENT_PER_MIN", "12")),
    "/api/transcribe": int(os.getenv("RATE_VOICE_PER_MIN", "20")),
    "/api/tts": int(os.getenv("RATE_VOICE_PER_MIN", "20")),
    "/api/ask": int(os.getenv("RATE_AGENT_PER_MIN", "12")),
    "/api/alerts": int(os.getenv("RATE_AGENT_PER_MIN", "12")),
}
_hits: dict[tuple[str, str], deque] = defaultdict(deque)


# Number of trusted reverse proxies in front of the app (Render = 1). The client can write anything into the
# LEFT side of X-Forwarded-For to dodge the limit, but the proxy appends the real address on the RIGHT.
TRUSTED_PROXIES = int(os.getenv("TRUSTED_PROXIES", "1"))
_last_sweep = 0.0


def client_ip(request: Request) -> str:
    fwd = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
    if fwd and TRUSTED_PROXIES > 0:
        return fwd[max(0, len(fwd) - TRUSTED_PROXIES)]
    return request.client.host if request.client else "unknown"


def _sweep(now: float) -> None:
    """Drop idle clients so the table cannot grow forever on a long-running public demo."""
    global _last_sweep
    if now - _last_sweep < WINDOW_S:
        return
    _last_sweep = now
    for k in [k for k, q in _hits.items() if not q or now - q[-1] > WINDOW_S]:
        del _hits[k]


def check(ip: str, path: str, now: float | None = None) -> int | None:
    """Return None if allowed, else the number of seconds to wait."""
    now = time.monotonic() if now is None else now
    _sweep(now)
    for prefix, limit in LIMITS.items():
        if path.startswith(prefix):
            q = _hits[(ip, prefix)]
            while q and now - q[0] > WINDOW_S:
                q.popleft()
            if len(q) >= limit:
                return max(1, int(WINDOW_S - (now - q[0])))
            q.append(now)
            return None
    return None


async def middleware(request: Request, call_next):
    wait = check(client_ip(request), request.url.path)
    if wait is not None:
        return JSONResponse(
            status_code=429,
            content={"detail": f"Too many requests. Please wait {wait} seconds and try again."},
            headers={"Retry-After": str(wait)},
        )
    return await call_next(request)
