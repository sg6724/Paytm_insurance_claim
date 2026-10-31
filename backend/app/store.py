"""Tiny document store: one table, JSON bodies, keyed by (user_id, kind, id).

Postgres (Neon) when DATABASE_URL is set, SQLite otherwise, so tests and local runs need no server.
Every read and write is scoped to the signed-in user at this layer, so a route cannot reach another user's
data even if it is handed that user's ids. Accounts and sessions live under SYSTEM.
"""

from __future__ import annotations

import contextvars
import json
import sqlite3
import ssl
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

from .config import DATABASE_URL, DB_PATH

SYSTEM = "_system"
_user = contextvars.ContextVar("user_id", default="local")
_lock = threading.RLock()
_conn = None


def set_user(user_id: str) -> None:
    _user.set(user_id)


def current_user() -> str:
    return _user.get()


def now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


SCHEMA = [
    "CREATE TABLE IF NOT EXISTS user_docs (user_id TEXT NOT NULL, kind TEXT NOT NULL, id TEXT NOT NULL, data TEXT NOT NULL, "
    "created TEXT NOT NULL, PRIMARY KEY (user_id, kind, id))",
    "CREATE INDEX IF NOT EXISTS user_docs_list ON user_docs (user_id, kind, created)",
]


def _connect():
    if DATABASE_URL:
        import pg8000.dbapi  # only needed where Postgres is used

        u = urlparse(DATABASE_URL)
        c = pg8000.dbapi.connect(user=unquote(u.username), password=unquote(u.password or ""), host=u.hostname, port=u.port or 5432,
                                 database=u.path.lstrip("/"), ssl_context=ssl.create_default_context())
        c.autocommit = True
    else:
        Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(DB_PATH, check_same_thread=False, isolation_level=None)
    cur = c.cursor()
    for sql in SCHEMA:
        cur.execute(sql)
    return c


def conn():
    global _conn
    if _conn is None:
        _conn = _connect()
    return _conn


def _run(sql: str, params: tuple = (), fetch: bool = False):
    """One shared connection. Neon closes idle ones, so a dropped connection is reopened and the statement retried once."""
    global _conn
    if DATABASE_URL:
        sql = sql.replace("?", "%s")
    with _lock:
        for attempt in (1, 2):
            try:
                cur = conn().cursor()
                cur.execute(sql, params)
                return cur.fetchall() if fetch else None
            except Exception:
                if not DATABASE_URL or attempt == 2:
                    raise
                try:
                    _conn.close()
                except Exception:
                    pass
                _conn = None


def put(kind: str, obj: dict, user: str | None = None) -> dict:
    obj.setdefault("created_at", now())
    obj["updated_at"] = now()
    _run("INSERT INTO user_docs (user_id, kind, id, data, created) VALUES (?, ?, ?, ?, ?) "
         "ON CONFLICT (user_id, kind, id) DO UPDATE SET data = excluded.data",
         (user or current_user(), kind, obj["id"], json.dumps(obj, ensure_ascii=False), obj["created_at"]))
    return obj


def get(kind: str, id: str, user: str | None = None) -> dict | None:
    rows = _run("SELECT data FROM user_docs WHERE user_id=? AND kind=? AND id=?", (user or current_user(), kind, id), fetch=True)
    return json.loads(rows[0][0]) if rows else None


def find(kind: str, **match) -> list[dict]:
    rows = _run("SELECT data FROM user_docs WHERE user_id=? AND kind=? ORDER BY created DESC", (current_user(), kind), fetch=True)
    out = [json.loads(r[0]) for r in rows]
    return [o for o in out if all(o.get(k) == v for k, v in match.items())]


def delete(kind: str, id: str, user: str | None = None) -> None:
    _run("DELETE FROM user_docs WHERE user_id=? AND kind=? AND id=?", (user or current_user(), kind, id))


def delete_sessions(user_id: str, keep: str | None = None) -> None:
    """Sign a user out everywhere, optionally except one session."""
    rows = _run("SELECT id, data FROM user_docs WHERE user_id=? AND kind='session'", (SYSTEM,), fetch=True)
    for sid, data in rows:
        if sid != keep and json.loads(data).get("user_id") == user_id:
            delete("session", sid, user=SYSTEM)


def wipe() -> None:
    """Everything belonging to the signed-in user. Their account stays."""
    _run("DELETE FROM user_docs WHERE user_id=?", (current_user(),))


def audit(actor: str, action: str, detail: str, ref: str | None = None, data: dict | None = None) -> dict:
    """Every AI action, consent and submission lands here ("What AI did with your data")."""
    return put("audit", {"id": new_id("aud"), "actor": actor, "action": action, "detail": detail, "ref": ref, "data": data or {}})
