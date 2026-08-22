"""
run_batch.py — Poore batch ko pipeline se chalata hai (deterministic).

Ye Phase 5 ke LangGraph agent ka pure-Python version hai — same flow:
  detect -> diagnose -> decide(propose) -> policy_engine.check -> execute/block -> audit

Isse tum bina Razorpay keys / webhooks ke bhi WINNING SPINE chala sakte ho.
Executor yahan DRY-RUN hai (real Razorpay call Phase 4 mein wire hoga).

Run:  python run_batch.py
      python run_batch.py --demo-hour 21   # 9 PM force -> contact-window block dikhega
"""
import argparse
from datetime import datetime

import seed
import diagnoser
import decider
import policy_engine
from audit import AuditLog
import metrics


def execute_dry_run(action, txn):
    """Phase 4 mein razorpay SDK se replace hoga. Abhi outcome simulate."""
    if action == "retry":
        # Soft declines mostly recover on retry (deterministic by id parity)
        return "recovered" if int(txn.id.split("_")[1]) % 3 != 0 else "pending"
    if action in ("payment_link", "recovery_link"):
        return "pending"          # link bhej diya, customer action pending
    if action == "human_review":
        return "human_review"
    return "not_attempted"


def run(demo_hour=14):
    """demo_hour: 'current time' force karne ke liye (window rule demo)."""
    now = datetime.now().replace(hour=demo_hour, minute=30)
    batch = seed.generate()
    log = AuditLog()
    customer_attempts = {}   # spend-cap tracking
    results = []

    for txn in batch:
        # 1) DETECT
        log.log(txn.id, "detect", {"status": txn.status, "amount": txn.amount,
                                    "error_code": txn.error_code})

        # 2) DIAGNOSE (deterministic label + explanation)
        label, explanation = diagnoser.diagnose(txn)
        log.log(txn.id, "diagnose", {"label": label, "explanation": explanation})

        # 3) DECIDE (propose only)
        action = decider.propose(txn, label)
        log.log(txn.id, "decide", {"proposed_action": action})

        # customer state for policy (spend cap etc.)
        attempts_today = customer_attempts.get(txn.customer_id, 0)
        cust_state = {"attempts_today": attempts_today, "has_consent": True,
                      "opted_out_within_cooldown": False}

        # 4) POLICY GATE (the star)
        verdict = policy_engine.check(action, txn, label, now=now,
                                      customer_state=cust_state)
        log.log(txn.id, "policy_check",
                {"action": action, "allowed": verdict["allowed"],
                 "failed_rules": verdict["reasons"]})

        # 5) EXECUTE or BLOCK
        if action == "human_review":
            outcome, reasons = "human_review", ["routed to human review (policy)"]
        elif verdict["allowed"]:
            outcome = execute_dry_run(action, txn)
            reasons = []
            customer_attempts[txn.customer_id] = attempts_today + 1
        else:
            outcome, reasons = "blocked", verdict["reasons"]

        log.log(txn.id, "outcome", {"outcome": outcome, "reasons": reasons})
        results.append({"txn": txn, "label": label, "action": action,
                        "allowed": verdict["allowed"], "outcome": outcome,
                        "reasons": reasons})

    return results, log


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo-hour", type=int, default=14,
                    help="Force 'current hour' (e.g. 21 for 9PM window-block demo)")
    ap.add_argument("--show-timeline", type=str, default=None,
                    help="Print audit timeline for a txn id, e.g. txn_055")
    args = ap.parse_args()

    results, log = run(demo_hour=args.demo_hour)
    m = metrics.compute(results)
    metrics.print_report(m)

    if args.show_timeline:
        log.print_timeline(args.show_timeline)
    else:
        # Ek blocked case ka timeline auto-dikhao (graceful-failure proof)
        blocked = next((r["txn"].id for r in results if r["outcome"] == "blocked"), None)
        if blocked:
            print(f"\n  (Sample blocked-case timeline — graceful failure proof:)")
            log.print_timeline(blocked)
