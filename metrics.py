"""
metrics.py — Honest, aggregate metrics over the whole batch.

Track 03 bar: "measured money recovered across a batch... one cherry-picked
match proves nothing." Isliye ye aggregate + exception list + false-positive
cost deta hai. False-positive cost dikhana = tum mature ho (sirf "recover" nahi).
"""
from collections import Counter
from typing import List, Dict


def compute(results: List[Dict]) -> Dict:
    """
    results: har txn ke liye ek dict:
      {txn, label, proposed_action, action, escalated_from, allowed,
       outcome, reasons, failed_rules, nudge}
      outcome in: recovered / pending / human_review / not_attempted
    """
    total_at_risk = sum(r["txn"].amount for r in results)
    recovered_val = sum(r["txn"].amount for r in results if r["outcome"] == "recovered")

    # Diagnoser precision: predicted label == ground-truth label
    labelled = [r for r in results if r["txn"].gt_label is not None]
    correct = sum(1 for r in labelled if r["label"] == r["txn"].gt_label)
    precision = correct / len(labelled) if labelled else 0.0

    # False-positive cost:
    #  (a) blocks we correctly avoided (compliance saves) — good
    #  (b) actions taken on txns whose ground truth said should_recover=False — bad
    # NOTE: "blocked" ab terminal outcome nahi hai — gate-blocked debit ya to
    # compliant fallback pe escalate hota hai, ya human_review banta hai.
    compliance_blocks_avoided = sum(1 for r in results if r["outcome"] == "human_review")
    wrong_actions = sum(
        1 for r in results
        if r["txn"].gt_should_recover is False and r["outcome"] in ("recovered", "pending")
    )

    by_cause: Dict[str, Dict] = {}
    for r in results:
        c = by_cause.setdefault(r["label"], {"count": 0, "recovered": 0, "value": 0})
        c["count"] += 1
        c["value"] += r["txn"].amount
        if r["outcome"] == "recovered":
            c["recovered"] += 1

    # Gate-produced refusals: kaunsa rule kitni baar fire hua.
    # (Phase 3.5: refusal ab decider ke short-circuit se nahi, gate se aata hai.)
    gate_blocks_by_rule = Counter()
    for r in results:
        gate_blocks_by_rule.update(r.get("failed_rules", []))

    # Blocked debit -> compliant payment link pe escalate hue kitne case.
    escalated_to_link = sum(1 for r in results if r.get("escalated_from"))

    # Nudges: bheje kitne, aur policy ne kitne rok diye (over-contact bacha).
    nudges_sent = sum(1 for r in results
                      if (r.get("nudge") or {}).get("status") == "sent")
    nudges_suppressed = sum(1 for r in results
                            if (r.get("nudge") or {}).get("status") == "suppressed")

    by_action: Dict[str, int] = {}
    for r in results:
        by_action[r["action"]] = by_action.get(r["action"], 0) + 1

    exceptions = [
        {"txn": r["txn"].id, "amount": r["txn"].amount, "label": r["label"],
         "proposed": r.get("proposed_action"), "outcome": r["outcome"],
         "reasons": r["reasons"]}
        for r in results if r["outcome"] in ("human_review", "not_attempted")
    ]

    return {
        "total_txns": len(results),
        "total_at_risk": total_at_risk,
        "recovered_value": recovered_val,
        "recovery_rate_pct": round(100 * recovered_val / total_at_risk, 1) if total_at_risk else 0,
        "diagnoser_precision_pct": round(100 * precision, 1),
        "compliance_blocks_avoided": compliance_blocks_avoided,
        "gate_blocks_by_rule": dict(gate_blocks_by_rule),
        "escalated_to_link": escalated_to_link,
        "nudges_sent": nudges_sent,
        "nudges_suppressed": nudges_suppressed,
        "wrong_actions_false_positive": wrong_actions,
        "by_cause": by_cause,
        "by_action": by_action,
        "exception_list": exceptions,
    }


def print_report(m: Dict) -> None:
    print("\n" + "=" * 60)
    print("  RECLAIMAGENT — BATCH METRICS")
    print("=" * 60)
    print(f"  Transactions processed : {m['total_txns']}")
    print(f"  Total at-risk          : Rs.{m['total_at_risk']:,}")
    print(f"  Recovered              : Rs.{m['recovered_value']:,} ({m['recovery_rate_pct']}%)")
    print(f"  Diagnoser precision    : {m['diagnoser_precision_pct']}%")
    print(f"  Compliance blocks (good): {m['compliance_blocks_avoided']}")
    print(f"  Wrong actions (FP cost) : {m['wrong_actions_false_positive']}")
    print(f"  Blocked debit -> link    : {m['escalated_to_link']} (compliant escalation)")
    print(f"  Nudges sent / suppressed : {m['nudges_sent']} / {m['nudges_suppressed']}")
    print("\n  Gate blocks by rule (every refusal comes from policy_engine):")
    for rule, n in sorted(m["gate_blocks_by_rule"].items(),
                          key=lambda kv: -kv[1]):
        print(f"    {rule:<18} {n}")
    print("\n  Recovery by root cause:")
    for cause, c in m["by_cause"].items():
        print(f"    {cause:<10} count={c['count']:<3} recovered={c['recovered']:<3} value=Rs.{c['value']:,}")
    print("\n  Actions taken:")
    for a, n in m["by_action"].items():
        print(f"    {a:<16} {n}")
    print(f"\n  EXCEPTION LIST ({len(m['exception_list'])} cases could not be auto-recovered):")
    for ex in m["exception_list"][:12]:
        reasons = "; ".join(ex["reasons"]) if ex["reasons"] else ex["outcome"]
        print(f"    {ex['txn']} (Rs.{ex['amount']:,}, {ex['label']}) -> {ex['outcome']}: {reasons}")
    print("=" * 60)
