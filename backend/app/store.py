"""Tiny SQLite document store: one table, JSON bodies, keyed by (kind, id)."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .config import DB_PATH

_lock = threading.RLock()
_conn: sqlite3.Connection | None = None


def now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.execute("CREATE TABLE IF NOT EXISTS docs (kind TEXT, id TEXT, data TEXT, created TEXT, PRIMARY KEY (kind, id))")
        _conn.commit()
    return _conn


def put(kind: str, obj: dict) -> dict:
    obj.setdefault("created_at", now())
    obj["updated_at"] = now()
    with _lock:
        conn().execute("INSERT OR REPLACE INTO docs VALUES (?, ?, ?, ?)", (kind, obj["id"], json.dumps(obj, ensure_ascii=False), obj["created_at"]))
        conn().commit()
    return obj


def get(kind: str, id: str) -> dict | None:
    with _lock:  # one shared connection: reads must not overlap writes from other request threads
        row = conn().execute("SELECT data FROM docs WHERE kind=? AND id=?", (kind, id)).fetchone()
    return json.loads(row[0]) if row else None


def find(kind: str, **match) -> list[dict]:
    with _lock:
        rows = conn().execute("SELECT data FROM docs WHERE kind=? ORDER BY created DESC", (kind,)).fetchall()
    out = [json.loads(r[0]) for r in rows]
    return [o for o in out if all(o.get(k) == v for k, v in match.items())]


def delete(kind: str, id: str) -> None:
    with _lock:
        conn().execute("DELETE FROM docs WHERE kind=? AND id=?", (kind, id))
        conn().commit()


def wipe() -> None:
    with _lock:
        conn().execute("DELETE FROM docs")
        conn().commit()


def audit(actor: str, action: str, detail: str, ref: str | None = None, data: dict | None = None) -> dict:
    """Every AI action, consent and submission lands here ("What AI did with your data")."""
    return put("audit", {"id": new_id("aud"), "actor": actor, "action": action, "detail": detail, "ref": ref, "data": data or {}})
