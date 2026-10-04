"""Human-in-the-loop review for supervisors.

  python review.py                         list items waiting for a human (pending plans, escalations, callbacks)
  python review.py approve C004 --by alex  approve a pending plan / close an escalation
  python review.py reject  C004 --by alex --note "needs hardship form"
  python review.py sample 3 --by alex      QA: label random finished calls pass/fail (interactive)
  python review.py agreement               compare human QA labels with the latest LLM-judge eval run
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import billing

QUEUE = {"pending_approval", "escalated", "callback"}
TRANSCRIPTS = billing.ROOT / "data" / "transcripts"


def transcript_lines(cid: str, limit: int | None = None) -> list[str]:
    files = sorted(TRANSCRIPTS.glob(f"{cid}-*.json"))
    if not files:
        return ["(no transcript)"]
    items = json.loads(files[-1].read_text()).get("items", [])
    lines = []
    for it in items:
        if it.get("type") == "message" and it.get("role") in ("user", "assistant"):
            text = " ".join(c for c in it.get("content", []) if isinstance(c, str))
            lines.append(f"{'CUSTOMER' if it['role'] == 'user' else 'AGENT':8} {text}")
        elif it.get("type") == "function_call":
            lines.append(f"{'TOOL':8} {it.get('name')}({it.get('arguments')})")
    return lines[-limit:] if limit else lines


def show_queue() -> None:
    pending = [c for c in billing.list_customers() if c["status"] in QUEUE]
    if not pending:
        print("Review queue is empty.")
        return
    for c in pending:
        last = [e for e in billing.events(c["id"]) if e["kind"] in ("payment_plan", "outcome")][-1:]
        print(f"\n== {c['id']} {c['name']}  ${c['amount_due']:.2f}  status={c['status']}")
        for e in last:
            print(f"   last: {e['kind']} {e['detail']}")
        for line in transcript_lines(c["id"], limit=6):
            print("   " + line)


def sample(n: int, by: str) -> None:
    done = [c for c in billing.list_customers()
            if any(e["kind"] == "call_end" for e in billing.events(c["id"]))]
    for c in random.sample(done, min(n, len(done))):
        print(f"\n== {c['id']} {c['name']}  final status={c['status']}")
        print("\n".join("   " + l for l in transcript_lines(c["id"])))
        verdict = ""
        while verdict not in ("pass", "fail"):
            verdict = input("verdict [pass/fail]: ").strip().lower()
        note = input("note (optional): ").strip()
        billing.qa_label(c["id"], verdict, by, note)
    if not done:
        print("No completed calls yet.")


def agreement() -> None:
    """Human QA labels on eval transcripts vs. the judge (task_success >= 4 counts as judge 'pass')."""
    runs = sorted((billing.ROOT / "evals" / "results").glob("*.json"))
    labels = billing.ROOT / "evals" / "human_labels.json"
    if not runs or not labels.exists():
        print("Need an eval run in evals/results/ and evals/human_labels.json "
              '({"scenario_id": "pass"|"fail", ...}).')
        return
    judged = {r["scenario"]: r for r in json.loads(runs[-1].read_text())["results"]}
    human = json.loads(labels.read_text())
    pairs = [(human[s], "pass" if judged[s]["judge"].get("task_success", 0) >= 4 and judged[s]["passed"] else "fail")
             for s in human if s in judged]
    agree = sum(h == j for h, j in pairs)
    print(f"Human vs automated verdict agreement: {agree}/{len(pairs)} ({agree / len(pairs):.0%}) on {runs[-1].name}")
    for s in human:
        if s in judged:
            j = "pass" if judged[s]["judge"].get("task_success", 0) >= 4 and judged[s]["passed"] else "fail"
            print(f"  {s:30} human={human[s]:4}  auto={j}{'' if human[s] == j else '   <-- disagree'}")


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd")
    for name in ("approve", "reject"):
        sp = sub.add_parser(name)
        sp.add_argument("customer")
        sp.add_argument("--by", required=True)
        sp.add_argument("--note", default="")
    sp = sub.add_parser("sample")
    sp.add_argument("n", type=int)
    sp.add_argument("--by", required=True)
    sub.add_parser("agreement")
    a = p.parse_args()

    if a.cmd in ("approve", "reject"):
        print(billing.review_decision(a.customer, a.cmd == "approve", a.by, a.note))
    elif a.cmd == "sample":
        sample(a.n, a.by)
    elif a.cmd == "agreement":
        agreement()
    else:
        show_queue()


if __name__ == "__main__":
    main()
