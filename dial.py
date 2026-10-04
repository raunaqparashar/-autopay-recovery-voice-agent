"""Dispatch outbound recovery calls.

  python dial.py --reset              re-seed the mock DB
  python dial.py --customer C003      call one customer
  python dial.py --all                call every eligible past-due customer, one at a time
  python dial.py --all --dry-run      show who would be called and why/why not
"""
from __future__ import annotations

import argparse
import asyncio
import json
import uuid

from dotenv import load_dotenv
from livekit import api

load_dotenv()

import billing  # noqa: E402
from safety import NotCallable, assert_callable  # noqa: E402

AGENT_NAME = "autopay-recovery"


async def dispatch(lk: api.LiveKitAPI, cust: dict) -> str:
    room = f"autopay-{cust['id']}-{uuid.uuid4().hex[:6]}"
    await lk.agent_dispatch.create_dispatch(
        api.CreateAgentDispatchRequest(
            agent_name=AGENT_NAME,
            room=room,
            metadata=json.dumps({"customer_id": cust["id"], "phone": cust["phone"]}),
        )
    )
    return room


async def wait_until_done(cid: str, timeout: int = 300) -> None:
    for _ in range(timeout // 3):
        await asyncio.sleep(3)
        if any(e["kind"] == "outcome" for e in billing.events(cid)):
            return


async def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--customer")
    p.add_argument("--all", action="store_true")
    p.add_argument("--reset", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()

    if a.reset or not billing.DB_PATH.exists():
        billing.reset()
        print("Mock DB seeded with 10 fictional customers.")
        if a.reset and not (a.customer or a.all):
            return

    targets = [billing.get_customer(a.customer)] if a.customer else billing.list_customers() if a.all else []
    if not targets or targets == [None]:
        p.error("pass --customer <ID> or --all")

    lk = api.LiveKitAPI()
    try:
        for c in targets:
            if c["status"] != "past_due":
                print(f"skip {c['id']}: status={c['status']}")
                continue
            try:
                assert_callable(c["phone"], c)
            except NotCallable as e:
                print(f"skip {c['id']}: {e}")
                billing.log(c["id"], "skipped", str(e))
                continue
            if a.dry_run:
                print(f"would call {c['id']} {c['name']} (${c['amount_due']:.2f}, {c['failure_reason']})")
                continue
            room = await dispatch(lk, c)
            print(f"calling {c['id']} {c['name']} -> room {room}")
            if a.all:
                await wait_until_done(c["id"])
    finally:
        await lk.aclose()


if __name__ == "__main__":
    asyncio.run(main())
