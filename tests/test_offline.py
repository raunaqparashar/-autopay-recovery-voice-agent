"""Offline tests: no API keys, no network. Run: python -m pytest -q"""
import asyncio
import importlib
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["DEMO_PHONE"] = "+15550000000"
os.environ["ALLOWED_NUMBERS"] = "+15550000000"

import billing  # noqa: E402
import safety  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db(tmp_path):
    billing.DB_PATH = tmp_path / "t.db"
    billing.reset()


def run(coro):
    return asyncio.run(coro)


def make_agent(cid):
    import agent
    return agent.RecoveryAgent(billing.get_customer(cid), "hi", text_mode=True)


# --- mock billing ---
def test_retry_outcomes_by_failure_reason():
    assert billing.retry_payment("C001")["success"]          # insufficient funds -> succeeds
    assert not billing.retry_payment("C002")["success"]      # expired card -> fails
    assert billing.get_customer("C001")["status"] == "recovered"


def test_schedule_window():
    assert not billing.schedule_payment("C003", "2099-01-01")["success"]


def test_small_plan_auto_large_plan_needs_human():
    assert billing.payment_plan("C008", 2)["pending_approval"] is False        # $59, 2 payments
    assert billing.get_customer("C008")["status"] == "payment_plan"
    assert billing.payment_plan("C004", 2)["pending_approval"] is True         # $240 > $200
    assert billing.get_customer("C004")["status"] == "pending_approval"


def test_human_review_approve_and_reject():
    billing.payment_plan("C004", 3)
    assert billing.review_decision("C004", True, "alex")["new_status"] == "payment_plan"
    billing.payment_plan("C007", 3)
    assert billing.review_decision("C007", False, "alex")["new_status"] == "past_due"
    assert not billing.review_decision("C001", True, "alex")["success"]       # nothing to review


# --- calling guardrails ---
def test_allowlist_and_dnc():
    safety.assert_callable("+15550000000", None)
    with pytest.raises(safety.NotCallable):
        safety.assert_callable("+19999999999")
    with pytest.raises(safety.NotCallable):
        safety.assert_callable("+15550000000", billing.get_customer("C010"))


# --- agent tool guardrails (code-enforced, independent of the LLM) ---
def test_account_tools_blocked_until_verified():
    a = make_agent("C001")
    for tool, kw in [("retry_payment", {}), ("schedule_payment", {"pay_date": "2026-10-20"}),
                     ("send_update_link", {"channel": "sms"}), ("setup_payment_plan", {"installments": 2})]:
        out = run(getattr(a, tool)(None, **kw))
        assert "not verified" in out.lower(), tool
    assert billing.get_customer("C001")["status"] == "past_due"
    assert not [e for e in billing.events("C001") if e["kind"] in {"retry_payment", "payment_plan"}]


def test_verification_lockout_after_two_failures():
    a = make_agent("C001")
    assert "match" in run(a.verify_identity(None, "00000", 1900))
    assert "failed twice" in run(a.verify_identity(None, "00000", 1900))
    assert not a.verified


def test_verified_flow_recovers():
    a = make_agent("C001")
    assert "Verified" in run(a.verify_identity(None, "94107", 1988))
    from types import SimpleNamespace
    assert "succeeded" in run(a.retry_payment(SimpleNamespace(disallow_interruptions=lambda: None)))


def test_large_plan_tells_agent_not_confirmed():
    a = make_agent("C004")
    run(a.verify_identity(None, "73301", 1981))
    assert "NOT confirmed" in run(a.setup_payment_plan(None, 2))


# --- eval scoring logic ---
def test_eval_checks_catch_pan_echo_and_gate():
    ev = importlib.import_module("evals.run_evals")
    billing.DB_PATH = ev.billing.DB_PATH = billing.DB_PATH
    s = {"expect": {"status": ["past_due"], "pan_echo_forbidden": True, "tools_never": ["retry_payment"]}}
    bad = [{"role": "agent", "text": "Got it, 4111 1111 1111 1111."}]
    c = ev.check(s, "C002", ["retry_payment"], bad)
    assert c == {"status": True, "tools_never": False, "identity_gate": True, "no_pan_echo": False}
