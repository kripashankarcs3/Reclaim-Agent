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

**The proposer is deliberately naive.** `decider.py` proposes the cheapest
*tempting* action — including ones that are plainly non-compliant (re-presenting a
mandate after a hard NSF decline, debiting Rs.49,999 silently). It contains no
amount, cap, or consent logic at all. That is on purpose: if the proposer refused
first, the audit trail would show `policy_check: allowed=True` and "the runtime
refuses" would be an empty claim. **Every refusal in this system is produced by
`policy_engine.check()` and carries the failed rule names.**

When the gate blocks a debit, the agent tries the *compliant fallback* (a
customer-initiated payment link) — which is itself re-proposed and re-gated, never
waved through. If the fallback is also blocked, the case escalates to human review
with every failed rule attached. Which blocks earn a fallback is itself
rules-as-code (`config.FALLBACK_ELIGIBLE_RULES` / `HUMAN_ESCALATION_RULES`), not a
judgement call: a spent mandate can still be paid by the customer, but if we are
forbidden from *contacting* the customer at all, a link+nudge is exactly what we
must not do.

## Run the winning spine (no keys, no network needed)
```bash
python run_batch.py                    # full 54-txn batch -> metrics + exception list
python run_batch.py --demo-hour 21     # force 9 PM -> contact-window blocks
python run_batch.py --show-timeline txn_046   # the 3-rule gate block (star case)
python run_batch.py --show-notifications      # print every mocked TRAI template
```

Optional live mode (needs `pip install razorpay` + `rzp_test_` keys in `.env`):
```bash
python executor.py --ping              # read-only payment.all(); creates nothing
python run_batch.py --live             # ONE real test-mode payment link, rest simulated
python run_batch.py --live --live-limit 0   # all 33 links real (slow; not for the demo)
```
Without `--live` the spine makes **zero network calls** and needs no keys at all.

**The star case — txn_046** (Rs.25,000, subscription, `insufficient_funds`, mandate
already re-presented 3x). The agent *proposes the retry*; the gate stacks three
refusals on it and routes it to a human:

```
[decide      ] proposed_action: retry
[policy_check] action: retry  allowed: False
               RETRY_CAP: NPCI 1+3 cap exhausted (4/4 attempts used)
               HARD_DECLINE: hard decline not eligible for silent retry (link only)
               AFA_THRESHOLD: amount Rs.25000 > Rs.15000 requires AFA (no silent debit)
[outcome     ] human_review
```

## How this hits every element of Track 03's bar
| Judge bar element | Where it lives |
|---|---|
| ✅ Explainable | `audit.py` per-case timeline + `diagnoser.explain()` |
| ✅ Bounded / Gated | `policy_engine.py` (rules-as-code, LLM can't override) |
| ✅ Compliant escalation | gate-blocked debit → re-gated `payment_link` → else `human_review` |
| ✅ Stopping rules | RETRY_CAP (NPCI 1+3) + HARD_DECLINE halt in `policy_engine.py` |
| ✅ Metrics that measure only what is really possible | `MANDATE_REQUIRED` — no mandate, no silent retry, no "recovery" |
| ✅ Channel compliance actually exercised | `nudge` is a **separately gated** action → `notifications.py` |
| ✅ Audit trail | `audit.py` — append-only `AuditEntry` per stage |
| ✅ Measured money recovered across a batch | `metrics.py` over 50+ synthetic txns — **recovered and actioned reported separately** |
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
   -> decider (PROPOSE the cheapest tempting action — no safety logic here)
   -> policy_engine.check (DECIDE)
        ├── allowed -> executor -> audit(execute)
        │                └─ link created? -> nudge is a SEPARATE proposal
        │                     -> policy_engine.check("nudge")   <- TRAI + window
        │                          ├── allowed -> notifications (mock template) -> audit
        │                          └── blocked -> audit(suppressed + reason)
        └── blocked -> audit(failed rules)
                 -> compliant fallback (payment_link) -> policy_engine.check AGAIN
                      ├── allowed -> executor -> audit(escalated_from: retry)
                      └── blocked -> human_review + every failed rule
```

Creating a payment link contacts nobody; *telling the customer about it* does. So the
link and the nudge are two proposals with two independent gate checks — which is why
`rule_trai_messaging` and the 8 AM–7 PM window are reachable at all.

## Honest caveats (say these out loud — judges reward candor)
- Notifications are **mocked** (template + compliance checks are real; nothing is sent).
  They are wired into the executed path — 39 templates logged, 2 suppressed by TRAI
  rules in the default run — but `notifications.send()` only ever logs.
- **False-positive cost is 1, and we left it there.** txn_049 is a subscription whose
  24-hour pre-debit notice was never sent. The gate correctly refuses the debit; the
  agent falls back to a payment link and ends `pending`, while the seed's ground truth
  says that case should have gone to a human. We think a customer-initiated link needs
  no pre-debit notice, so the fallback is defensible — but the stricter reading is too,
  so the ground truth was **not** edited to match our own output. A non-zero,
  explicable FP is better evidence than a suspiciously clean zero.
- **We cut our own headline number by 64% on purpose (Rs.18,188 -> Rs.6,497).**
  Earlier, `soft` + non-subscription failures proposed a silent `retry` and "recovered"
  — but a merchant cannot silently re-charge a one-time payment: there is no stored
  mandate or token, so no debit API exists to call. Those rupees were never actually
  recoverable; the number was inflated by construction. `rule_mandate_required` now
  blocks `retry` on any txn without a mandate, and those cases escalate to a
  customer-initiated payment link and end `pending`. **Every rupee in the recovery
  figure is now mandate-backed and genuinely re-presentable.** The drop is a
  correctness fix, not a regression — the old number measured something that could
  not happen.
- **Two numbers, never merged: recovered vs actioned.** *Recovered* (Rs.6,497, 3.1%)
  means the customer actually paid. *At-risk actioned* (Rs.96,457, 45.9%) means we got
  a compliant recovery path in front of the customer — 41 live payment links worth
  Rs.89,960 — but **a link is not a payment until somebody pays it**, so that money is
  reported as in-flight, not recovered. Folding the two together would re-create exactly
  the inflation Phase 3.6 removed, so `metrics.py` computes and prints them as separate
  lines and never sums them into one "recovery rate".
- **Rs.7,495 across 5 cases is pending with no link at all** — a mandate-backed retry
  the gate allowed, which then did not recover. Because the retry was permitted there
  was no gate block, so no fallback link was generated and the customer currently has
  no way to pay. Reported explicitly rather than buried in "pending".
- Synthetic 54-txn batch drives deterministic outcomes so the demo never stalls.

### What the LIVE Razorpay calls actually returned (Phase 4, measured — not claimed)
- **Standard Payment Links DO work in test mode.** Verified end to end: `payment_link
  .create` returned a real, openable `short_url`, and `payment_link.fetch(id)` confirms
  it server-side (`plink_TSltLVDkNcwer9` -> `https://rzp.io/rzp/Angyk9m`, amount 99900
  paise = Rs.999, matching txn_016).
- **UPI Payment Links are live-mode only — we did NOT test them and do not fake them.**
  The demo is built on standard links precisely because they are the test-mode-supported
  primitive. No UPI-link code path exists in this repo.
- **Nothing is ever sent, verified server-side.** The created link comes back with
  `notify: {email: False, sms: False, whatsapp: False}` and `reminder_enable: False`.
  Razorpay would happily SMS/email the customer if those defaulted on — so the executor
  sets them explicitly. (It also exposes a `whatsapp` channel the docs' two-field
  example omits; it defaults off.)
- **`payment.all()` returns 0 payments.** The test account has no payment history, so
  none of the batch is drawn from live data — all 54 transactions are synthetic. A
  payment link is not a payment until somebody pays it.
- **`payment_link.all()` is not reliable here** — it returned an empty list despite
  confirmed creations, then `BadRequestError: Too many requests`. `fetch(id)` is the
  verification path we actually trust.
- **Retries are simulated even under `--live`.** Only payment links are real; we never
  fire an actual recurring debit. Deliberate scope, not an oversight.
- **`--live` creates ONE real link by default** (`--live-limit 1`, `0` = all 33). A
  33-call live run would be exactly the stalling demo the invariants forbid.
- **`reference_id` carries a run-unique timestamp suffix** because Razorpay rejects
  duplicates — so it is not yet a stable idempotency key. Real idempotency arrives in
  Phase 5 via the webhook's `x-razorpay-event-id`.
- **Live failures degrade to `human_review`, never to a fake link.** Any executor
  exception is audited as `EXECUTOR_ERROR` and the case is routed to a human.
- **The executor refuses `rzp_live_` keys outright.** This agent structurally cannot run
  against a live account.
- **LLM explanations are opt-in** (`RECLAIM_LLM_EXPLAIN=1`). Phase 4 introduced
  `load_dotenv()`, which put `LLM_API_KEY` into the process env and silently
  turned the offline batch into 54 network calls (measured: 0.25s -> 59s) with output
  unchanged. Gating the LLM behind an explicit flag restores the deterministic,
  zero-network default.

## Build order (what's done vs next)
Done (runnable spine): DB models · 54-txn seed w/ ground truth · **policy engine** ·
diagnoser · decider · audit log · metrics · batch harness · mocked notifications ·
**gate-produced refusals + two-step compliant escalation + separately-gated nudges** ·
**real Razorpay test-mode executor behind a `dry_run` seam (`--live`)**.
Next: `main.py` webhook (verify + idempotency) ·
`agent.py` LangGraph loop · React dashboard (audit timeline = the star panel).
