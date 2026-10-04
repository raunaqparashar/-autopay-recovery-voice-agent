"""Create the LiveKit outbound SIP trunk from the Twilio values in .env and save its ID back to .env.
Prints only the trunk ID, never credentials."""
import asyncio
import re
from pathlib import Path

from dotenv import load_dotenv
import os
from livekit import api

ENV = Path(".env")
load_dotenv(ENV)
need = ["LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET", "TWILIO_TERMINATION_URI",
        "TWILIO_NUMBER", "TWILIO_SIP_USERNAME", "TWILIO_SIP_PASSWORD"]
missing = [k for k in need if not os.getenv(k) or "your-" in os.getenv(k) or "XXXX" in os.getenv(k)]
if missing:
    raise SystemExit(f"Fill these in .env first: {', '.join(missing)}")


async def main():
    lk = api.LiveKitAPI()
    try:
        trunk = await lk.sip.create_outbound_trunk(api.CreateSIPOutboundTrunkRequest(trunk=api.SIPOutboundTrunkInfo(
            name="twilio-trial-autopay",
            address=os.environ["TWILIO_TERMINATION_URI"].removeprefix("sip:"),
            numbers=[os.environ["TWILIO_NUMBER"]],
            auth_username=os.environ["TWILIO_SIP_USERNAME"],
            auth_password=os.environ["TWILIO_SIP_PASSWORD"],
        )))
    finally:
        await lk.aclose()
    tid = trunk.sip_trunk_id
    text = ENV.read_text()
    text = re.sub(r"^SIP_OUTBOUND_TRUNK_ID=.*$", f"SIP_OUTBOUND_TRUNK_ID={tid}", text, flags=re.M)
    ENV.write_text(text)
    print(f"Created LiveKit outbound trunk {tid} and saved it to .env")


asyncio.run(main())
