# Autopay Recovery Voice Agent

Outbound voice agent that calls customers whose autopay failed, verifies identity, and recovers the payment
(retry, schedule, secure card-update link, or payment plan). Uses 10 fictional customers and a mock billing system.

**Stack:** LiveKit Agents · Deepgram STT · Groq `gpt-oss-120b` · Cartesia TTS · optional Twilio SIP for PSTN.

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
