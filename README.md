# Autopay Recovery Voice Agent (prototype)

An outbound AI voice agent ("Ava") that calls customers whose autopay failed. It verifies their identity, explains why the payment failed and tries to recover it. It works with **10 fictional customer records** and a **mock billing system** (SQLite). Every record dials **your own number**, which is enforced by an allowlist.

```
dial.py ──dispatch──▶ LiveKit Cloud ──▶ agent.py worker ──SIP──▶ Twilio trial ──▶ your phone
                                         │  Deepgram STT · Groq gpt-oss-120b · Cartesia TTS
                                         └─ tools ─▶ billing.py (SQLite) ◀── report.py
```

## Call flow
1. AI disclosure and recording notice, then confirm it's the right person. A wrong person gets no account details.
2. Identity check: billing ZIP + birth year, with at most 2 attempts.
3. Explain the failure: insufficient funds, expired card, decline, lost card or processing error.
4. Resolve with one of: **retry now** · **schedule a date (≤30 days)** · **secure card-update link** (SMS/email, mocked) · **2–3 installment plan**.
5. Read back the confirmation, log the outcome and hang up.
6. Edge cases:
   - Voicemail gets a message with no account details.
   - Asking for a human, hardship, a dispute or a lawyer triggers a transfer or callback.
   - Asking not to be called again records do-not-call.
   - Card numbers are never collected by voice.

## Guardrails
- `ALLOWED_NUMBERS`: the agent and dialer refuse any other number.
- `do_not_call` flag: C010 is set as an example and is always skipped.
- Calls are only placed between 08:00 and 21:00 in the customer's local time. For a demo, set `IGNORE_CALL_HOURS=1` to skip this check.
- Account tools refuse to run until identity is verified. This is enforced in code, not just in the prompt.

## Setup (all free tiers)
1. **Python 3.11+**
   ```
   py -3.11 -m venv .venv && .venv\Scripts\pip install -r requirements.txt
   copy .env.example .env      # then fill it in
   ```
2. **Keys:** create the following accounts and put the keys in `.env`:
   - LiveKit Cloud (cloud.livekit.io)
   - Deepgram ($200 free credit)
   - Cartesia (free tier)
   - Groq (free tier)
3. **Phone line (Twilio trial):**
   1. Sign up and get the free trial number. **Verify your own mobile** under *Verified Caller IDs*; trial accounts can only call verified numbers.
   2. Elastic SIP Trunking → create a trunk:
      - Termination SIP URI: e.g. `autopay-demo.pstn.twilio.com`
      - Credential list: username/password
      - Assign your Twilio number to the trunk.
   3. Create the LiveKit outbound trunk. Use the LiveKit CLI `lk`, or Telephony → SIP trunks in the dashboard:
      ```
      lk sip outbound create outbound-trunk.json
      ```
      ```json
      { "trunk": { "name": "twilio-trial", "address": "autopay-demo.pstn.twilio.com",
                   "numbers": ["+1YOURTWILIONUMBER"], "auth_username": "...", "auth_password": "..." } }
      ```
      Put the returned `ST_...` id in `SIP_OUTBOUND_TRUNK_ID`.
4. Set `DEMO_PHONE` and `ALLOWED_NUMBERS` to your verified mobile number.

Twilio trial calls start with a short "trial account" message. Press any key to continue.

## Run the demo
```
.venv\Scripts\python dial.py --reset                 # seed 10 fictional customers
.venv\Scripts\python agent.py dev                    # terminal 1: start the agent worker
.venv\Scripts\python dial.py --customer C001         # terminal 2: your phone rings
.venv\Scripts\python dial.py --all                   # or work the whole queue, one call at a time
.venv\Scripts\python report.py --events              # results + audit trail
```
No phone? `python agent.py console` talks to `CONSOLE_CUSTOMER_ID` through your mic and speakers.

Transcripts are saved to `data/transcripts/`.

## Test customers (answer as them)
| ID | Name | ZIP | Birth year | Due | Failure | Best path |
|---|---|---|---|---|---|---|
| C001 | Maya Thompson | 94107 | 1988 | $49.99 | insufficient funds | retry now |
| C002 | Daniel Okafor | 10001 | 1975 | $129.00 | card expired | update link |
| C003 | Priya Raman | 60614 | 1992 | $18.50 | bank declined | update link / schedule |
| C004 | Luis Fernandez | 73301 | 1981 | $240.00 | insufficient funds | payment plan |
| C005 | Hannah Becker | 98101 | 1969 | $75.25 | card lost/stolen | update link |
| C006 | Kwame Mensah | 30303 | 1995 | $12.99 | card expired | update link |
| C007 | Sofia Rossi | 02108 | 1984 | $310.40 | bank declined | ask for human → escalate |
| C008 | Ethan Brooks | 80202 | 1999 | $59.00 | insufficient funds | schedule after payday |
| C009 | Aiko Tanaka | 96813 | 1978 | $89.90 | processing error | retry now |
| C010 | Robert Klein | 33101 | 1958 | $150.00 | insufficient funds | **do-not-call, skipped** |

Retrying the card succeeds for insufficient funds and processing errors. It fails for expired, declined and lost cards, so the agent pivots to the secure link.

## Files
| File | Purpose |
|---|---|
| `agent.py` | LiveKit agent: prompt, tools, outbound SIP dial, voicemail handling, transfer, transcript |
| `billing.py` | Mock billing API + event log (SQLite) |
| `dial.py` | Dispatcher: single customer, whole queue, dry run |
| `safety.py` | Allowlist, do-not-call and call-hours checks |
| `report.py` | Recovery summary and audit trail |
| `data/customers.json` | 10 fictional records |

## Quality: tests, evals, human review
```
.venv\Scripts\python -m pytest -q                    # 10 offline tests (no keys)
.venv\Scripts\python evals\run_evals.py --validate   # check scenario file (no keys)
.venv\Scripts\python evals\run_evals.py -n 3         # 14 simulated conversations x3, needs GROQ_API_KEY
.venv\Scripts\python review.py                       # supervisor queue (pending plans, escalations)
.venv\Scripts\python review.py approve C004 --by you
.venv\Scripts\python review.py sample 3 --by you     # QA-label finished calls
.venv\Scripts\python review.py agreement             # human vs automated verdicts (evals/human_labels.json)
```
Payment plans over $200 or with 3 installments go to `pending_approval` and need a human.
The interview write-up is in `docs/WRITEUP.md`.
