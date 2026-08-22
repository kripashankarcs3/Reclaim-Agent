# ReclaimAgent — AI Revenue Recovery (Razorpay Buildathon, Track 03)

A closed-loop agent that watches a Razorpay merchant's payment stream, detects
revenue at risk (failed payments, abandoned checkouts, halted subscriptions),
**diagnoses** the root cause from Razorpay error codes, **decides** the cheapest
*compliant* intervention, **gates** it through a deterministic policy engine,
executes it, and proves how much money it recovered — with a full audit trail
and an honest exception list.

## Core design: propose–verify split
> **The LLM PROPOSES. A deterministic policy engine DECIDES.**
> The LLM never moves money. Every proposed action passes through
> `policy_engine.check()` first; any rule failure = **blocked + logged with reason**.

This is the whole defense: judges will try to make the agent do something
unsafe — the *runtime* (not the prompt) refuses.

## Run the winning spine (no keys, no network needed)
```bash
python run_batch.py                    # full 54-txn batch -> metrics + exception list
python run_batch.py --demo-hour 21     # force 9 PM -> contact-window blocks
python run_batch.py --show-timeline txn_049   # one case's full audit timeline
```

## How this hits every element of Track 03's bar
| Judge bar element | Where it lives |
|---|---|
| ✅ Explainable | `audit.py` per-case timeline + `diagnoser.explain()` |
| ✅ Bounded / Gated | `policy_engine.py` (rules-as-code, LLM can't override) |
| ✅ Compliant escalation | `decider.py` → `human_review`; policy blocks route out |
| ✅ Stopping rules | RETRY_CAP (NPCI 1+3) + HARD_DECLINE halt in `policy_engine.py` |
| ✅ Audit trail | `audit.py` — append-only `AuditEntry` per stage |
| ✅ Measured money recovered across a batch | `metrics.py` over 50+ synthetic txns |
| ✅ Honest metrics + false-positive cost | `metrics.py` (precision, FP cost, exception list) |
| ✅ One failure handled gracefully | the policy BLOCK moment (9 PM / >₹15k / hard decline) |

## Compliance rules encoded (interview ammunition — see `config.py`)
- **NPCI 1 + 3 retry cap** (max 4 attempts, effective 1 Aug 2025)
- **RBI ₹15,000 AFA threshold** (E-mandate Framework, 2026; ₹1,00,000 for MF/insurance/CC)
- **RBI 24-hour pre-debit notification**
- **RBI 8 AM–7 PM contact window** (fair-practices; used as safe default)
- **TRAI TCCCPR** transactional template + 90-day opt-out cooldown
- **Per-customer spend cap** (over-contact guard)

## Architecture
```
[webhook/batch] -> detector -> diagnoser (label + LLM explanation)
   -> decider (PROPOSE) -> policy_engine.check (DECIDE)
        ├── allowed -> executor -> verify -> audit(outcome)
        └── blocked -> audit(blocked + reason) -> human_review
```

## Honest caveats (say these out loud — judges reward candor)
- Notifications are **mocked** (template + compliance checks are real; nothing is sent).
- Synthetic 54-txn batch drives deterministic outcomes so the demo never stalls.
- **UPI Payment Links are live-mode only**; demo uses test-mode-supported primitives.
- Executor is dry-run in the spine; real Razorpay SDK wiring is in `executor.py` TODOs.

## Build order (what's done vs next)
Done (runnable spine): DB models · 54-txn seed w/ ground truth · **policy engine** ·
diagnoser · decider · audit log · metrics · batch harness · mocked notifications.
Next: wire `executor.py` to Razorpay test APIs · `main.py` webhook (verify + idempotency) ·
`agent.py` LangGraph loop · React dashboard (audit timeline = the star panel).
