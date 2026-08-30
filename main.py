"""
main.py — FastAPI webhook receiver + read-only dashboard API (Phase 7 Half A).

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

DASHBOARD API (Phase 7 Half A) — sab READ-ONLY hain, koi endpoint kisi bhi
core decision-path ko chhoo nahi sakta:
  GET /api/metrics       -> ek FRESH throwaway batch (jaisa run_batch.py karta
                            hai) chala ke honest metrics.
  GET /api/cases         -> batch ke 54 cases + persisted store ke live cases
                            (source: "batch" ya "live").
  GET /api/case/{txn_id} -> ek case ka POORA audit timeline (star panel).
  GET /api/policy-stats  -> saare active guardrail rules + batch mein kitni
                            baar fire hue.

Har dashboard endpoint apna khud ka `:memory:` store use karta hai (bilkul
run_batch.run() jaisa) — durable webhook DB (`agent.STORE` / `reclaim.db`)
kabhi likha nahi jata, sirf `agent.STORE` se LIVE cases padhe jaate hain.

CORS (Phase 7 Half B): sirf Vite dev server ke origins allow hain, wildcard
NAHI — ye backend ek webhook secret rakhta hai, isliye har origin ko API
khol dena galat hoga. Ye sirf LOCAL DEV ke liye hai; production mein dashboard
ko isi backend se serve karna behtar hoga (tab CORS ki zaroorat hi nahi).

Run:
    uvicorn main:app --reload --port 8000
Baad mein ngrok se expose karke Razorpay dashboard -> Webhooks (Test mode).
"""
import json
import os
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

import agent
import config
import metrics
import policy_engine
import run_batch

app = FastAPI(title="ReclaimAgent")

# Sirf local Vite dev server — wildcard nahi, is backend ke paas webhook
# secret hai. GET-only dashboard hai, par phir bhi origin scope karna sahi hai.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

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


# ============================================================================
# DASHBOARD API (Phase 7, Half A) — read-only, no core logic here
# ============================================================================

def _fresh_batch():
    """
    run_batch.run() jaisa hi call — apna khud ka `:memory:` store banata hai
    (pipeline.Ctx default), durable `reclaim.db` ko kabhi chhoo ta nahi.
    Deterministic hai, isliye har call same result deta hai — parallel
    /api/metrics aur /api/cases requests kabhi disagree nahi karenge.
    """
    return run_batch.run()


def _case_summary(r: Dict[str, Any]) -> Dict[str, Any]:
    """Ek batch result ko dashboard-friendly summary mein badlo."""
    txn = r["txn"]
    return {
        "id": txn.id,
        "order_id": txn.order_id,
        "amount": txn.amount,
        "method": txn.method,
        "label": r["label"],
        "action": r["action"],
        "outcome": r["outcome"],
        "failed_rules": r.get("failed_rules", []),
        "source": "batch",
    }


def _live_case_summary(txn_id: str, order_id: Optional[str]) -> Dict[str, Any]:
    """
    Ek LIVE (webhook) case ka summary — persisted audit_log se reconstruct
    karte hain, kyunki store sirf audit ROWS rakhta hai, koi alag "cases"
    table nahi (aur banane ki zaroorat nahi thi — audit hi source of truth hai).

    HONEST LIMITATION: `method` yahan hamesha None hoga. pipeline.detect()
    apne audit detail mein status/amount/error_code hi likhta hai, method
    nahi — isliye persisted trail se wo field reconstruct nahi ho sakta.
    Batch cases mein `method` hai kyunki wo seedha Transaction object se aata
    hai, audit JSON se nahi. Isse chupaya nahi ja raha — dashboard mein
    `method: null` dikhega live cases ke liye jab tak koi is field ko
    detect()'s log call mein add na kare (jo core-logic-touching change hai,
    isliye Half A ke scope se bahar rakha).
    """
    entries = agent.case_timeline(txn_id)
    amount = None
    label = None
    outcome = None
    action = None
    failed_rules: List[str] = []
    for e in entries:
        stage, detail = e["stage"], e["detail"]
        if stage == "detect":
            amount = detail.get("amount")
        elif stage == "diagnose":
            label = detail.get("label")
        elif stage == "policy_check":
            if detail.get("allowed") is False:
                for fr in detail.get("failed_rules", []):
                    if fr not in failed_rules:
                        failed_rules.append(fr)
            # `nudge` ka apna policy_check hamesha asli `execute` ke BAAD aata
            # hai (link banne ke baad hi nudge propose hota hai) — usse
            # `action` ko "nudge" se overwrite nahi karne dena, warna case ka
            # asli action (payment_link/retry) gum ho jata hai.
            checked = detail.get("action")
            if checked != "nudge":
                action = checked
        elif stage == "execute":
            action = detail.get("action")            # actually executed action — authoritative
        elif stage == "outcome":
            outcome = detail.get("outcome")
            if outcome == "human_review":
                action = "human_review"

    return {
        "id": txn_id,
        "order_id": order_id,
        "amount": amount,
        "method": None,          # dekho docstring — audit trail mein hai hi nahi
        "label": label,
        "action": action,
        "outcome": outcome,
        "failed_rules": failed_rules,
        "source": "live",
    }


@app.get("/api/metrics")
def api_metrics():
    """
    Ek FRESH throwaway batch chala ke honest metrics. recovered aur actioned
    HAMESHA alag rehte hain (metrics.compute() khud kabhi jodta nahi) —
    dashboard bhi inhe kabhi sum na kare.
    """
    results, _log = _fresh_batch()
    return metrics.compute(results)


@app.get("/api/cases")
def api_cases():
    """
    Batch ke 54 cases + persisted store ke live (webhook) cases, ek hi list
    mein — har entry `source: "batch"` ya `source: "live"` carry karta hai.
    """
    results, _log = _fresh_batch()
    cases = [_case_summary(r) for r in results]
    for txn_id, order_id in agent.STORE.list_cases():
        cases.append(_live_case_summary(txn_id, order_id))
    return {"count": len(cases), "cases": cases}


@app.get("/api/case/{txn_id}")
def api_case(txn_id: str):
    """
    Ek case ka POORA audit timeline — star panel isi pe banega.

    Pehle LIVE store check karte hain (durable, real webhook delivery ka
    proof), phir batch mein dhoondte hain (fresh run, deterministic). Store ko
    priority isliye milti hai: agar wahi id kabhi live bhi aaya ho, wo asli
    event hai — batch sirf synthetic demo data hai.
    """
    live = agent.case_timeline(txn_id)
    if live:
        return {"txn_id": txn_id, "source": "live", "timeline": live}

    results, log = _fresh_batch()
    if any(r["txn"].id == txn_id for r in results):
        timeline = [{"stage": e.stage, "detail": e.detail}
                    for e in log.timeline(txn_id)]
        return {"txn_id": txn_id, "source": "batch", "timeline": timeline}

    raise HTTPException(status_code=404, detail=f"no case found for txn_id={txn_id}")


@app.get("/api/policy-stats")
def api_policy_stats():
    """
    Active guardrail rules (policy_engine.check() se, hardcoded copy nahi —
    docstrings seedha function object se padhte hain) + batch mein har rule
    kitni baar fire hui (metrics.compute()'s gate_blocks_by_rule).
    """
    rule_funcs = {
        "RETRY_CAP": policy_engine.rule_retry_cap,
        "HARD_DECLINE": policy_engine.rule_hard_decline,
        "MANDATE_REQUIRED": policy_engine.rule_mandate_required,
        "AFA_THRESHOLD": policy_engine.rule_afa_threshold,
        "PRE_DEBIT_NOTICE": policy_engine.rule_pre_debit_notice,
        "CONTACT_WINDOW": policy_engine.rule_contact_window,
        "TRAI_MESSAGING": policy_engine.rule_trai_messaging,
        "SPEND_CAP": policy_engine.rule_spend_cap,
    }
    results, _log = _fresh_batch()
    fired = metrics.compute(results)["gate_blocks_by_rule"]
    rules = [
        {"rule": name,
         "description": (fn.__doc__ or "").strip().splitlines()[0] if fn.__doc__ else "",
         "fired_in_batch": fired.get(name, 0)}
        for name, fn in rule_funcs.items()
    ]
    return {"rules": rules}
