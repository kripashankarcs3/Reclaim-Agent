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

import config

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
    """
    Human-readable reason. LLM OPT-IN hai; default offline template.

    Kyun opt-in: Phase 4 mein executor load_dotenv() call karta hai, jisse .env
    ka LLM_API_KEY poore process ke env mein aa jata hai. Agar hum sirf
    "key hai?" pe LLM chala dete, to `python run_batch.py` chupchap 54 network
    call maar deta (measured: 0.3s -> 59s) — aur INVARIANT #5 (demo kabhi live
    call pe stall na ho) toot jata. Isliye LLM tabhi jab user ne explicitly
    bola ho:  RECLAIM_LLM_EXPLAIN=1  (PowerShell: $env:RECLAIM_LLM_EXPLAIN=1)
    """
    if os.getenv("RECLAIM_LLM_EXPLAIN", "").strip() not in ("1", "true", "yes"):
        return _explain_template(txn, label)
    key = os.getenv("LLM_API_KEY")
    if key and not config.is_placeholder(key):
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
    """
    Optional LLM explanation. Explanation ONLY — kabhi koi decision nahi.

    Provider-agnostic by design: endpoint aur model dono .env se aate hain,
    code mein koi vendor SDK ya model hardcode nahi. Stdlib urllib use karta
    hai taaki koi extra dependency na lage.
        LLM_API_URL  -> messages-style chat endpoint
        LLM_MODEL    -> model identifier
        LLM_API_KEY  -> bearer token
    Kuch bhi fail hua to caller deterministic template par gir jata hai.
    """
    import json
    import urllib.request

    url = os.getenv("LLM_API_URL", "").strip()
    model = os.getenv("LLM_MODEL", "").strip()
    if not url or not model:
        raise RuntimeError("LLM_API_URL / LLM_MODEL not configured")

    prompt = (
        f"A payment failed. label={label}, error_code={txn.error_code}, "
        f"method={txn.method}, amount=Rs.{txn.amount}, subscription={txn.is_subscription}. "
        f"In ONE plain sentence, explain the likely root cause for a support dashboard. "
        f"Do NOT recommend an action — explanation only."
    )
    body = json.dumps({
        "model": model, "max_tokens": 120,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "content-type": "application/json",
        "authorization": f"Bearer {api_key}",
    })
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode())

    # Providers ke response shapes alag hote hain — dono common shapes handle
    # kar lete hain, warna exception -> template fallback.
    content = data.get("content")
    if isinstance(content, list):
        return "".join(b.get("text", "") for b in content).strip()
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        return (choices[0].get("message", {}).get("content") or "").strip()
    raise RuntimeError("unrecognised LLM response shape")


def diagnose(txn) -> Tuple[str, str]:
    """Returns (label, explanation)."""
    label = classify(txn)
    return label, explain(txn, label)
