"""Optional Google sign-in: tokens are signed and expire, Google's answer is checked field by field, nothing is stored."""
import asyncio, os, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["MOCK_MODE"] = "1"
from fastapi.testclient import TestClient
from app import auth
from app.main import app

c = TestClient(app)
U = {"sub": "123", "email": "farmer@example.com", "name": "Farmer", "picture": ""}


def test_session_token_roundtrip_tamper_expiry():
    tok = auth.issue(U)
    assert auth.read(tok)["email"] == "farmer@example.com"
    body, sig = tok.split(".")
    assert auth.read(body + "." + sig[:-2] + "AA") is None, "bad signature"
    assert auth.read("x" + tok) is None and auth.read("") is None and auth.read(None) is None and auth.read("a.b.c") is None
    assert auth.read(auth.issue(U, now=time.time() - 40 * 86400)) is None, "expired"
    other = auth.issue({**U, "sub": "999"})
    assert auth.read(other.split(".")[0] + "." + sig) is None, "payload swapped under another signature"


class Resp:
    def __init__(self, code, data): self.status_code, self._d = code, data
    def json(self): return self._d


def with_google(code, data, fn):
    class Client:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url, params=None): return Resp(code, data)
    real = auth.httpx.AsyncClient
    auth.httpx.AsyncClient = Client
    os.environ["GOOGLE_CLIENT_ID"] = "cid.apps.googleusercontent.com"
    try:
        return fn()
    finally:
        auth.httpx.AsyncClient = real


GOOD = {"aud": "cid.apps.googleusercontent.com", "iss": "https://accounts.google.com", "exp": str(int(time.time()) + 600), "email_verified": "true", "email": "a@b.com", "sub": "7", "name": "Asha"}


def test_verify_google_checks_every_field():
    ok = with_google(200, GOOD, lambda: asyncio.run(auth.verify_google("tok")))
    assert ok["email"] == "a@b.com" and ok["name"] == "Asha"
    for bad, why in [({**GOOD, "aud": "other"}, "app"), ({**GOOD, "iss": "evil.com"}, "issuer"), ({**GOOD, "exp": "1"}, "expired"),
                     ({**GOOD, "email_verified": "false"}, "verified"), ({**{k: v for k, v in GOOD.items() if k != "email"}}, "verified")]:
        try:
            with_google(200, bad, lambda: asyncio.run(auth.verify_google("tok")))
            raise AssertionError("accepted " + why)
        except ValueError:
            pass
    try:
        with_google(400, {}, lambda: asyncio.run(auth.verify_google("tok")))
        raise AssertionError("accepted a rejected token")
    except ValueError:
        pass


def test_endpoints():
    os.environ.pop("GOOGLE_CLIENT_ID", None)
    assert c.get("/api/auth/config").json()["google_client_id"] is None
    assert c.post("/api/auth/google", json={"credential": "x"}).status_code == 401, "not configured"
    os.environ["GOOGLE_CLIENT_ID"] = "cid.apps.googleusercontent.com"
    assert c.get("/api/auth/config").json()["google_client_id"] == "cid.apps.googleusercontent.com"
    r = with_google(200, GOOD, lambda: c.post("/api/auth/google", json={"credential": "tok"}))
    assert r.status_code == 200 and r.json()["user"]["email"] == "a@b.com"
    tok = r.json()["token"]
    me = c.get("/api/auth/me", headers={"Authorization": "Bearer " + tok})
    assert me.status_code == 200 and me.json()["user"]["name"] == "Asha"
    assert c.get("/api/auth/me").status_code == 401 and c.get("/api/auth/me", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert with_google(200, {**GOOD, "aud": "x"}, lambda: c.post("/api/auth/google", json={"credential": "tok"})).status_code == 401
    assert c.post("/api/auth/google", json={}).status_code == 401
    os.environ.pop("GOOGLE_CLIENT_ID", None)


if __name__ == "__main__":
    for k, v in list(globals().items()):
        if k.startswith("test_"):
            v()
            print("ok", k)
