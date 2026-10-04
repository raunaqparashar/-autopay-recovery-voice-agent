"""Mock billing system backed by SQLite. Fictional data only."""
from __future__ import annotations

import json
import os
import random
import sqlite3
import string
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).parent
DB_PATH = ROOT / "data" / "billing.db"
SEED_PATH = ROOT / "data" / "customers.json"

# Simulated outcome of retrying the same card, keyed by original failure reason.
RETRY_SUCCEEDS = {
    "insufficient_funds": True,  # assume the customer says funds are now available
    "processing_error": True,
    "bank_declined": False,
    "card_expired": False,
    "card_lost_stolen": False,
}


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def reset() -> None:
    """(Re)create the DB from customers.json, substituting DEMO_PHONE."""
    phone = os.environ.get("DEMO_PHONE", "")
    rows = json.loads(SEED_PATH.read_text().replace("${DEMO_PHONE}", phone))
    with _conn() as c:
        c.executescript(
            """
            DROP TABLE IF EXISTS customers; DROP TABLE IF EXISTS events;
            CREATE TABLE customers (id TEXT PRIMARY KEY, data TEXT, status TEXT DEFAULT 'past_due');
            CREATE TABLE events (ts TEXT, customer_id TEXT, kind TEXT, detail TEXT);
            """
        )
        c.executemany(
            "INSERT INTO customers (id, data) VALUES (?, ?)",
            [(r["id"], json.dumps(r)) for r in rows],
        )


def get_customer(cid: str) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT data, status FROM customers WHERE id = ?", (cid,)).fetchone()
    if not row:
        return None
    return {**json.loads(row["data"]), "status": row["status"]}


def list_customers() -> list[dict]:
    with _conn() as c:
        ids = [r["id"] for r in c.execute("SELECT id FROM customers ORDER BY id")]
    return [get_customer(i) for i in ids]


def log(cid: str, kind: str, detail: dict | str = "") -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO events VALUES (?, ?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(timespec="seconds"), cid, kind,
             detail if isinstance(detail, str) else json.dumps(detail)),
        )


def _set_status(cid: str, status: str) -> None:
    with _conn() as c:
        c.execute("UPDATE customers SET status = ? WHERE id = ?", (status, cid))


def retry_payment(cid: str) -> dict:
    cust = get_customer(cid)
    ok = RETRY_SUCCEEDS.get(cust["failure_reason"], False)
    if ok:
        conf = "PAY-" + "".join(random.choices(string.digits, k=6))
        _set_status(cid, "recovered")
        result = {"success": True, "confirmation": conf, "amount": cust["amount_due"]}
    else:
        result = {"success": False, "reason": cust["failure_reason"]}
    log(cid, "retry_payment", result)
    return result


def schedule_payment(cid: str, pay_date: str) -> dict:
    cust = get_customer(cid)
    d = date.fromisoformat(pay_date)
    latest = date.fromisoformat(cust["failed_on"]) + timedelta(days=30)
    if d < date.today() or d > latest:
        result = {"success": False, "reason": f"date must be between today and {latest.isoformat()}"}
    else:
        _set_status(cid, "promise_to_pay")
        result = {"success": True, "scheduled_for": d.isoformat(), "amount": cust["amount_due"]}
    log(cid, "schedule_payment", result)
    return result


def send_update_link(cid: str, channel: str) -> dict:
    # Mock: a real system would text/email a hosted, PCI-compliant card form.
    link = f"https://pay.example.invalid/u/{cid.lower()}-{random.randint(1000, 9999)}"
    _set_status(cid, "link_sent")
    result = {"success": True, "channel": channel, "link": link}
    log(cid, "send_update_link", result)
    return result


APPROVAL_AMOUNT = 200.00  # plans above this, or 3-installment plans, need a human supervisor


def needs_approval(cust: dict, installments: int) -> bool:
    return cust["amount_due"] > APPROVAL_AMOUNT or installments == 3


def payment_plan(cid: str, installments: int) -> dict:
    cust = get_customer(cid)
    if installments not in (2, 3):
        result = {"success": False, "reason": "plans are 2 or 3 installments"}
    else:
        each = round(cust["amount_due"] / installments, 2)
        pending = needs_approval(cust, installments)
        _set_status(cid, "pending_approval" if pending else "payment_plan")
        result = {"success": True, "installments": installments, "each": each, "pending_approval": pending}
    log(cid, "payment_plan", result)
    return result


def review_decision(cid: str, approved: bool, reviewer: str, note: str = "") -> dict:
    """Supervisor approves/rejects a pending plan or closes an escalation."""
    cust = get_customer(cid)
    if cust["status"] == "pending_approval":
        new = "payment_plan" if approved else "past_due"
    elif cust["status"] in ("escalated", "callback"):
        new = "resolved_by_human" if approved else cust["status"]
    else:
        return {"success": False, "reason": f"nothing to review (status={cust['status']})"}
    _set_status(cid, new)
    result = {"success": True, "approved": approved, "reviewer": reviewer, "note": note, "new_status": new}
    log(cid, "human_review", result)
    return result


def qa_label(cid: str, verdict: str, reviewer: str, note: str = "") -> None:
    log(cid, "qa_label", {"verdict": verdict, "reviewer": reviewer, "note": note})


def set_outcome(cid: str, outcome: str, notes: str = "") -> None:
    if outcome in {"callback", "escalated", "refused", "wrong_party", "no_answer", "voicemail",
                   "do_not_call", "verification_failed"}:
        cur = get_customer(cid)["status"]
        if cur == "past_due":
            _set_status(cid, outcome)
    log(cid, "outcome", {"outcome": outcome, "notes": notes})


def events(cid: str | None = None) -> list[dict]:
    q, args = "SELECT * FROM events", ()
    if cid:
        q, args = q + " WHERE customer_id = ?", (cid,)
    with _conn() as c:
        return [dict(r) for r in c.execute(q + " ORDER BY ts", args)]
