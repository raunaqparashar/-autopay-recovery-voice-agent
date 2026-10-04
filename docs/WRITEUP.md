# Write-up: Autopay Recovery Voice Agent

> Fill the `⟨…⟩` blanks from `python evals/run_evals.py -n 3`, `python report.py` and `python review.py agreement`
> after the live run. Don't quote numbers you haven't measured.

## 2-minute spoken answer

I built an outbound AI voice agent that calls customers whose autopay failed and tries to recover the payment.

**Tools and data:**
- LiveKit Agents runs the real-time pipeline: Deepgram for speech-to-text, gpt-oss-120b on Groq as the reasoning
  model, and Cartesia for text-to-speech. Calls go out over a Twilio SIP trunk.
- The model never touches data directly. It acts through eight typed tools, such as verify identity, retry the
  card, schedule a payment, send a secure card-update link, set up a payment plan and transfer to a human.
- The tools sit on a mock billing system with 10 fictional customers. I chose the customers so each one tests a
  different failure: insufficient funds, expired card, decline, lost card and processing error.

**Guardrails:** I put them in layers, and the important ones are enforced in code rather than by the prompt.
- Before dialing: a number allowlist, do-not-call and calling-hours checks.
- During the call: every account-changing tool refuses to run until identity is verified, with a two-attempt
  lockout. The agent never collects card numbers by voice; it sends a secure link instead. Voicemail messages
  contain no account details.
- In the prompt: the agent says it's an AI, doesn't pressure the customer, and ignores attempts to override its
  instructions.

**Human review:**
- Hardship, disputes or a request for a person trigger a transfer to a human.
- Payment plans over $200, or with three installments, aren't committed by the bot. They go to a supervisor queue
  to approve or reject.
- Supervisors also QA-sample finished calls.

**Evaluation:** a text-mode harness runs the real agent, with the same prompt and tools, against an LLM-simulated
customer across 14 scenarios.
- 8 of the scenarios are adversarial: wrong person on the line, failed verification, reading out a card number,
  prompt injection, hardship, do-not-call, "are you a robot?" and voicemail.
- Each run is scored two ways:
  1. Deterministic checks on the billing event log: correct final status, required or forbidden tools, the
     identity gate never bypassed, and no card number echoed back.
  2. An LLM judge rubric for compliance, task success, clarity and brevity.
- Three repeated runs showed ⟨X%⟩ overall pass rate ±⟨Y⟩, with guardrail scenarios at ⟨Z%⟩.
- Human labels agreed with the automated verdict ⟨A/B⟩ of the time.
- In live calls I tracked recovery rate, containment, escalation rate and latency per turn: ⟨…⟩.

The biggest lesson was ⟨e.g. what the first eval run caught and what I changed⟩.

---

## Long version

### 1. Problem
When autopay fails, the business loses revenue and it costs a lot to have staff phone each customer. The goal is to
contact every past-due customer quickly, recover as much as possible safely, and send the hard cases to people.

### 2. Architecture
```
dial.py (queue + pre-dial checks) ──▶ LiveKit dispatch ──▶ agent worker ──SIP──▶ Twilio ──▶ customer phone
                                                           │ STT Deepgram · LLM Groq gpt-oss-120b · TTS Cartesia
                                                           └─ tools ──▶ billing.py (SQLite + audit event log)
review.py (supervisor queue, QA) ◀── billing events / transcripts ──▶ report.py (KPIs)
evals/run_evals.py (simulated customers + judge) ──▶ evals/results/*.json
```

### 3. Tools and data
| Tool | Purpose | Gated by identity |
|---|---|---|
| verify_identity | ZIP + birth year, 2 attempts max | n/a |
| retry_payment | charge the card on file now | yes |
| schedule_payment | date within 30 days of failure | yes |
| send_update_link | secure link (SMS/email) to update the card | yes |
| setup_payment_plan | 2–3 installments; large plans go to approval | yes |
| transfer_to_human | live SIP transfer, or a callback if no line | no |
| detected_voicemail | message with no account details, then hang up | no |
| end_call(outcome) | log final outcome + hang up (merged after evals caught repeated goodbyes) | no |

Data: 10 fictional records (`data/customers.json`), each covering a different failure type or edge case. Every
action is written to an append-only event log, which serves as the audit trail and is also what the evals score.

### 4. Guardrails, in layers
| Layer | Guardrail | Where |
|---|---|---|
| Pre-dial | number allowlist; do-not-call; 08:00–21:00 in the customer's local time | `safety.py`, `dial.py` and `agent.py` |
| Identity | account tools refuse until verified; lockout after 2 failures | `RecoveryAgent._guard`, `verify_identity` |
| Data minimisation | no account details before verification, to a wrong party, or on voicemail | prompt + `detected_voicemail` |
| Payments (PCI) | card numbers never taken by voice; secure link instead | prompt; eval checks for card-number echo |
| Honesty | AI disclosure up front; never claims a payment succeeded unless a tool said so | greeting + prompt |
| Conduct | no threats or mention of collections; hardship → human | prompt + `transfer_to_human` |
| Injection | instructions can't be overridden by the caller; only tools change state | prompt + tool-only state changes |

### 5. Human review
- **Escalation:** hardship, disputes, legal or a request for a person → live transfer, or a callback logged.
- **Approval gate:** plans over $200 or with 3 installments get status `pending_approval`. The agent tells the
  customer the plan is not confirmed yet. A supervisor runs `review.py approve|reject <id>`, and the decision is
  logged.
- **QA sampling:** `review.py sample N` lets a human label finished calls pass or fail.
  `review.py agreement` measures how often humans agree with the automated eval.

### 6. Evaluation
- **Unit tests** (offline, `pytest`): 10 tests cover billing rules, allowlist and do-not-call, the identity gate
  enforced in code, the verification lockout, the approval gate and the eval scoring logic.
- **Scenario evals:** 14 scenarios (`evals/scenarios.yaml`), 8 of them guardrail scenarios. The real agent talks
  to a simulated customer (gpt-oss-20b). Scoring:
  - Deterministic: final status, required or forbidden tools, identity gate, card-number echo.
  - LLM judge (1–5): compliance, task success, clarity, brevity.
- **Variance:** `-n 3` reports the pass rate ± stdev, since LLM conversations aren't deterministic.
- **Live KPIs** (`report.py`): recovery rate, containment, escalation rate, average call length, and average
  latency for end of speech, the model's first token and the first audio from TTS.
- **Results:** ⟨paste scorecard + KPIs⟩

### 7. Limitations / next steps
- Mock billing and a mocked card-update link. A real deployment needs a PCI-compliant payment page and
  processor.
- Identity check is ZIP + birth year only. A real system would add stronger verification, such as a one-time
  code.
- The simulated customer is an LLM, so it's less messy than real callers. Next would be audio-level tests for
  noise and accents, and A/B testing call scripts.
- Compliance (TCPA/FDCPA, consent to record, regional rules) needs legal review before any real use.
