"""
decider.py — label -> PROPOSED action.

Ye sirf PROPOSE karta hai. Final allow/block policy_engine.check() karta hai.
Money decision deterministic hai (LLM nahi lega).
"""
import config


def propose(txn, label: str) -> str:
    """
    Label -> proposed action:
      soft      -> retry (within cap)
      hard      -> payment_link (+ later nudge)
      abandoned -> recovery_link (+ later nudge, within window)
      halted    -> payment_link, mark pending
      amount > AFA threshold OR mandate change -> human_review
    """
    # High-value / mandate-change cases: silent recovery mat propose karo.
    if txn.amount > config.AFA_THRESHOLD and label in ("soft", "halted"):
        return "human_review"

    return {
        "soft": "retry",
        "hard": "payment_link",
        "abandoned": "recovery_link",
        "halted": "payment_link",
    }.get(label, "human_review")
