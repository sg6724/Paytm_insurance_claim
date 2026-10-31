"""The assistant remembers. One thread per claim (or per policy, or general), kept between visits.

The model sees the last MODEL_WINDOW messages plus a rolling summary of anything older, so a long history never
grows the prompt. The recap shown when the user comes back is AI-written; the "next step" under it is not: it comes
from the claim's own state, so what we tell the user to do next is always rules, never a guess.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from . import store

MODEL_WINDOW = 16   # messages sent to the model verbatim
SUMMARISE_EVERY = 8  # fold older messages into the summary in batches, not on every turn
MAX_STORED = 200
RETURN_GAP = timedelta(minutes=30)  # a gap this long counts as the user coming back


def thread_id(claim_id: str | None, policy_id: str | None) -> str:
    if claim_id:
        return f"thr_claim_{claim_id}"
    if policy_id:
        return f"thr_policy_{policy_id}"
    return "thr_general"


def load(tid: str) -> dict:
    return store.get("thread", tid) or {"id": tid, "messages": [], "summary": "", "summary_n": 0, "recap": None, "recap_n": -1, "recap_lang": None}


def save(t: dict) -> dict:
    extra = len(t["messages"]) - MAX_STORED
    if extra > 0:
        t["messages"] = t["messages"][extra:]
        t["summary_n"] = max(0, t.get("summary_n", 0) - extra)
        t["recap_n"] = -1
    return store.put("thread", t)


def append(t: dict, role: str, content: str, **extra) -> None:
    t["messages"].append({"role": role, "content": content, "at": store.now(), **{k: v for k, v in extra.items() if v}})


def for_model(m: dict) -> dict:
    """A stored message as the model sees it: no timestamp, and any screenshot text it carried."""
    content = m["content"]
    if m.get("attachment"):
        content += f"\n\nATTACHMENT (text read from the screenshot/document):\n{m['attachment']}"
    return {"role": m["role"], "content": content}


def history_for_model(t: dict, new_user: str) -> list[dict]:
    """Stored messages plus the message being asked now."""
    return [for_model(m) for m in t["messages"][-MODEL_WINDOW:]] + [{"role": "user", "content": new_user}]


def returning_since(t: dict, now: datetime | None = None) -> str | None:
    """When the user last talked to us, but only if that was long enough ago to be a new visit."""
    if not t["messages"]:
        return None
    last = t["messages"][-1]["at"]
    try:
        then = datetime.fromisoformat(last)
    except ValueError:
        return None
    now = now or datetime.now(then.tzinfo)
    return last if now - then >= RETURN_GAP else None


def pending_summary(t: dict) -> list[dict]:
    """Messages that have scrolled out of the model window and are not in the summary yet (empty until a full batch)."""
    older = t["messages"][: max(0, len(t["messages"]) - MODEL_WINDOW)]
    return older if len(older) - t.get("summary_n", 0) >= SUMMARISE_EVERY else []
