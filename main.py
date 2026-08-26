"""
main.py — FastAPI webhook receiver. Real-time "revenue at risk" trigger.

Flow: POST /webhook -> signature verify -> idempotency claim -> agent.handle_event
      -> us case ka audit timeline JSON mein wapas.

TEEN cheezein CRITICAL hain, teeno yahan hain:

1. SIGNATURE VERIFY — aur ye FAIL-CLOSED hai.
   Pehle code `if WEBHOOK_SECRET:` karta tha, yaani secret set na ho to
   verification SKIP ho jati thi aur koi bhi banda fake `payment.failed` bhej
   kar agent se paise wale actions karwa sakta tha. Ab secret na ho (ya
   .env.example ka placeholder ho) to endpoint 503 deta hai — unverified event
   kabhi process nahi hota.

2. IDEMPOTENCY (x-razorpay-event-id) — ab DB-backed (store.seen_events).
   Razorpay same event dobara bhejta hai. Pehle ye ek in-memory set tha jo
   restart par bhool jata; retry dobara process ho jata aur customer ko dobara
   link/nudge chala jata. Ab claim_event() atomic hai aur restart ke baad bhi
   yaad rehta hai.

   TRADEOFF (jaan-boojh kar): hum event id ko process karne se PEHLE claim
   karte hain (at-most-once). Agar processing beech mein crash ho gayi to wo
   event dobara process nahi hoga. Paise wale system mein "ek baar miss" karna
   "do baar charge" karne se behtar hai. Missed events reconciliation se
   pakde jayenge (payment.all()), duplicate charge nahi pakda ja sakta.

3. RETRY HISTORY PAYLOAD SE NAHI AATI.
   Razorpay ke webhook mein `retry_count` / `pre_debit_notice_sent` hote hi
   nahi. Wo store.py se aate hain (pipeline.detect -> ctx.hydrate), isliye NPCI
   1+3 aur pre-debit rules yahan sach mein enforce hote hain.

Run:
    uvicorn main:app --reload --port 8000
Baad mein ngrok se expose karke Razorpay dashboard -> Webhooks (Test mode).
"""
import json
import os

from fastapi import FastAPI, Header, HTTPException, Request

import agent
import config

app = FastAPI(title="ReclaimAgent")

# Sirf ye events recovery loop trigger karte hain.
RECOVERY_EVENTS = {"payment.failed", "subscription.halted", "subscription.pending"}


def _webhook_secret() -> str:
    """
    Har request par padho, import ke waqt nahi — kyunki .env `agent` import
    hone par load hoti hai, aur module-level read us se pehle chal jata.
    """
    return os.getenv("RAZORPAY_WEBHOOK_SECRET", "").strip()


def signature_ok(raw: bytes, signature: str, secret: str) -> bool:
    """
    Razorpay ka apna verifier: HMAC-SHA256 hex over the RAW body, constant-time
    compare. Mismatch par SDK exception raise karta hai, isliye catch karke
    False lautate hain. (SDK na ho to same algorithm stdlib se.)
    """
    if not signature:
        return False
    try:
        import razorpay
        razorpay.Utility().verify_webhook_signature(raw.decode(), signature, secret)
        return True
    except ImportError:
        import hashlib
        import hmac
        expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)
    except Exception:
        return False


@app.post("/webhook")
async def webhook(request: Request,
                  x_razorpay_signature: str = Header(default=""),
                  x_razorpay_event_id: str = Header(default="")):
    raw = await request.body()

    # 1) SIGNATURE — fail closed.
    secret = _webhook_secret()
    if config.is_placeholder(secret):
        raise HTTPException(
            status_code=503,
            detail="RAZORPAY_WEBHOOK_SECRET not configured — refusing to process "
                   "unverified events")
    if not signature_ok(raw, x_razorpay_signature, secret):
        raise HTTPException(status_code=400, detail="invalid signature")

    # 2) IDEMPOTENCY — DB-backed, restart ke baad bhi yaad.
    if not x_razorpay_event_id:
        raise HTTPException(status_code=400, detail="missing x-razorpay-event-id")
    if not agent.STORE.claim_event(x_razorpay_event_id):
        return {"status": "duplicate_ignored", "event_id": x_razorpay_event_id}

    try:
        event = json.loads(raw)
    except ValueError:
        raise HTTPException(status_code=400, detail="malformed JSON body")

    etype = event.get("event", "")
    if etype not in RECOVERY_EVENTS:
        return {"status": "ignored", "event": etype}

    # 3) AGENT LOOP — retry history store se aati hai, payload se nahi.
    txn = agent.txn_from_event(event)
    timeline = agent.handle_event(event)
    return {"status": "processed", "event": etype, "event_id": x_razorpay_event_id,
            "txn_id": txn.id, "order_id": txn.order_id, "timeline": timeline}


@app.get("/health")
def health():
    """Secret configured hai ya nahi — value kabhi expose nahi karte."""
    return {"ok": True,
            "webhook_secret_configured": not config.is_placeholder(_webhook_secret())}
