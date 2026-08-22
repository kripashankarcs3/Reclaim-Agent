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


def run(demo_hour=14, show_notifications=False, live=False, live_limit=1):
    """
    demo_hour: 'current time' force karne ke liye (window rule demo).
    live:      payment_link actions REAL Razorpay test-mode API se banao.
               (Retries phir bhi simulated — executor.py rail #3 dekho.)
    live_limit: max kitne real link banayenge (0 = unlimited). Demo ko fast
               rakhne ke liye — invariant: live call pe demo stall nahi hona chahiye.
    """
    now = datetime.now().replace(hour=demo_hour, minute=30)
    batch = seed.generate()
    log = AuditLog()
    customer_attempts = {}   # spend-cap tracking
    results = []
    live_created = 0         # kitne REAL link ban chuke

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

        def do_execute(act):
            """
            Single execution seam — sab kuch executor.py se hokar jata hai.
            Returns (outcome, artifact, error_or_None).

            Live call fail hui to hum MOCK par fallback NAHI karte: error audit
            mein jata hai aur case human_review banta hai. Fake link kabhi nahi.
            """
            nonlocal live_created
            use_live = (live and act in ("payment_link", "recovery_link")
                        and (live_limit == 0 or live_created < live_limit))
            try:
                oc, art = executor.execute(act, txn, dry_run=not use_live)
            except Exception as e:
                err = f"EXECUTOR_ERROR: {type(e).__name__}: {e}"
                log.log(txn.id, "execute_error",
                        {"action": act, "live": use_live, "error": err})
                return "human_review", None, err
            if art is not None and art.get("live"):
                live_created += 1
                print(f"  [LIVE] {txn.id}: payment link created -> {art['short_url']}")
            log.log(txn.id, "execute",
                    {"action": act, "outcome": oc,
                     "live": bool(art and art.get("live")), "artifact": art})
            return oc, art, None

        # 4) POLICY GATE (the star) — refusal SIRF yahan se aata hai
        verdict = policy_engine.check(proposed, txn, label, now=now,
                                      customer_state=cust_state())
        log.log(txn.id, "policy_check",
                {"action": proposed, "allowed": verdict["allowed"],
                 "failed_rules": verdict["reasons"]})

        action = proposed
        escalated_from = None
        escalation_kind = None       # gate_blocked | retry_failed
        gate_reasons = []
        failed_rules = list(verdict["failed_rules"])
        link = None

        # 5) EXECUTE, or ESCALATE via a compliant fallback, or HUMAN REVIEW
        if proposed == "human_review":
            # Diagnoser label unclassified tha — koi money action propose hi nahi hua.
            outcome = "human_review"
            gate_reasons = ["unclassified failure - no automated action proposed"]
        elif verdict["allowed"]:
            outcome, link, exec_err = do_execute(proposed)
            if exec_err:
                action, gate_reasons = "human_review", [exec_err]
            else:
                customer_attempts[cid] = customer_attempts.get(cid, 0) + 1

                # 5b) RETRY CHALA PAR RECOVER NAHI HUA -> dead end mat chhodo.
                # Gate ne retry allow kiya tha, attempt hua, phir bhi paisa nahi
                # aaya. Aise case ko `pending` par bina link ke chhod dena matlab
                # customer ke paas pay karne ka koi rasta hi nahi — closed-loop
                # agent mein ye dead end hai. Isliye customer-initiated link
                # propose karo — aur use bhi DOBARA gate se guzaro (koi bypass
                # nahi, wahi escalation pattern jo blocked retry pe lagta hai).
                if proposed == "retry" and outcome != "recovered":
                    fb = "payment_link"
                    v3 = policy_engine.check(fb, txn, label, now=now,
                                             customer_state=cust_state())
                    log.log(txn.id, "policy_check",
                            {"action": fb, "escalated_from": "retry (attempted, not recovered)",
                             "allowed": v3["allowed"], "failed_rules": v3["reasons"]})
                    failed_rules += list(v3["failed_rules"])
                    if v3["allowed"]:
                        outcome, link, exec_err = do_execute(fb)
                        if exec_err:
                            action = "human_review"
                            gate_reasons = gate_reasons + [exec_err]
                        else:
                            action, escalated_from = fb, "retry"
                            escalation_kind = "retry_failed"
                            customer_attempts[cid] = customer_attempts.get(cid, 0) + 1
                    else:
                        # Link bhi gated (window / spend cap / TRAI) -> human review
                        # with reasons. Chup-chaap dead end kabhi nahi.
                        gate_reasons += list(v3["reasons"])
                        action, outcome = "human_review", "human_review"
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
                    outcome, link, exec_err = do_execute(fb)
                    if exec_err:
                        action = "human_review"
                        gate_reasons = gate_reasons + [exec_err]
                    else:
                        action, escalated_from = fb, proposed
                        escalation_kind = "gate_blocked"
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
                                    "escalated_from": escalated_from,
                                    "escalation_kind": escalation_kind})
        results.append({"txn": txn, "label": label,
                        "proposed_action": proposed, "action": action,
                        "escalated_from": escalated_from,
                        "escalation_kind": escalation_kind,
                        "allowed": verdict["allowed"], "outcome": outcome,
                        "reasons": gate_reasons, "failed_rules": failed_rules,
                        # `link` = executor ka artifact (mock ya real). Iski
                        # presence hi batati hai ki customer ke paas pay karne ka
                        # rasta bana ya nahi — metrics isi pe "actioned" ginta hai,
                        # action ke naam se guess nahi karta.
                        "link": link,
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
    ap.add_argument("--live", action="store_true",
                    help="Use the REAL Razorpay test-mode API for payment_link "
                         "actions (retries stay simulated). Needs .env keys.")
    ap.add_argument("--live-limit", type=int, default=1,
                    help="Max real payment links to create with --live "
                         "(default 1, 0 = no limit). Keeps the demo fast.")
    args = ap.parse_args()

    if args.live:
        # Pre-flight: keys missing / live key / SDK missing -> saaf error do,
        # chupke se dry-run par mat gir jao.
        ready, reason = executor.live_available()
        if not ready:
            raise SystemExit(f"--live refused: {reason}")
        print(f"[LIVE MODE] real Razorpay TEST-mode payment links "
              f"(limit={args.live_limit or 'none'}); retries stay simulated.")

    results, log = run(demo_hour=args.demo_hour,
                       show_notifications=args.show_notifications,
                       live=args.live, live_limit=args.live_limit)
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

    if args.live:
        # payment.all() bhi wired hai — yahi fields diagnoser ka raw material hain.
        print("\n  [LIVE] verifying payment.all() ...")
        try:
            items = executor.fetch_payments(count=5, dry_run=False)
            print(f"  [LIVE] payment.all() OK — {len(items)} payment(s) visible")
            for p in items:
                print(f"    {p.get('id')} {str(p.get('status')):<10} "
                      f"method={p.get('method')} error_code={p.get('error_code')}")
        except Exception as e:
            # Honest failure: batao, chhupao mat.
            print(f"  [LIVE] payment.all() FAILED — {type(e).__name__}: {e}")
