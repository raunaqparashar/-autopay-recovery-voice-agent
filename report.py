"""Print recovery results: per-customer status, recovered dollars, and the event log."""
from __future__ import annotations

import argparse

import billing

p = argparse.ArgumentParser()
p.add_argument("--events", action="store_true", help="also print the full event log")
a = p.parse_args()

custs = billing.list_customers()
print(f"{'ID':5} {'Name':16} {'Due':>8}  {'Reason':19} Status")
print("-" * 66)
for c in custs:
    print(f"{c['id']:5} {c['name']:16} {c['amount_due']:>8.2f}  {c['failure_reason']:19} {c['status']}")

done = {"recovered"}
committed = {"recovered", "promise_to_pay", "payment_plan", "link_sent"}
rec = sum(c["amount_due"] for c in custs if c["status"] in done)
com = sum(c["amount_due"] for c in custs if c["status"] in committed)
total = sum(c["amount_due"] for c in custs)
print("-" * 66)
print(f"Recovered now: ${rec:.2f}   Committed (incl. scheduled/plan/link): ${com:.2f}   Total past-due: ${total:.2f}")

import json  # noqa: E402

ev = billing.events()
called = {e["customer_id"] for e in ev if e["kind"] in ("dial", "call_end")}
connected = {e["customer_id"] for e in ev if e["kind"] == "call_end"}
by_status = {c["id"]: c["status"] for c in custs}
human = {"escalated", "callback", "pending_approval", "resolved_by_human"}
resolved_by_bot = [cid for cid in connected if by_status[cid] in committed]
escalated = [cid for cid in connected if by_status[cid] in human]
ends = [json.loads(e["detail"]) for e in ev if e["kind"] == "call_end"]
lat: dict[str, list[float]] = {}
for d in ends:
    for k, v in d.get("avg_latency_s", {}).items():
        lat.setdefault(k, []).append(v)
qa = [json.loads(e["detail"])["verdict"] for e in ev if e["kind"] == "qa_label"]
reviews = [e for e in ev if e["kind"] == "human_review"]


def pct(n: int, d: int) -> str:
    return f"{n / d:.0%}" if d else "n/a"


print()
print("KPIs (live calls)")
print(f"  calls placed {len(called)} | connected {len(connected)}")
print(f"  recovery rate (committed / connected)   {pct(len(resolved_by_bot), len(connected))}")
print(f"  containment (no human needed)           {pct(len(connected) - len(escalated), len(connected))}")
print(f"  escalation / approval rate              {pct(len(escalated), len(connected))}")
if ends:
    print(f"  avg call length                         {sum(d['duration_s'] for d in ends) / len(ends):.0f}s")
for k, v in lat.items():
    print(f"  avg {k:35} {sum(v) / len(v):.2f}s")
print(f"  human reviews {len(reviews)} | QA labels {len(qa)} (pass {pct(qa.count('pass'), len(qa))})")

if a.events:
    print()
    for e in billing.events():
        print(f"{e['ts']}  {e['customer_id']}  {e['kind']:18} {e['detail']}")
