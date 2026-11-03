"""Email + password accounts in PostgreSQL (Render), next to the optional Google sign-in in auth.py.

What is stored, and nothing else: email, display name, a salted scrypt password hash (never the password), the Google subject id if the
user signed in with Google, and sign-up / last-login times. Farm data (profile, notes, documents, quiz history) is NOT stored here: it stays on
the phone. Passwords are checked in constant time; a wrong email and a wrong password give the same message; five failures for one email lock
it for ten minutes. Without DATABASE_URL accounts are switched off (guest and Google-only still work). There is no password reset yet because
the app sends no email.
"""
import base64
import hashlib
import hmac
import logging
import os
import re
import secrets
import time
from collections import defaultdict, deque

log = logging.getLogger("krishi.accounts")
EMAIL_RX = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,189}\.[^@\s.]{2,}$")
MIN_PW, MAX_PW, MAX_EMAIL, MAX_NAME = 8, 128, 254, 80
N, R, P = 2 ** 14, 8, 1
LOCK_AFTER, LOCK_WINDOW_S = 5, 600
SCHEMA = """CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  password_hash TEXT,
  google_sub TEXT UNIQUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_login TIMESTAMPTZ)"""


class Duplicate(Exception):
    pass


def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=N, r=R, p=P, dklen=32)
    return f"scrypt${N}${R}${P}${base64.b64encode(salt).decode()}${base64.b64encode(h).decode()}"


def check_password(pw: str, stored: str | None) -> bool:
    """Constant-time check. A missing hash (Google-only account, unknown email) still costs one scrypt so timing does not reveal it."""
    try:
        _, n, r, p, salt, h = (stored or "").split("$")
        want = base64.b64decode(h)
        got = hashlib.scrypt(pw.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=len(want))
        return hmac.compare_digest(got, want)
    except Exception:
        hashlib.scrypt(pw.encode(), salt=b"x" * 16, n=N, r=R, p=P, dklen=32)
        return False


class MemoryStore:
    """In-process store for tests (and nothing else)."""
    def __init__(self):
        self.rows: dict[str, dict] = {}

    def init(self): pass

    def by_email(self, email):
        return next((dict(u) for u in self.rows.values() if u["email"] == email), None)

    def by_id(self, uid): return dict(self.rows[uid]) if uid in self.rows else None

    def by_google(self, sub): return next((dict(u) for u in self.rows.values() if u.get("google_sub") == sub), None)

    def create(self, email, name, pw_hash=None, google_sub=None):
        if self.by_email(email) or (google_sub and self.by_google(google_sub)):
            raise Duplicate()
        uid = secrets.token_hex(8)
        self.rows[uid] = {"id": uid, "email": email, "name": name, "password_hash": pw_hash, "google_sub": google_sub}
        return dict(self.rows[uid])

    def link_google(self, uid, sub): self.rows[uid]["google_sub"] = sub

    def touch(self, uid): self.rows[uid]["last_login"] = time.time()

    def delete(self, uid): return self.rows.pop(uid, None) is not None


class PgStore:
    def __init__(self, url: str):
        self.url = url

    def _c(self):
        import psycopg
        from psycopg.rows import dict_row
        return psycopg.connect(self.url, connect_timeout=8, row_factory=dict_row)

    def init(self):
        with self._c() as c:
            c.execute(SCHEMA)

    @staticmethod
    def _u(row): return {**row, "id": str(row["id"])} if row else None

    def by_email(self, email):
        with self._c() as c:
            return self._u(c.execute("SELECT * FROM users WHERE email = %s", (email,)).fetchone())

    def by_id(self, uid):
        try:
            with self._c() as c:
                return self._u(c.execute("SELECT * FROM users WHERE id = %s::uuid", (uid,)).fetchone())
        except Exception:
            return None                                           # a token whose sub is not a uuid (Google-only session)

    def by_google(self, sub):
        with self._c() as c:
            return self._u(c.execute("SELECT * FROM users WHERE google_sub = %s", (sub,)).fetchone())

    def create(self, email, name, pw_hash=None, google_sub=None):
        import psycopg
        try:
            with self._c() as c:
                return self._u(c.execute("INSERT INTO users (email, name, password_hash, google_sub) VALUES (%s, %s, %s, %s) RETURNING *", (email, name, pw_hash, google_sub)).fetchone())
        except psycopg.errors.UniqueViolation:
            raise Duplicate()

    def link_google(self, uid, sub):
        with self._c() as c:
            c.execute("UPDATE users SET google_sub = %s WHERE id = %s::uuid", (sub, uid))

    def touch(self, uid):
        with self._c() as c:
            c.execute("UPDATE users SET last_login = now() WHERE id = %s::uuid", (uid,))

    def delete(self, uid):
        with self._c() as c:
            return c.execute("DELETE FROM users WHERE id = %s::uuid", (uid,)).rowcount > 0


_store = None
_failures: dict[str, deque] = defaultdict(deque)


def set_store(s) -> None:
    global _store
    _store = s


def enabled() -> bool:
    return _store is not None or bool(os.getenv("DATABASE_URL", "").strip())


def store():
    global _store
    if _store is None:
        url = os.getenv("DATABASE_URL", "").strip()
        if not url:
            raise RuntimeError("accounts are not set up")
        _store = PgStore(url)
        _store.init()
    return _store


def startup_check() -> None:
    """Create the table at start-up and say in the log whether it worked (never stops the server from starting)."""
    if not os.getenv("DATABASE_URL", "").strip():
        log.info("accounts: DATABASE_URL not set, email accounts are off")
        return
    try:
        store()
        log.info("accounts: users table ready")
    except Exception as e:
        log.error("accounts: database not reachable (%s)", type(e).__name__)


def clean_email(raw) -> str | None:
    e = str(raw or "").strip().lower()
    return e if len(e) <= MAX_EMAIL and EMAIL_RX.match(e) else None


def _locked(email: str, now: float) -> bool:
    q = _failures[email]
    while q and now - q[0] > LOCK_WINDOW_S:
        q.popleft()
    return len(q) >= LOCK_AFTER


def register(email, password, name) -> dict:
    e = clean_email(email)
    if not e:
        raise ValueError("Enter a valid email")
    pw = str(password or "")
    if not MIN_PW <= len(pw) <= MAX_PW:
        raise ValueError(f"Password must be {MIN_PW} to {MAX_PW} characters")
    nm = re.sub(r"[\x00-\x1f\x7f]+", " ", str(name or "")).strip()[:MAX_NAME] or e.split("@")[0]
    try:
        return store().create(e, nm, hash_password(pw))
    except Duplicate:
        raise LookupError("This email already has an account. Sign in instead.")


def login(email, password, now: float | None = None) -> dict:
    now = now or time.time()
    e = clean_email(email)
    if not e or not password:
        raise PermissionError("Email or password is wrong")
    if _locked(e, now):
        raise TimeoutError("Too many wrong tries. Wait 10 minutes and try again.")
    u = store().by_email(e)
    ok = check_password(str(password)[:MAX_PW], u.get("password_hash") if u else None)
    if not (u and ok):
        _failures[e].append(now)
        raise PermissionError("Email or password is wrong")
    _failures.pop(e, None)
    store().touch(u["id"])
    return u


def google_user(g: dict) -> dict:
    """Find or create the account for a verified Google identity (linked by verified email)."""
    s = store()
    u = s.by_google(g["sub"]) or s.by_email(g["email"].lower())
    if u:
        if not u.get("google_sub"):
            s.link_google(u["id"], g["sub"])
    else:
        u = s.create(g["email"].lower(), g["name"], None, g["sub"])
    s.touch(u["id"])
    return u
