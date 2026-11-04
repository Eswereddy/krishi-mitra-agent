"""Request hardening: security headers, request-size caps, and a privacy-safe access log.
The log records method, path, status and milliseconds only: never bodies, query strings, headers, IPs or farmer data.
"""
import logging
import time

from fastapi import Request
from fastapi.responses import JSONResponse

log = logging.getLogger("krishi.access")
MAX_JSON_BYTES = 1 * 1024 * 1024
MAX_UPLOAD_BYTES = 12 * 1024 * 1024
LARGE_JSON_PATHS = ("/api/claim/evidence",)          # carries a few small embedded photos
LARGE_JSON_BYTES = 2 * 1024 * 1024
UPLOAD_PATHS = ("/api/transcribe", "/api/asr", "/api/diagnose", "/api/leaf-scan", "/api/whatsapp", "/api/research/ingest", "/api/guardian")
HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(self), microphone=(self), geolocation=(self), payment=()",
}


def too_big(path: str, length: str | None) -> bool:
    try:
        n = int(length) if length is not None else 0
    except ValueError:
        return True
    return n > (MAX_UPLOAD_BYTES if path.startswith(UPLOAD_PATHS) else LARGE_JSON_BYTES if path in LARGE_JSON_PATHS else MAX_JSON_BYTES)


async def middleware(request: Request, call_next):
    t0 = time.perf_counter()
    if request.method in ("POST", "PUT", "PATCH") and too_big(request.url.path, request.headers.get("content-length")):
        resp = JSONResponse(status_code=413, content={"detail": "Request too large"})
    else:
        try:
            resp = await call_next(request)
        except Exception as e:                       # logged without the message (it could contain user text)
            log.error("%s %s 500 %s", request.method, request.url.path, type(e).__name__)
            raise
    for k, v in HEADERS.items():
        resp.headers.setdefault(k, v)
    if request.url.path.startswith("/api"):
        log.info("%s %s %s %.0fms", request.method, request.url.path, resp.status_code, (time.perf_counter() - t0) * 1000)
    return resp


SIGNATURES = (b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n")


def is_real_image(data: bytes) -> bool:
    """Trust the bytes, not the Content-Type header: JPEG, PNG or WebP only."""
    return data.startswith(SIGNATURES) or (data[:4] == b"RIFF" and data[8:12] == b"WEBP")
