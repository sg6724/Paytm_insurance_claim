"""Email and password sign-in. Passwords are scrypt-hashed; sessions are random tokens stored only as a hash."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request

from . import store

SESSION_DAYS = 30
MAX_FAILS = 5
LOCK_MINUTES = 15
PUBLIC = {"/health", "/languages", "/auth/signup", "/auth/login"}
MEDIA = re.compile(r"^(/assistant/tts\.wav|/claims/[^/]+/form\.pdf)$")  # opened by a player or browser, which can't send a header
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _hash(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, maxmem=64 * 1024 * 1024)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _key(email: str) -> str:
    return email.strip().lower()


def _token_id(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_session(user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    store.put("session", {"id": _token_id(token), "user_id": user_id, "expires": (_utcnow() + timedelta(days=SESSION_DAYS)).isoformat()}, user=store.SYSTEM)
    return token


def signup(email: str, password: str, name: str) -> dict:
    key = _key(email)
    if not EMAIL.match(key):
        raise HTTPException(422, "Enter a valid email address.")
    if len(password) < 8:
        raise HTTPException(422, "Use at least 8 characters for your password.")
    if not name.strip():
        raise HTTPException(422, "Enter your name.")
    if store.get("account", key, user=store.SYSTEM):
        raise HTTPException(409, "An account with this email already exists. Please sign in.")
    salt = secrets.token_bytes(16)
    account = {"id": key, "user_id": store.new_id("usr"), "name": name.strip(), "salt": salt.hex(), "hash": _hash(password, salt).hex(), "fails": 0}
    return store.put("account", account, user=store.SYSTEM)


def login(email: str, password: str) -> dict:
    """The same message for a wrong password and an unknown email, so this can't be used to find out who has an account."""
    wrong = HTTPException(401, "Wrong email or password.")
    a = store.get("account", _key(email), user=store.SYSTEM)
    if not a:
        _hash(password, b"0" * 16)  # same work, so timing doesn't reveal it either
        raise wrong
    if a.get("locked_until") and datetime.fromisoformat(a["locked_until"]) > _utcnow():
        raise HTTPException(429, f"Too many wrong attempts. Try again in {LOCK_MINUTES} minutes.")
    if not hmac.compare_digest(_hash(password, bytes.fromhex(a["salt"])).hex(), a["hash"]):
        a["fails"] = a.get("fails", 0) + 1
        if a["fails"] >= MAX_FAILS:
            a.update(fails=0, locked_until=(_utcnow() + timedelta(minutes=LOCK_MINUTES)).isoformat())
        store.put("account", a, user=store.SYSTEM)
        raise wrong
    if a.get("fails") or a.get("locked_until"):
        a.update(fails=0, locked_until=None)
        store.put("account", a, user=store.SYSTEM)
    return a


def logout(token: str) -> None:
    store.delete("session", _token_id(token), user=store.SYSTEM)


def token_from(request: Request) -> str | None:
    head = request.headers.get("authorization", "")
    if head.lower().startswith("bearer "):
        return head[7:].strip()
    if MEDIA.match(request.url.path):
        return request.query_params.get("access_token")
    return None


async def require_user(request: Request) -> None:
    """Runs before every route and sets whose data the store may touch. Async so the value reaches the route's thread."""
    if request.url.path in PUBLIC or request.method == "OPTIONS":
        return
    token = token_from(request)
    session = store.get("session", _token_id(token), user=store.SYSTEM) if token else None
    if not session or datetime.fromisoformat(session["expires"]) < _utcnow():
        raise HTTPException(401, "Please sign in.")
    store.set_user(session["user_id"])
