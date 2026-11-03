"""Email + password accounts: hashing, validation, lockout, endpoints (in-memory store), and the real PostgreSQL store when TEST_DATABASE_URL is set."""
import os, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["MOCK_MODE"] = "1"
os.environ.pop("DATABASE_URL", None)
os.environ["RATE_AGENT_PER_MIN"] = "1000"
from fastapi.testclient import TestClient
from app import accounts as a, auth
from app.main import app

c = TestClient(app)


def fresh(store=None):
    a._failures.clear()
    a.set_store(store or a.MemoryStore())


def test_hash_is_salted_and_checked():
    h1, h2 = a.hash_password("longpassword"), a.hash_password("longpassword")
    assert h1 != h2 and "longpassword" not in h1
    assert a.check_password("longpassword", h1) and not a.check_password("longpassw0rd", h1)
    assert not a.check_password("x", None) and not a.check_password("x", "garbage")


def test_register_validation():
    fresh()
    for bad in [("nope", "longpassword"), ("a@b", "longpassword"), ("a@b.com", "short"), ("a@b.com", "x" * 200)]:
        try: a.register(*bad, "n"); assert False, bad
        except ValueError: pass
    u = a.register(" Mixed@Case.COM ", "longpassword", "  \x00Ravi\n ")
    assert u["email"] == "mixed@case.com" and u["name"] == "Ravi"
    try: a.register("mixed@case.com", "longpassword", "x"); assert False
    except LookupError: pass


def test_login_and_lockout():
    fresh(); a.register("r@x.com", "longpassword", "R")
    assert a.login("R@x.com", "longpassword")["email"] == "r@x.com"
    for _ in range(5):
        try: a.login("r@x.com", "wrong-password"); assert False
        except PermissionError: pass
    try: a.login("r@x.com", "longpassword"); assert False, "locked even with the right password"
    except TimeoutError: pass
    assert a.login("r@x.com", "longpassword", now=time.time() + 700)["email"] == "r@x.com", "lock ends"


def test_google_links_by_verified_email():
    fresh(); u = a.register("g@x.com", "longpassword", "G")
    g = a.google_user({"sub": "S1", "email": "G@x.com", "name": "G Google"})
    assert g["id"] == u["id"] and a.store().by_google("S1")["id"] == u["id"]
    n = a.google_user({"sub": "S2", "email": "new@x.com", "name": "New"})
    assert n["password_hash"] is None and a.google_user({"sub": "S2", "email": "new@x.com", "name": "New"})["id"] == n["id"]


def test_endpoints():
    fresh()
    assert c.get("/api/auth/config").json()["accounts"] is True
    r = c.post("/api/auth/register", json={"email": "e@x.com", "password": "longpassword", "name": "Eswar"})
    assert r.status_code == 200 and r.json()["user"]["account"] and "password" not in r.text
    tok = r.json()["token"]
    assert c.post("/api/auth/register", json={"email": "e@x.com", "password": "longpassword"}).status_code == 409
    assert c.post("/api/auth/register", json={"email": "bad", "password": "longpassword"}).status_code == 400
    assert c.post("/api/auth/login", json={"email": "e@x.com", "password": "nope-nope"}).status_code == 401
    ok = c.post("/api/auth/login", json={"email": "e@x.com", "password": "longpassword"})
    assert ok.status_code == 200
    h = {"Authorization": "Bearer " + ok.json()["token"]}
    assert c.get("/api/auth/me", headers=h).json()["user"]["email"] == "e@x.com"
    assert c.delete("/api/auth/account", headers={"Authorization": "Bearer junk"}).status_code == 401
    assert c.delete("/api/auth/account", headers=h).json()["deleted"]
    assert c.get("/api/auth/me", headers=h).status_code == 401, "deleted account's token stops working"


def test_off_without_database():
    a._store = None; a._failures.clear()
    assert c.get("/api/auth/config").json()["accounts"] is False
    assert c.post("/api/auth/register", json={"email": "e@x.com", "password": "longpassword"}).status_code == 503
    assert c.post("/api/auth/login", json={"email": "e@x.com", "password": "longpassword"}).status_code == 503


def test_real_postgres():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        print("skip real postgres (TEST_DATABASE_URL not set)"); return
    s = a.PgStore(url); s.init(); s.init()
    with s._c() as cx: cx.execute("DELETE FROM users")
    fresh(s)
    u = a.register("pg@x.com", "longpassword", "PG")
    assert a.login("pg@x.com", "longpassword")["id"] == u["id"] and len(u["id"]) == 36
    try: a.register("PG@x.com", "longpassword", "dup"); assert False
    except LookupError: pass
    assert s.by_id("not-a-uuid") is None
    g = a.google_user({"sub": "G9", "email": "pg@x.com", "name": "x"})
    assert g["id"] == u["id"] and s.by_google("G9")["id"] == u["id"]
    assert s.delete(u["id"]) and s.by_email("pg@x.com") is None


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f(); print("ok", n)
