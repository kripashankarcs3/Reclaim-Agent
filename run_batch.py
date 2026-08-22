"""
run_batch.py — Poore batch ko pipeline se chalata hai (deterministic).

Ye Phase 5 ke LangGraph agent ka pure-Python version hai — same flow:
  detect -> diagnose -> decide(propose) -> policy_engine.check
         -> allowed?  execute
         -> blocked?  compliant fallback propose -> check AGAIN
         -> phir bhi blocked? human_review (gate ke reasons ke saath)
  link bana? -> nudge ALAG action hai -> ALAG gate check -> mocked TRAI template

Ye file ab sirf ek THIN LOOP hai: batch generate karo, har txn ko
pipeline.process_txn() se chalao, results metrics ko do. Asli flow (steps +
routing) pipeline.py mein hai — wahi agent.py bhi use karta hai.

Isse tum bina Razorpay keys / webhooks ke bhi WINNING SPINE chala sakte ho.
Executor default DRY-RUN hai (--live se real test-mode links).

Run:  python run_batch.py
      python run_batch.py --demo-hour 21        # 9 PM -> contact-window blocks
      python run_batch.py --show-timeline txn_046
      python run_batch.py --show-notifications  # mocked TRAI templates print karo
"""
import argparse
from datetime import datetime

import seed
import pipeline
from audit import AuditLog
import metrics


def run(demo_hour=14, show_notifications=False, live=False, live_limit=1):
    """
    demo_hour: 'current time' force karne ke liye (window rule demo).
    live:      payment_link actions REAL Razorpay test-mode API se banao.
               (Retries phir bhi simulated — executor.py rail #3 dekho.)
    live_limit: max kitne real link banayenge (0 = unlimited). Demo ko fast
               rakhne ke liye — invariant: live call pe demo stall nahi hona chahiye.

    Poora per-txn flow pipeline.py mein hai — wahi implementation agent.py bhi
    use karta hai, taaki batch aur webhook path kabhi alag na ho jayein.
    """
    now = datetime.now().replace(hour=demo_hour, minute=30)
    log = AuditLog()
    ctx = pipeline.Ctx(log=log, now=now, live=live, live_limit=live_limit,
                       show_notifications=show_notifications,
                       messaging_state=seed.messaging_state)
    results = [pipeline.process_txn(txn, ctx) for txn in seed.generate()]
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
