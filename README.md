# ReclaimAgent

AI-powered revenue recovery for Razorpay payments, built for Razorpay Buildathon — Track 03.

ReclaimAgent monitors failed payments and other revenue-at-risk events, identifies the likely cause, proposes a recovery action, and checks that action against a deterministic policy engine before anything is executed.

The key design principle is simple:

> **The LLM proposes. The policy engine decides.**

The model does not control payments or compliance decisions. Every action goes through `policy_engine.check()` and a blocked action is recorded with the rule that caused the refusal.

---

## What it does

ReclaimAgent runs a transaction through a single recovery pipeline:

1. **Detect** a payment or subscription at risk.
2. **Diagnose** the failure using Razorpay error information.
3. **Decide** on a proposed recovery action.
4. **Gate** the proposal through deterministic rules.
5. **Execute** an allowed action.
6. **Fallback** to a customer-initiated payment link when appropriate.
7. **Nudge** the customer only after a separate messaging-policy check.
8. **Escalate** to human review when no compliant automated route remains.
9. **Audit** every stage.

The same pipeline is used by both the offline batch runner and the webhook/LangGraph path, so the two entry points do not maintain separate business logic.

---

## Why the propose–verify split matters

The proposer is intentionally not responsible for safety rules. It can suggest an action that should ultimately be rejected.

For example, it may propose a retry even when:

- the retry cap has already been reached,
- the failure is a hard decline,
- additional authentication is required, or
- the transaction has no mandate that can legally be re-presented.

The policy engine is responsible for making that decision.

If an action is blocked, the failure is logged with the relevant rule names. If a debit is blocked, the system can propose a customer-initiated `payment_link`, but that fallback is also sent through the policy engine. A fallback can therefore be blocked as well, in which case the case is escalated to `human_review`.

This keeps compliance logic in code instead of relying on an LLM prompt.

---

## Quick start

The default demo is completely offline. No Razorpay credentials or network access are required.

```bash
python run_batch.py
```

Useful demo commands:

```bash
# Run the full 54-transaction batch
python run_batch.py

# Simulate a 9 PM run to exercise contact-window rules
python run_batch.py --demo-hour 21

# Inspect the timeline for the main policy-block case
python run_batch.py --show-timeline txn_046

# Show all mocked notification templates
python run_batch.py --show-notifications
```

### Example: policy-gated recovery

`txn_046` is a ₹25,000 subscription payment with `insufficient_funds`, where the mandate has already been re-presented three times.

The agent can propose a retry, but the policy engine rejects it because multiple independent rules apply:

```text
[decide      ] proposed_action: retry
[policy_check] action: retry  allowed: False
               RETRY_CAP: NPCI 1+3 cap exhausted (4/4 attempts used)
               HARD_DECLINE: hard decline not eligible for silent retry (link only)
               AFA_THRESHOLD: amount Rs.25000 > Rs.15000 requires AFA (no silent debit)
[outcome     ] human_review
```

---

## Live Razorpay test mode

Live integration is optional and deliberately limited to Razorpay test mode.

Install the SDK:

```bash
pip install razorpay
```

Configure test credentials in `.env` and then:

```bash
# Read-only connectivity check
python executor.py --ping

# Create one real test-mode payment link; everything else stays simulated
python run_batch.py --live

# Create real links for the full set
python run_batch.py --live --live-limit 0
```

Without `--live`, the application makes **zero network calls**.

The executor refuses `rzp_live_` keys, so the repository cannot be used against a live Razorpay account.

Retries remain simulated even in `--live`; the only real external operation is payment-link creation.

---

## Architecture

There are two entry points, but only one transaction pipeline:

```text
                 ┌──────────────────┐
                 │  Webhook / Batch │
                 └────────┬─────────┘
                          │
                       detector
                          │
                       diagnoser
                          │
                   decider / LLM
                  (proposes action)
                          │
                          ▼
                ┌───────────────────┐
                │   Policy Engine   │
                │     (decides)     │
                └─────────┬─────────┘
                    ┌─────┴─────┐
                 allowed      blocked
                    │             │
                 executor      fallback
                    │          payment_link
                  audit             │
                    │          policy check
                    │          ┌────┴────┐
                    │       allowed   blocked
                    │          │          │
                    │       executor   human_review
                    │
                    └── payment link created?
                              │
                         nudge proposal
                              │
                        policy check
                         ┌────┴────┐
                      allowed   blocked
                         │          │
                  notification    audit
```

### Core modules

| Module | Responsibility |
| --- | --- |
| `pipeline.py` | Single source of truth for the transaction flow, steps, routes and context |
| `run_batch.py` | Runs the seeded transaction batch |
| `agent.py` | LangGraph entry point; wraps the same pipeline steps and routes |
| `detector.py` | Identifies revenue-at-risk transactions |
| `diagnoser.py` | Classifies failures and provides explanations |
| `decider.py` | Proposes a recovery action |
| `policy_engine.py` | Deterministic safety and compliance gate |
| `executor.py` | Only module that communicates with Razorpay |
| `store.py` | SQLite persistence for attempts, contacts and audit history |
| `audit.py` | Append-only audit entries and transaction timelines |
| `metrics.py` | Recovery, actioned-value, precision and false-positive metrics |
| `notifications.py` | Mocked customer notification path |

---

## Compliance rules

The policy engine currently encodes the following rules:

- **NPCI 1+3 retry cap** — maximum four attempts.
- **RBI ₹15,000 AFA threshold** — silent debit is not allowed above the configured threshold.
- **RBI 24-hour pre-debit notification**.
- **8 AM–7 PM contact window** used as the safe contact-window rule.
- **TRAI TCCCPR messaging checks**, including transactional templates and opt-out handling.
- **Per-customer contact/spend cap** to prevent repeated customer contact.

The important part is not only that these rules exist, but that they are evaluated at runtime. A proposed action cannot bypass them.

---

## Persistence and webhook handling

Webhook events do not contain all the state needed for recovery decisions. In particular, retry history and pre-debit notification state are maintained by the application.

`store.py` persists:

- retry/attempt history by `order_id`,
- daily customer contact counts,
- append-only audit entries.

`order_id` is used for attempt history rather than payment ID because Razorpay can issue a new payment ID for a re-presentment while the order remains the same.

The contact tally also includes the day in its key so that the daily cap resets by date rather than by process restart.

The webhook path uses Razorpay's `x-razorpay-event-id` for idempotency and verifies webhook signatures before processing the event.

---

## Auditability

Every important stage produces an audit entry.

A transaction timeline can therefore show:

```text
detect
  → diagnose
  → decide
  → policy_check
  → execute / blocked
  → fallback
  → policy_check
  → nudge
  → escalate
  → finalize
```

A blocked action records the failed policy rules instead of simply returning a generic error.

The audit log is persisted in SQLite, so the history survives process restarts and can be reconstructed across payment re-presentments using the order-level timeline.

---

## Metrics

The project intentionally keeps **recovered** and **actioned** money separate.

- **Recovered** means the customer actually paid.
- **At-risk actioned** means the system created a compliant recovery path, such as a payment link. A link is not counted as recovered until the payment is actually made.

In the measured 54-transaction synthetic batch:

- **₹6,497 recovered** (3.1%)
- **₹103,952 at-risk actioned** (49.5%)
- 46 live payment links represented ₹97,455 of the actioned amount.

The distinction is important: combining these numbers would overstate actual revenue recovery.

---

## Current limitations

The demo intentionally keeps several integrations conservative:

- Notifications are mocked. Compliance checks and templates are exercised, but no SMS, email or WhatsApp message is sent.
- Payment retries are simulated. The repository does not perform a real recurring debit.
- The default batch uses 54 synthetic transactions rather than live merchant payment history.
- Standard Razorpay Payment Links were verified in test mode. UPI Payment Links were not tested and are not implemented in this repository.
- `payment_link.fetch(id)` is used as the verification path for created links.
- The default live run creates one real test-mode payment link to keep demos predictable.
- LLM explanations are opt-in with `RECLAIM_LLM_EXPLAIN=1`; the default batch remains deterministic and offline.

These limitations are deliberate. The system does not claim a recovery, API call, or customer notification that it did not actually perform.

---

## Verified Razorpay test-mode behavior

The live integration was tested against Razorpay's test environment.

Verified behavior includes:

- Standard Payment Link creation returning a real `short_url`.
- Server-side verification of a created link using `payment_link.fetch(id)`.
- Explicitly disabling Razorpay's email, SMS and WhatsApp notification flags when creating the link.
- Test-account payment history containing no payments, so the batch remains synthetic.
- Live executor failures degrading to `human_review` rather than producing a fake recovery result.
- The executor rejecting `rzp_live_` credentials.

The webhook path was also verified against an actual Razorpay test-mode `payment.failed` delivery through a running `uvicorn` service and ngrok tunnel. The request was signature-verified and passed through the same policy engine and persistent store used by the normal pipeline.

---

## Example: graceful escalation

When an automated debit is blocked, the system does not stop at the first refusal.

The route is:

```text
blocked debit
    ↓
propose payment_link
    ↓
policy check again
    ├── allowed → create link → separately gate customer nudge
    └── blocked → human_review
```

This matters because creating a payment link and contacting the customer are different actions. A link can exist without a message being sent, so messaging rules are evaluated separately.

---

## Project status

### Completed

- SQLite data models and persistence
- 54-transaction deterministic seed with ground truth
- Detection and diagnosis
- Recovery decision layer
- Deterministic policy engine
- Audit log and transaction timelines
- Recovery and false-positive metrics
- Batch demo harness
- Mocked notifications
- Two-step compliant escalation
- Separately gated customer nudges
- Razorpay test-mode executor behind a `dry_run` seam
- Shared `pipeline.py` transaction flow
- LangGraph `agent.py` entry point
- Persistent retry history and daily contact tally
- Webhook signature verification
- `x-razorpay-event-id` idempotency
- Live verification against a Razorpay test-mode webhook delivery

### Next

- React dashboard
- Audit timeline as the primary review interface

---

## Repository structure

```text
.
├── agent.py
├── audit.py
├── config.py
├── decider.py
├── diagnoser.py
├── detector.py
├── executor.py
├── metrics.py
├── notifications.py
├── pipeline.py
├── policy_engine.py
├── run_batch.py
├── store.py
└── main.py
```

---

## Design principles

A few decisions are intentional throughout the project:

1. **Business-critical safety rules live in code.**
2. **LLM output is treated as a proposal, never as authority.**
3. **Every fallback is re-evaluated by the same policy engine.**
4. **Customer contact and backend payment actions are treated as different actions.**
5. **Recovered money is never mixed with money merely placed on a recovery path.**
6. **Audit history is persistent rather than process-local.**
7. **The system prefers an explicit human-review outcome over an unsafe or unverifiable automated action.**

The goal is not to maximize the number of automated retries. It is to recover revenue where the system can do so **legitimately, explainably and measurably**.
