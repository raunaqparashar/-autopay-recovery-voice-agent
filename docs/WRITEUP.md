# Write-up

## What it does
Outbound voice agent ("Ava") for failed-autopay recovery. Discloses it is an AI, verifies identity
(ZIP + birth year), explains the failure, and resolves via retry, scheduled payment, secure card-update link,
or a 2–3 installment plan. Escalates to a human when needed.

## Tools and data
- **Pipeline:** LiveKit Agents; Deepgram STT; Groq `gpt-oss-120b`; Cartesia TTS; Twilio SIP (optional).
- **Agent tools (8):** `verify_identity`, `retry_payment`, `schedule_payment`, `send_update_link`,
  `setup_payment_plan`, `transfer_to_human`, `detected_voicemail`, `end_call`.
- **Data:** 10 fictional customers (`data/customers.json`), mock billing in SQLite with an append-only event log.

## Guardrails
| Layer | Control |
|---|---|
| Pre-dial | number allowlist, do-not-call flag, 08:00–21:00 local-time window (`safety.py`) |
| Identity | account tools refuse to run until verified; lockout after 2 failed attempts (enforced in code) |
| Payments | no card numbers over voice, secure link instead |
| Privacy | no account details to wrong party or on voicemail |
| Conduct | AI disclosure, no pressure or threats, prompt-injection resistance |

## Human review
- Hardship, disputes or a request for a person → `transfer_to_human` (or callback).
- Plans over $200 or 3 installments → `pending_approval`; supervisor approves/rejects in `review.py`.
- `review.py sample` for QA labelling; `review.py agreement` compares human vs automated verdicts.

## Evaluation
- **Unit tests:** 10 offline tests (identity gate, lockout, approval gate, allowlist/DNC, scoring logic).
- **Scenario evals:** 14 scenarios (8 adversarial). The real agent talks to an LLM-simulated customer.
  - Deterministic checks on the event log: final status, required/forbidden tools, identity gate, card-number echo.
  - LLM judge (1–5): compliance, task success, clarity, brevity.

**Results** (`evals/results/final-20261004.json`, 1 run):

| Metric | Result |
|---|---|
| Scenarios passed | 13/14 (93%) |
| Guardrail scenarios passed | 7/8 |
| Judge: compliance / task / clarity / brevity | 5.0 / 4.64 / 4.71 / 4.79 |
| Identity-gate or card-echo violations | 0 |

The single failure (`are_you_a_robot`) was a scenario-spec issue: the agent disclosed it was an AI correctly, but
the simulated customer chose the update link instead of paying. The expectation has been widened.

**Found and fixed by evals:**
- The agent repeated its goodbye three times. `log_outcome` and `end_call` were merged into one tool that ends the
  turn, which raised the brevity score.
- Free-tier rate limits (8k tokens/min) broke runs. Added pacing/retry and spread the agent, simulator and judge
  across separate models.

## Limitations
Mock billing and link. Identity check is basic (a real system would use a one-time code). The simulated customers
are cleaner than real callers. Compliance (TCPA / TRAI, consent to record) would need review before real use.
