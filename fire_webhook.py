"""
fire_webhook.py — demo helper: signed `payment.failed` webhook bhejta hai.

Dashboard par zinda bharne ke liye: jab tak koi event fire nahi karta, feed
sirf seeded batch dikhata hai (static lagta hai). Ye script ek REAL,
signature-verified webhook delivery simulate karta hai — main.py ka
`signature_ok()` check ise tabhi accept karega jab HMAC sahi ho.

Run:
    python fire_webhook.py            # ek soft failed payment (nudge + pending)
    python fire_webhook.py --hard     # hard insufficient_funds -> block + needs-a-human
    python fire_webhook.py --halted   # subscription.halted (mandate exhausted)
    python fire_webhook.py --many 3   # 3 distinct events, 1 sec apart

Har naya event feed mein `source: live` ke saath aata hai — wahi "real-time"
ka proof demo ka. Signatures .env ke RAZORPAY_WEBHOOK_SECRET se bante hain.
"""
import argparse
import hashlib
import hmac
import json
import os
import time
import urllib.request

import dotenv

dotenv.load_dotenv()
BASE = "http://127.0.0.1:8000"


def _secret() -> str:
    secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "").strip()
    if not secret:
        raise SystemExit("RAZORPAY_WEBHOOK_SECRET missing in .env")
    return secret


def _sign(raw: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()


def event_for(kind: str, seq: int) -> tuple[dict, str]:
    if kind == "hard":
        etype = "payment.failed"
        entity = {
            "id": f"pay_live_hard_{seq}",
            "order_id": f"order_live_hard_{seq}",
            "amount": 25000_00,
            "method": "upi",
            "error_code": "insufficient_funds",
            "error_source": "bank",
            "error_step": "payment_authentication",
            "error_reason": "Your bank account has insufficient funds.",
            "notes": {"customer_id": f"cust_live_{seq}",
                      "retry_count": "3",
                      "amount": "25000",
                      "order_id": f"order_live_hard_{seq}"},
        }
    elif kind == "halted":
        etype = "subscription.halted"
        entity = {
            "id": f"pay_live_halt_{seq}",
            "order_id": f"order_live_halt_{seq}",
            "amount": 4999_00,
            "method": "card",
            "subscription_id": f"sub_live_{seq}",
            "error_code": "mandate_bank_creation_failed",
            "notes": {"customer_id": f"cust_live_{seq}",
                      "retry_count": "0",
                      "amount": "4999",
                      "order_id": f"order_live_halt_{seq}",
                      "is_subscription": "true"},
        }
    else:
        etype = "payment.failed"
        entity = {
            "id": f"pay_live_soft_{seq}",
            "order_id": f"order_live_soft_{seq}",
            "amount": 2999_00,
            "method": "card",
            "error_code": "payment_timeout",
            "error_source": "gateway",
            "error_step": "payment_gateway",
            "error_reason": "Your payment attempt timed out.",
            "notes": {"customer_id": f"cust_live_{seq}",
                      "retry_count": "0",
                      "amount": "2999",
                      "order_id": f"order_live_soft_{seq}"},
        }
    event = {
        "entity": "event",
        "account_id": "acc_test_live_demo",
        "event": etype,
        "contains": ["payment"],
        "payload": {"payment": {"entity": entity}},
        "created_at": int(time.time()),
    }
    event_id = f"evt_live_{kind}_{seq}"
    return event, event_id


def fire(event: dict, event_id: str, secret: str) -> None:
    raw = json.dumps(event).encode()
    sig = _sign(raw, secret)
    req = urllib.request.Request(
        f"{BASE}/webhook",
        data=raw,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": sig,
            "X-Razorpay-Event-Id": event_id,
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            body = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = {"http_error": e.code, "detail": e.read().decode()}
    print(f"[{event_id}] {body}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=["soft", "hard", "halted"], default="soft")
    ap.add_argument("--many", type=int, default=1)
    args = ap.parse_args()

    secret = _secret()
    for i in range(1, args.many + 1):
        event, event_id = event_for(args.kind, i)
        fire(event, event_id, secret)
        if i < args.many:
            time.sleep(1)


if __name__ == "__main__":
    main()