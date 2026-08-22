"""
executor.py — the ONLY place jo Razorpay se baat karta hai.

Do modes, ek hi code path:
  dry_run=True   -> koi network call nahi. Deterministic mock. Offline spine
                    isi pe chalta hai (no keys, no network, byte-identical out).
  dry_run=False  -> real Razorpay TEST-mode call (razorpay SDK + .env keys).

SAFETY RAILS (ye jaan-boojh kar yahan hain, interview mein bolne layak):
  1. TEST KEYS ONLY. Agar key `rzp_live_` se start hui to executor REFUSE karta
     hai. Live key se ye agent kabhi chalega hi nahi — asli paisa move karne ka
     rasta hi band.
  2. NOTIFY OFF. payment_link.create mein `notify.sms/email` explicitly False
     aur `reminder_enable` False. Razorpay khud SMS/email bhej deta hai agar ye
     true ho — hamara invariant hai ki hum kabhi real notification nahi bhejte
     (notifications.py sirf template LOG karta hai).
  3. RETRIES ALWAYS SIMULATED. Live mode mein bhi hum asli recurring charge
     nahi maarte — sirf payment links real hain. Ye deliberate scope hai.
  4. Koi bhi live call fail hua to hum MOCK par fallback NAHI karte — error
     upar jata hai aur case human_review ban jata hai. Fake link kabhi nahi.

HONESTY (README mein bhi likha hai):
  - Standard Payment Links TEST mode mein kaam karte hain. **UPI Payment Links
    sirf LIVE mode mein** — isliye demo standard links pe design kiya hai.
    Agar UPI link chahiye to woh test mode mein banega hi nahi; hum use fake
    nahi karenge.
"""
import os
import time
from typing import Any, Dict, Optional, Tuple

import config

# .env se keys uthao (optional dependency — spine ko iski zaroorat nahi).
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:          # pragma: no cover - offline spine ko farak nahi padta
    pass

_client = None               # lazy singleton


# --- key / client plumbing ---------------------------------------------------

def _keys() -> Tuple[str, str]:
    return os.getenv("RAZORPAY_KEY_ID", ""), os.getenv("RAZORPAY_KEY_SECRET", "")


def _is_placeholder(value: str) -> bool:
    """.env.example ke dummy values ko 'unset' maano (rzp_test_xxxxxxxx etc.)."""
    v = (value or "").strip().lower()
    return (not v) or ("xxxx" in v) or v.endswith("_here") or v in ("changeme", "todo")


def live_available() -> Tuple[bool, str]:
    """(ready, reason). --live se pehle isse check karo — clear error do."""
    key_id, key_secret = _keys()
    if not key_id or not key_secret:
        return False, ("RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET not set. "
                       "Copy .env.example -> .env and fill your test keys.")
    if _is_placeholder(key_id) or _is_placeholder(key_secret):
        return False, ("RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET still hold the "
                       ".env.example placeholders — paste your real rzp_test_ keys.")
    if key_id.startswith("rzp_live_"):
        return False, ("REFUSED: live key detected. ReclaimAgent only runs "
                       "against rzp_test_ keys.")
    if not key_id.startswith("rzp_test_"):
        return False, f"REFUSED: key_id does not look like a test key ({key_id[:12]}...)."
    try:
        import razorpay  # noqa: F401
    except ImportError:
        return False, "razorpay SDK not installed. Run: pip install razorpay"
    return True, ""


def client():
    """Razorpay client — sirf tab banta hai jab live call actually chahiye."""
    global _client
    if _client is None:
        ready, reason = live_available()
        if not ready:
            raise RuntimeError(reason)
        import razorpay
        key_id, key_secret = _keys()
        _client = razorpay.Client(auth=(key_id, key_secret))
    return _client


# --- the two real primitives -------------------------------------------------

def create_payment_link(txn, dry_run: bool = True) -> Dict[str, Any]:
    """
    Recovery ke liye pre-filled payment link.
    dry_run=True -> deterministic mock (offline spine).
    """
    if dry_run:
        return {"id": f"plink_{txn.id}", "status": "created",
                "short_url": f"https://rzp.io/i/mock-{txn.id}", "live": False}

    payload = {
        "amount": int(txn.amount) * 100,          # Razorpay paise leta hai
        "currency": config.CURRENCY,
        "description": f"Recovery for {txn.order_id}",
        # Razorpay duplicate reference_id reject karta hai — isliye run-unique
        # suffix, warna dobara --live chalane pe call fail ho jayegi.
        "reference_id": f"reclaim-{txn.id}-{int(time.time())}",
        # INVARIANT: hum kabhi real notification nahi bhejte. Dono False.
        "notify": {"sms": False, "email": False},
        "reminder_enable": False,
        "notes": {"txn_id": txn.id, "order_id": txn.order_id,
                  "source": "ReclaimAgent"},
    }
    resp = client().payment_link.create(payload)
    return {"id": resp.get("id"), "status": resp.get("status"),
            "short_url": resp.get("short_url"),
            "reference_id": resp.get("reference_id"), "live": True}


def fetch_payments(count: int = 5, dry_run: bool = True) -> list:
    """
    payment.all() — batch build karne aur live wiring verify karne ke liye.
    Yahi fields (error_code/error_source/error_step) diagnoser ka raw material hain.
    """
    if dry_run:
        return []
    resp = client().payment.all({"count": count})
    return resp.get("items", [])


def retry_charge(txn, dry_run: bool = True) -> Dict[str, Any]:
    """
    ALWAYS SIMULATED — live mode mein bhi. Hum asli recurring debit nahi maarte.
    TODO(Phase 5): real subscription re-charge, tab bhi policy_engine.check()
    ke baad hi, aur pehle test-mode subscription seed karke.
    """
    return {"id": f"pay_retry_{txn.id}", "status": "attempted", "simulated": True}


def refund(payment_id: str, amount: int, dry_run: bool = True) -> Dict[str, Any]:
    if dry_run:
        return {"id": f"rfnd_{payment_id}", "status": "processed", "live": False}
    resp = client().payment.refund(payment_id, {"amount": int(amount) * 100})
    return {"id": resp.get("id"), "status": resp.get("status"), "live": True}


# --- unified execution seam --------------------------------------------------

def execute(action: str, txn, dry_run: bool = True) -> Tuple[str, Optional[Dict]]:
    """
    Ek hi execution path — run_batch aur (Phase 5) agent dono yahi call karte hain.
    Returns: (outcome, artifact_or_None)

    NOTE: `dry_run` sirf PAYMENT LINKS pe lagta hai. Retry har haal mein
    simulated hai (upar rail #3 dekho).
    """
    if action == "retry":
        retry_charge(txn)
        # Soft declines mostly recover on retry (deterministic by id parity)
        outcome = "recovered" if int(txn.id.split("_")[1]) % 3 != 0 else "pending"
        return outcome, None
    if action in ("payment_link", "recovery_link"):
        link = create_payment_link(txn, dry_run=dry_run)   # link banana = koi contact NAHI
        return "pending", link                             # customer action pending
    return "not_attempted", None


if __name__ == "__main__":
    # Chhota self-check: `python executor.py` -> sirf key status batata hai
    # (koi network call nahi). `python executor.py --ping` -> ek live read.
    import sys
    ready, reason = live_available()
    print(f"live_available: {ready}" + ("" if ready else f"  ({reason})"))
    if ready and "--ping" in sys.argv:
        items = fetch_payments(count=3, dry_run=False)
        print(f"payment.all() OK — {len(items)} payment(s) visible in test mode")
        for p in items:
            print(f"  {p.get('id')} {p.get('status'):<10} "
                  f"error_code={p.get('error_code')}")
