"""
run_batch.py — Poore batch ko pipeline se chalata hai (deterministic).

Ye Phase 5 ke LangGraph agent ka pure-Python version hai — same flow:
  detect -> diagnose -> decide(propose) -> policy_engine.check
         -> allowed?  execute
         -> blocked?  compliant fallback propose -> check AGAIN
         -> phir bhi blocked? human_review (gate ke reasons ke saath)
  link bana? -> nudge ALAG action hai -> ALAG gate check -> mocked TRAI template

Isse tum bina Razorpay keys / webhooks ke bhi WINNING SPINE chala sakte ho.
Executor yahan DRY-RUN hai (real Razorpay call Phase 4 mein wire hoga).

Run:  python run_batch.py
      python run_batch.py --demo-hour 21        # 9 PM -> contact-window blocks
      python run_batch.py --show-timeline txn_046
      python run_batch.py --show-notifications  # mocked TRAI templates print karo
"""
import argparse
from datetime import datetime

import seed
import diagnoser
import decider
import policy_engine
import executor
import notifications
from audit import AuditLog
import metrics


def execute_dry_run(action, txn):
    """
    Phase 4 mein ye executor ke REAL razorpay calls karega. Abhi executor ke
    dry-run stubs — outcome deterministically simulate hota hai.
    Returns: (outcome, link_dict_or_None)
    """
    if action == "retry":
        executor.retry_charge(txn)
        # Soft declines mostly recover on retry (deterministic by id parity)
        outcome = "recovered" if int(txn.id.split("_")[1]) % 3 != 0 else "pending"
        return outcome, None
    if action in ("payment_link", "recovery_link"):
        link = executor.create_payment_link(txn)   # link banana = koi contact NAHI
        return "pending", link                     # customer action pending
    return "not_attempted", None


def run(demo_hour=14, show_notifications=False):
    """demo_hour: 'current time' force karne ke liye (window rule demo)."""
    now = datetime.now().replace(hour=demo_hour, minute=30)
    batch = seed.generate()
    log = AuditLog()
    customer_attempts = {}   # spend-cap tracking
    results = []

    for txn in batch:
        cid = txn.customer_id

        # 1) DETECT
        log.log(txn.id, "detect", {"status": txn.status, "amount": txn.amount,
                                    "error_code": txn.error_code})

        # 2) DIAGNOSE (deterministic label + explanation)
        label, explanation = diagnoser.diagnose(txn)
        log.log(txn.id, "diagnose", {"label": label, "explanation": explanation})

        # 3) DECIDE (propose only — deliberately naive, see decider.py)
        proposed = decider.propose(txn, label)
        log.log(txn.id, "decide", {"proposed_action": proposed})

        def cust_state():
            """Policy ke liye customer state (spend cap + TRAI consent)."""
            s = seed.messaging_state(cid)
            s["attempts_today"] = customer_attempts.get(cid, 0)
            return s

        # 4) POLICY GATE (the star) — refusal SIRF yahan se aata hai
        verdict = policy_engine.check(proposed, txn, label, now=now,
                                      customer_state=cust_state())
        log.log(txn.id, "policy_check",
                {"action": proposed, "allowed": verdict["allowed"],
                 "failed_rules": verdict["reasons"]})

        action = proposed
        escalated_from = None
        gate_reasons = []
        failed_rules = list(verdict["failed_rules"])
        link = None

        # 5) EXECUTE, or ESCALATE via a compliant fallback, or HUMAN REVIEW
        if proposed == "human_review":
            # Diagnoser label unclassified tha — koi money action propose hi nahi hua.
            outcome = "human_review"
            gate_reasons = ["unclassified failure - no automated action proposed"]
        elif verdict["allowed"]:
            outcome, link = execute_dry_run(proposed, txn)
            customer_attempts[cid] = customer_attempts.get(cid, 0) + 1
        else:
            gate_reasons = list(verdict["reasons"])
            fb = decider.fallback(proposed, verdict["failed_rules"])
            if fb:
                # Fallback bhi PROPOSAL hai — dobara gate se guzarta hai (no bypass).
                v2 = policy_engine.check(fb, txn, label, now=now,
                                         customer_state=cust_state())
                log.log(txn.id, "policy_check",
                        {"action": fb, "escalated_from": proposed,
                         "allowed": v2["allowed"], "failed_rules": v2["reasons"]})
                failed_rules += list(v2["failed_rules"])
                if v2["allowed"]:
                    action, escalated_from = fb, proposed
                    outcome, link = execute_dry_run(fb, txn)
                    customer_attempts[cid] = customer_attempts.get(cid, 0) + 1
                else:
                    gate_reasons += list(v2["reasons"])
                    action, outcome = "human_review", "human_review"
            else:
                action, outcome = "human_review", "human_review"

        # 6) NUDGE — ALAG action, ALAG gate check.
        #    Link banana customer ko contact nahi karta; usse BATANA karta hai.
        #    Isliye TRAI messaging rule yahan lagta hai, link check se alag.
        nudge = None
        if link is not None:
            vn = policy_engine.check("nudge", txn, label, now=now,
                                     customer_state=cust_state())
            log.log(txn.id, "policy_check",
                    {"action": "nudge", "allowed": vn["allowed"],
                     "failed_rules": vn["reasons"]})
            if vn["allowed"]:
                record = notifications.send(cid, txn.amount, txn.order_id,
                                            link["short_url"], now=now,
                                            verbose=show_notifications)
                log.log(txn.id, "notify", record)
                customer_attempts[cid] = customer_attempts.get(cid, 0) + 1
                nudge = {"status": "sent", "reasons": []}
            else:
                log.log(txn.id, "notify",
                        {"suppressed": True, "reasons": vn["reasons"]})
                failed_rules += list(vn["failed_rules"])
                nudge = {"status": "suppressed", "reasons": list(vn["reasons"])}

        log.log(txn.id, "outcome", {"outcome": outcome, "reasons": gate_reasons,
                                    "escalated_from": escalated_from})
        results.append({"txn": txn, "label": label,
                        "proposed_action": proposed, "action": action,
                        "escalated_from": escalated_from,
                        "allowed": verdict["allowed"], "outcome": outcome,
                        "reasons": gate_reasons, "failed_rules": failed_rules,
                        "nudge": nudge})

    return results, log


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo-hour", type=int, default=14,
                    help="Force 'current hour' (e.g. 21 for 9PM window-block demo)")
    ap.add_argument("--show-timeline", type=str, default=None,
                    help="Print audit timeline for a txn id, e.g. txn_046")
    ap.add_argument("--show-notifications", action="store_true",
                    help="Print every mocked TRAI template as it is logged")
    args = ap.parse_args()

    results, log = run(demo_hour=args.demo_hour,
                       show_notifications=args.show_notifications)
    m = metrics.compute(results)
    metrics.print_report(m)

    if args.show_timeline:
        log.print_timeline(args.show_timeline)
    else:
        # Sabse zyada rules ek saath fail karne wala case auto-dikhao
        # (gate-produced refusal = graceful-failure proof).
        worst = max((r for r in results if r["failed_rules"]),
                    key=lambda r: len(r["failed_rules"]), default=None)
        if worst:
            print("\n  (Most-gated case - refusal comes from policy_engine, "
                  "not the decider:)")
            log.print_timeline(worst["txn"].id)
