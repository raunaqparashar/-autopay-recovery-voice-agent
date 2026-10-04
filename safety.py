"""Calling guardrails: only allowlisted numbers, do-not-call honoured, sane local hours."""
from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo


class NotCallable(Exception):
    pass


def allowlist() -> set[str]:
    return {n.strip() for n in os.getenv("ALLOWED_NUMBERS", "").split(",") if n.strip()}


def assert_callable(phone: str, customer: dict | None = None) -> None:
    if phone not in allowlist():
        raise NotCallable(f"{phone} is not in ALLOWED_NUMBERS; refusing to dial")
    if customer is None:
        return
    if customer.get("do_not_call"):
        raise NotCallable(f"{customer['id']} is flagged do-not-call")
    if os.getenv("IGNORE_CALL_HOURS") != "1":
        local = datetime.now(ZoneInfo(customer["timezone"]))
        if not 8 <= local.hour < 21:
            raise NotCallable(
                f"{customer['id']} local time is {local:%H:%M}; outside 08:00-21:00 (set IGNORE_CALL_HOURS=1 for demo)"
            )
