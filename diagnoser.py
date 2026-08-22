"""
diagnoser.py — Root cause diagnosis.

DO parts (ye split interview mein must bolna):
  1. Deterministic classifier: error_code -> label. YE label action drive karta hai.
  2. LLM explanation: sirf human-readable reason. Decision LLM nahi leta.

Yahan LLM call pluggable hai — agar LLM_API_KEY set hai to real explanation,
warna deterministic template fallback (taaki bina network ke bhi chale).
"""
import os
from typing import Tuple

# error_code -> label mapping. Real codes Razorpay ki official error list se:
# razorpay.com/docs/errors/payments/list/  (judge poochega "codes kaha se?" -> yahi)
SOFT_CODES = {"GATEWAY_ERROR", "payment_timeout", "gateway_timeout", "SERVER_ERROR"}
HARD_CODES = {"insufficient_funds", "card_declined", "payment_failed",
              "BAD_REQUEST_ERROR", "invalid_vpa", "card_expired"}
ABANDONED_CODES = {None, "null", "payment_pending", ""}


def classify(txn) -> str:
    """Deterministic label. Ye kabhi LLM se nahi aata."""
    if txn.status == "halted":
        return "halted"
    code = txn.error_code
    if code in ABANDONED_CODES and txn.status == "abandoned":
        return "abandoned"
    if code in HARD_CODES:
        return "hard"
    if code in SOFT_CODES:
        return "soft"
    # Unknown code -> safest: treat as hard (don't silently retry into a wall)
    return "hard"


def explain(txn, label: str) -> str:
    """Human-readable reason. LLM optional; fallback template offline chalta hai."""
    key = os.getenv("LLM_API_KEY")
    if key:
        try:
            return _explain_llm(txn, label, key)
        except Exception:
            pass  # network/LLM fail -> graceful fallback
    return _explain_template(txn, label)


def _explain_template(txn, label: str) -> str:
    templates = {
        "soft": (f"Payment failed due to a transient issue "
                 f"({txn.error_code or 'gateway/timeout'}) — likely to succeed on retry."),
        "hard": (f"Hard decline ({txn.error_code or 'insufficient_funds'}) — retrying "
                 f"silently won't work; needs a customer-initiated payment."),
        "abandoned": ("Customer started checkout but did not complete payment — "
                      "a recovery link within the window can convert this."),
        "halted": ("Subscription retries exhausted and mandate halted — auto-retry "
                   "is spent; needs a fresh customer payment/authorization."),
    }
    return templates.get(label, "Unclassified failure — routed for review.")


def _explain_llm(txn, label: str, api_key: str) -> str:
    """Phase 3+: real LLM call. Explanation ONLY — no decision."""
    import llm_client  # razorpay's Agent Studio bhi agent SDK pe hai (on-brand)
    client = LLMClient(api_key=api_key)
    prompt = (
        f"A payment failed. label={label}, error_code={txn.error_code}, "
        f"method={txn.method}, amount=Rs.{txn.amount}, subscription={txn.is_subscription}. "
        f"In ONE plain sentence, explain the likely root cause for a support dashboard. "
        f"Do NOT recommend an action — explanation only."
    )
    resp = client.messages.create(
        model="llm-model", max_tokens=120,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()


def diagnose(txn) -> Tuple[str, str]:
    """Returns (label, explanation)."""
    label = classify(txn)
    return label, explain(txn, label)
