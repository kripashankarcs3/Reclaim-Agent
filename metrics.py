"""
metrics.py — Honest, aggregate metrics over the whole batch.

Track 03 bar: "measured money recovered across a batch... one cherry-picked
match proves nothing." Isliye ye aggregate + exception list + false-positive
cost deta hai. False-positive cost dikhana = tum mature ho (sirf "recover" nahi).
"""
from typing import List, Dict


def compute(results: List[Dict]) -> Dict:
    """
    results: har txn ke liye ek dict:
      {txn, label, action, allowed, outcome, reasons}
      outcome in: recovered / pending / blocked / human_review / not_attempted
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
    compliance_blocks_avoided = sum(1 for r in results if r["outcome"] in ("blocked", "human_review"))
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

    by_action: Dict[str, int] = {}
    for r in results:
        by_action[r["action"]] = by_action.get(r["action"], 0) + 1

    exceptions = [
        {"txn": r["txn"].id, "amount": r["txn"].amount, "label": r["label"],
         "outcome": r["outcome"], "reasons": r["reasons"]}
        for r in results if r["outcome"] in ("blocked", "human_review", "not_attempted")
    ]

    return {
        "total_txns": len(results),
        "total_at_risk": total_at_risk,
        "recovered_value": recovered_val,
        "recovery_rate_pct": round(100 * recovered_val / total_at_risk, 1) if total_at_risk else 0,
        "diagnoser_precision_pct": round(100 * precision, 1),
        "compliance_blocks_avoided": compliance_blocks_avoided,
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
