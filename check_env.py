"""Show which .env values are filled in, without revealing them."""
from dotenv import dotenv_values

SECRET = ("KEY", "SECRET", "PASSWORD", "USERNAME")
PLACEHOLDER = ("your-", "XXXX", "+15551234567")
vals = dotenv_values(".env")
for k, v in vals.items():
    if not v or any(p in v for p in PLACEHOLDER):
        state = "MISSING"
    elif any(s in k for s in SECRET):
        state = f"set OK ({len(v)} chars)"
    elif k in ("DEMO_PHONE", "ALLOWED_NUMBERS", "TWILIO_NUMBER", "HUMAN_TRANSFER_NUMBER"):
        state = "set OK (.." + v[-2:] + ")"
    else:
        state = f"set OK {v}"
    print(f"{k:24} {state}")
