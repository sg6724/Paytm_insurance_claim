"""Transactional email through Resend. Without RESEND_API_KEY nothing can be sent, and callers say so."""

from __future__ import annotations

import httpx

from . import config


class MailError(Exception):
    pass


def available() -> bool:
    return bool(config.RESEND_API_KEY)


def send(to: str, subject: str, text: str) -> None:
    if not available():
        raise MailError("Email is not set up")
    try:
        r = httpx.post("https://api.resend.com/emails", headers={"Authorization": f"Bearer {config.RESEND_API_KEY}"},
                       json={"from": config.MAIL_FROM, "to": [to], "subject": subject, "text": text}, timeout=15)
    except httpx.HTTPError as e:
        raise MailError(f"email network error: {e}") from e
    if r.status_code >= 400:
        raise MailError(f"email {r.status_code}: {r.text[:200]}")
