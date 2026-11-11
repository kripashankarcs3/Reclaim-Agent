"""
decider.py — label -> PROPOSED action.

Ye sirf PROPOSE karta hai. Final allow/block policy_engine.check() karta hai.

⚠️ Design rule (Phase 3.5) — decider ko "safe" banane ki koshish MAT karo.
Ye jaan-boojh kar NAIVE hai: sabse sasta/tempting recovery action propose karta
hai, chahe woh non-compliant ho. Refuse karna SIRF gate ka kaam hai.

Kyun: agar decider khud pehle se human_review kar de, to audit timeline mein
policy_check `allowed: True, failed_rules: []` dikhata hai — aur "the runtime
refuses, not the prompt" wala poora claim khokhla ho jata hai. Judge ko gate
ko REFUSE karte hue dikhna chahiye, decider ko dodge karte hue nahi.
"""
from typing import Optional, Iterable

import config


def propose(txn, label: str) -> str:
    """
    Cheapest tempting recovery action (koi safety check yahan NAHI):
      mandate-backed txn (subscription) -> retry   (mandate pe dobara present)
      soft (one-time)                   -> retry
      hard (bina mandate)               -> payment_link
      abandoned                         -> recovery_link

    Amount / retry cap / consent ka check yahan deliberately absent hai —
    woh policy_engine.check() ka kaam hai.
    """
    if txn.is_subscription and label in ("soft", "hard", "halted"):
        # Naive dunning engine yahi karta hai: NSF/hard decline pe bhi mandate
        # dobara present kar do. YEHI woh temptation hai jise gate rokta hai
        # (HARD_DECLINE / RETRY_CAP / AFA_THRESHOLD ek saath fire karte hain).
        return "retry"

    return {
        "soft": "retry",
        "hard": "payment_link",
        "abandoned": "recovery_link",
        "halted": "payment_link",
    }.get(label, "human_review")


def fallback(action: str, failed_rules: Iterable[str]) -> Optional[str]:
    """
    Gate ne debit block kar diya -> compliant alternative propose karo.

    Fallback SIRF tab jab saare failed rules "is debit attempt" ke baare mein
    hain (config.FALLBACK_ELIGIBLE_RULES). Agar koi bhi failed rule
    authorization ya contact-permission ka hai (config.HUMAN_ESCALATION_RULES)
    to koi automated fallback nahi — seedha human review.

    Note: ye bhi sirf PROPOSE karta hai. Fallback ko dobara gate se guzarna
    padta hai (run_batch/agent mein) — koi bypass nahi.
    """
    if action != "retry":
        return None                      # link/nudge ka koi sasta fallback nahi
    failed = list(failed_rules)
    if not failed:
        return None
    if any(r in config.HUMAN_ESCALATION_RULES for r in failed):
        return None                      # contact/authorization defect -> human
    if all(r in config.FALLBACK_ELIGIBLE_RULES for r in failed):
        return "payment_link"
    return None                          # anjaan rule -> fail safe, human review
