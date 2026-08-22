"""
main.py — FastAPI webhook receiver (Phase 5 target).

Real-time "revenue at risk" trigger. Do cheezein CRITICAL hain:
  1. Signature verify — warna koi bhi fake event bhej dega.
  2. Idempotency (x-razorpay-event-id) — Razorpay retries bhejta hai; duplicate ignore.

Run (after pip install fastapi uvicorn razorpay):
    uvicorn main:app --reload --port 8000
Phir ngrok se expose karke Razorpay dashboard -> Webhooks (Test mode) mein register.
"""
import os
from fastapi import FastAPI, Request, Header, HTTPException

app = FastAPI(title="ReclaimAgent")

_seen_event_ids = set()   # Phase 5: DB-backed idempotency store
WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")


@app.post("/webhook")
async def webhook(request: Request,
                  x_razorpay_signature: str = Header(default=""),
                  x_razorpay_event_id: str = Header(default="")):
    raw = await request.body()

    # 1) Signature verify
    if WEBHOOK_SECRET:
        try:
            import razorpay
            razorpay.Utility.verify_webhook_signature(
                raw.decode(), x_razorpay_signature, WEBHOOK_SECRET)
        except Exception:
            raise HTTPException(status_code=400, detail="invalid signature")

    # 2) Idempotency
    if x_razorpay_event_id in _seen_event_ids:
        return {"status": "duplicate_ignored"}
    _seen_event_ids.add(x_razorpay_event_id)

    event = await request.json()
    etype = event.get("event", "")

    # 3) Trigger the agent loop on relevant events
    if etype in ("payment.failed", "subscription.halted", "subscription.pending"):
        # from agent import handle_event   # LangGraph loop (Phase 5)
        # handle_event(event)
        return {"status": "queued", "event": etype}

    return {"status": "ignored", "event": etype}


@app.get("/health")
def health():
    return {"ok": True}
