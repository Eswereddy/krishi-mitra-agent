"""Optional sign-in with Google. Minimal on purpose: it tells the app who the farmer is, nothing more.

Design (kept consistent with the rest of the app): the server stores NO accounts and NO farmer data. Google proves the identity; the
server verifies Google's ID token (signature checked by Google's tokeninfo endpoint; audience, issuer, expiry and verified email checked
here) and hands back a signed, expiring session token that the phone keeps. The farm data itself stays on the phone, so signing in does not
sync it between devices. The app works without signing in (guest).

Needs GOOGLE_CLIENT_ID (a public OAuth Web client id, not a secret). SESSION_SECRET signs session tokens; if it is not set, a random one is
made at start-up and sessions end whenever the server restarts.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time

import httpx

TOKENINFO = "https://oauth2.googleapis.com/tokeninfo"
ISSUERS = ("accounts.google.com", "https://accounts.google.com")
SESSION_DAYS = 30
_RANDOM_SECRET = secrets.token_hex(32)


def client_id() -> str:
    return os.getenv("GOOGLE_CLIENT_ID", "").strip()


def _secret() -> bytes:
    return (os.getenv("SESSION_SECRET", "").strip() or _RANDOM_SECRET).encode()


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def issue(user: dict, now: float | None = None) -> str:
    body = _b64(json.dumps({"sub": user["sub"], "email": user["email"], "name": user["name"], "picture": user.get("picture", ""),
                            "exp": int((now or time.time()) + SESSION_DAYS * 86400)}, separators=(",", ":")).encode())
    return body + "." + _b64(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())


def read(token: str, now: float | None = None) -> dict | None:
    """The user inside a valid, unexpired session token, else None. Never raises."""
    try:
        body, sig = str(token or "").split(".")
        if not hmac.compare_digest(sig, _b64(hmac.new(_secret(), body.encode(), hashlib.sha256).digest())):
            return None
        d = json.loads(_unb64(body))
        return d if isinstance(d, dict) and d.get("exp", 0) > (now or time.time()) and d.get("sub") else None
    except Exception:
        return None


async def verify_google(credential: str) -> dict:
    """Check a Google ID token. Returns {sub, email, name, picture} or raises ValueError with a short reason."""
    cid = client_id()
    if not cid:
        raise ValueError("Google sign-in is not set up on this server")
    if not credential or len(credential) > 4096:
        raise ValueError("Missing sign-in credential")
    async with httpx.AsyncClient(timeout=8) as c:
        r = await c.get(TOKENINFO, params={"id_token": credential})
    if r.status_code != 200:
        raise ValueError("Google did not accept this sign-in")
    d = r.json()
    if d.get("aud") != cid:
        raise ValueError("This sign-in was issued for a different app")
    if d.get("iss") not in ISSUERS:
        raise ValueError("Unexpected token issuer")
    if int(d.get("exp", 0)) <= time.time():
        raise ValueError("Sign-in expired, please try again")
    if str(d.get("email_verified")).lower() != "true" or not d.get("email"):
        raise ValueError("Google email is not verified")
    return {"sub": str(d["sub"]), "email": str(d["email"]), "name": str(d.get("name") or d["email"].split("@")[0])[:80], "picture": str(d.get("picture") or "")[:300]}


def bearer(header: str) -> str:
    return header[7:].strip() if header and header.lower().startswith("bearer ") else ""
