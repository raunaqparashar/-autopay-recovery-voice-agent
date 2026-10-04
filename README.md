# Autopay Recovery Voice Agent

Outbound voice agent that calls customers whose autopay failed, verifies identity, and recovers the payment
(retry, schedule, secure card-update link, or payment plan). Uses 10 fictional customers and a mock billing system.

**Stack:** LiveKit Agents · Deepgram STT · Groq `gpt-oss-120b` · Cartesia TTS · optional Twilio SIP for PSTN.

## Setup
Python 3.11+. Free-tier keys go in `.env` (copied from `.env.example`):

| Needed for | Keys |
|---|---|
| Unit tests | none |
| Evals | `GROQ_API_KEY` ([console.groq.com](https://console.groq.com)) |
| Voice session | Groq + `LIVEKIT_*` ([cloud.livekit.io](https://cloud.livekit.io)), `DEEPGRAM_API_KEY` ([deepgram.com](https://console.deepgram.com)), `CARTESIA_API_KEY` ([cartesia.ai](https://play.cartesia.ai)) |
| Phone calls | the above + SIP trunk (`setup_trunk.py`) |

`python check_env.py` shows which keys are set without printing them.

## Run
```
pip install -r requirements.txt
cp .env.example .env              # add API keys
python agent.py console           # local voice session (or BROWSER_DEMO=1 + LiveKit Agents Playground)
python dial.py --customer C001    # outbound phone call (requires SIP trunk)
python report.py                  # outcomes + KPIs
```

## Quality
```
python -m pytest -q               # offline unit tests
python evals/run_evals.py -n 3    # 14 simulated-customer scenarios, deterministic checks + LLM judge
python review.py                  # supervisor queue for escalations / plans needing approval
```

Design, guardrails and evaluation results: [docs/WRITEUP.md](docs/WRITEUP.md)
