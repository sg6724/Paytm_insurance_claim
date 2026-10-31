"""Email and password sign-in. Passwords are scrypt-hashed; sessions are random tokens stored only as a hash."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request

from . import mailer, store

SESSION_DAYS = 30
MAX_FAILS = 5
LOCK_MINUTES = 15
RESET_MINUTES = 15
RESET_TRIES = 5
RESET_GAP_SECONDS = 60
PUBLIC = {"/", "/health", "/languages", "/auth/signup", "/auth/login", "/auth/forgot-password", "/auth/reset-password"}
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


def _check_password(password: str) -> None:
    if len(password) < 8:
        raise HTTPException(422, "Use at least 8 characters for your password.")


def _set_password(a: dict, password: str) -> None:
    salt = secrets.token_bytes(16)
    a.update(salt=salt.hex(), hash=_hash(password, salt).hex(), fails=0, locked_until=None)
    store.put("account", a, user=store.SYSTEM)


def signup(email: str, password: str, name: str) -> dict:
    key = _key(email)
    if not EMAIL.match(key):
        raise HTTPException(422, "Enter a valid email address.")
    _check_password(password)
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


def _code_hash(email: str, code: str) -> str:
    return hashlib.sha256(f"{email}:{code}".encode()).hexdigest()


def forgot_password(email: str) -> None:
    """Emails a 6-digit code. Answers the same whether or not the account exists, so it can't reveal who has one."""
    if not mailer.available():
        raise HTTPException(503, "Password reset by email isn't available right now.")
    key = _key(email)
    a = store.get("account", key, user=store.SYSTEM)
    if not a:
        return
    old = store.get("reset", key, user=store.SYSTEM)
    if old and datetime.fromisoformat(old["sent"]) > _utcnow() - timedelta(seconds=RESET_GAP_SECONDS):
        return  # one email a minute, so nobody can flood an inbox
    code = f"{secrets.randbelow(1_000_000):06d}"
    store.put("reset", {"id": key, "code": _code_hash(key, code), "sent": _utcnow().isoformat(), "expires": (_utcnow() + timedelta(minutes=RESET_MINUTES)).isoformat(), "tries": 0}, user=store.SYSTEM)
    try:
        mailer.send(key, "Your Claimezy password reset code",
                    f"Your code is {code}. It works for {RESET_MINUTES} minutes.\n\nIf you did not ask for this, ignore this email. Your password has not changed.")
    except mailer.MailError as e:
        store.delete("reset", key, user=store.SYSTEM)
        raise HTTPException(503, "We couldn't send the email. Try again in a few minutes.") from e


def reset_password(email: str, code: str, password: str) -> None:
    _check_password(password)
    key = _key(email)
    wrong = HTTPException(400, "That code is wrong or has expired. Ask for a new one.")
    r = store.get("reset", key, user=store.SYSTEM)
    a = store.get("account", key, user=store.SYSTEM)
    if not r or not a or datetime.fromisoformat(r["expires"]) < _utcnow():
        raise wrong
    if not hmac.compare_digest(r["code"], _code_hash(key, code.strip())):
        r["tries"] += 1
        if r["tries"] >= RESET_TRIES:
            store.delete("reset", key, user=store.SYSTEM)
        else:
            store.put("reset", r, user=store.SYSTEM)
        raise wrong
    _set_password(a, password)
    store.delete("reset", key, user=store.SYSTEM)
    store.delete_sessions(a["user_id"])  # whoever had the old password is signed out


def change_password(email: str, current: str, new: str, token: str) -> None:
    _check_password(new)
    a = store.get("account", _key(email), user=store.SYSTEM)
    if not a or not hmac.compare_digest(_hash(current, bytes.fromhex(a["salt"])).hex(), a["hash"]):
        raise HTTPException(400, "Your current password is wrong.")
    _set_password(a, new)
    store.delete_sessions(a["user_id"], keep=_token_id(token))


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
