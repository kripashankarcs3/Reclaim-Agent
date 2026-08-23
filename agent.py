"""
agent.py — LangGraph loop wrapping the SAME pipeline as run_batch.py.

Ye ek ADDITIONAL entry point hai, replacement NAHI:
  run_batch.py -> 54 seeded txns, sequential loop
  agent.py     -> ek event (webhook ya synthetic), same steps as graph nodes

Dono pipeline.py ke WAHI STEPS aur WAHI ROUTES use karte hain. Is file mein
koi business logic nahi hai — sirf (a) Razorpay event ko Transaction banana
aur (b) pipeline ke steps ko LangGraph nodes/edges mein wire karna.

Graph:

    detect -> diagnose -> decide -> gate
                                     |
                    allowed ---------+--------- blocked
                       |                           |
                    execute                     fallback
                       |                           |
        retry chala par recover nahi ---> (wapas GATE, ek hi baar)
                       |                           |
                     nudge                      escalate
                       |                           |
                       +--------> finalize <-------+

Gate par wapas jaane wala cycle hi structurally guarantee karta hai ki koi
fallback bina dobara check hue execute tak nahi pahunch sakta.

⚠️ INVARIANTS: LLM kabhi paisa nahi hilata; policy_engine hi refuse karta hai;
audit append-only; default offline (koi key/network nahi).
"""
import os
from datetime import datetime
from typing import Any, Dict, List, TypedDict

from langgraph.graph import END, StateGraph

import pipeline
import store as store_mod
from audit import AuditLog
from models import Transaction

# Ek hi append-only audit log + ek long-lived Ctx.
# Phase 6: attempt history aur contact tally ab SQLite mein hain, isliye ye
# process RESTART ke baad bhi zinda rehte hain — yahi wo gap tha jiski wajah se
# live webhook har event ko "attempt #1" samajh leta aur NPCI 1+3 / spend cap
# enforce hi nahi ho pate the.
DB_PATH = os.getenv("RECLAIM_DB", "reclaim.db")
AUDIT = AuditLog()
STORE = store_mod.Store(DB_PATH)
CTX = pipeline.Ctx(log=AUDIT, now=datetime.now(), store=STORE)


# --- Razorpay event -> Transaction -------------------------------------------

def txn_from_event(event: Dict[str, Any]) -> Transaction:
    """
    Razorpay-shaped event se Transaction banao.

    HONEST LIMITATION: `retry_count` aur `pre_debit_notice_sent` webhook payload
    mein hote hi nahi — wo hamare apne store se aane chahiye. Yahan inhe notes se
    padhte hain, warna 0/False. Matlab ek akela webhook NPCI 1+3 cap ko sahi
    enforce nahi kar sakta jab tak Phase 6 (persistence) attempt history na de.
    Isliye ye default rakha hai aur chhupaya nahi gaya.
    """
    etype = event.get("event", "")
    payload = event.get("payload", {}) or {}

    if "payment" in payload:
        e = (payload.get("payment") or {}).get("entity", {}) or {}
    elif "subscription" in payload:
        e = (payload.get("subscription") or {}).get("entity", {}) or {}
    else:
        e = {}

    notes = e.get("notes") or {}

    # Razorpay amount paise mein deta hai; hamara model rupees mein hai.
    amount_paise = e.get("amount")
    amount = int(amount_paise) // 100 if amount_paise is not None else int(notes.get("amount", 0))

    # Mandate-backed? Subscription charge pe token/invoice hota hai.
    is_sub = bool(e.get("token_id") or e.get("invoice_id")
                  or e.get("subscription_id")
                  or etype.startswith("subscription.")
                  or str(notes.get("is_subscription", "")).lower() in ("1", "true", "yes"))

    status = "halted" if etype.startswith("subscription.") else "failed"
    if str(notes.get("status", "")):
        status = str(notes["status"])

    return Transaction(
        id=e.get("id") or event.get("id") or "txn_event",
        order_id=e.get("order_id") or notes.get("order_id") or "order_event",
        amount=amount,
        method=e.get("method") or "unknown",
        status=status,
        customer_id=(e.get("customer_id") or notes.get("customer_id") or "cust_unknown"),
        is_subscription=is_sub,
        retry_count=int(notes.get("retry_count", 0)),
        error_code=e.get("error_code"),
        error_source=e.get("error_source"),
        error_step=e.get("error_step"),
        error_reason=e.get("error_reason"),
        pre_debit_notice_sent=str(notes.get("pre_debit_notice_sent", "")).lower()
        in ("1", "true", "yes"),
    )


# --- Graph: pipeline ke steps hi nodes hain --------------------------------

class GraphState(TypedDict, total=False):
    st: Dict[str, Any]          # pipeline.new_state() ka mutable state


def _node(name: str):
    """pipeline.STEPS[name] ko LangGraph node bana do (koi logic yahan nahi)."""
    step = pipeline.STEPS[name]

    def node(state: GraphState) -> GraphState:
        step(state["st"], CTX)
        return {"st": state["st"]}

    node.__name__ = f"node_{name}"
    return node


def _route(name: str):
    """pipeline.ROUTES[name] ko LangGraph conditional edge bana do."""
    route = pipeline.ROUTES[name]
    return lambda state: route(state["st"])


def build_graph():
    g = StateGraph(GraphState)
    for name in pipeline.STEPS:
        g.add_node(name, _node(name))

    g.set_entry_point("detect")
    g.add_edge("detect", "diagnose")
    g.add_edge("diagnose", "decide")
    g.add_conditional_edges("decide", _route("decide"),
                            {"gate": "gate", "escalate": "escalate"})
    g.add_conditional_edges("gate", _route("gate"),
                            {"execute": "execute", "fallback": "fallback",
                             "escalate": "escalate"})
    g.add_conditional_edges("execute", _route("execute"),
                            {"fallback": "fallback", "nudge": "nudge",
                             "finalize": "finalize"})
    g.add_conditional_edges("fallback", _route("fallback"),
                            {"gate": "gate", "escalate": "escalate"})
    g.add_edge("nudge", "finalize")
    g.add_edge("escalate", "finalize")
    g.add_edge("finalize", END)
    return g.compile()


GRAPH = build_graph()


# --- Public entry point -------------------------------------------------------

def handle_event(event: Dict[str, Any], now: datetime = None,
                 live: bool = False) -> List[Dict[str, Any]]:
    """
    Ek Razorpay-shaped event lo, graph chalao, us case ka audit timeline lauta do.
    Default offline: live=False -> executor dry-run, koi key/network nahi.
    """
    txn = txn_from_event(event)
    CTX.now = now or datetime.now()
    CTX.live = live
    GRAPH.invoke({"st": pipeline.new_state(txn)})
    return [{"stage": e.stage, "detail": e.detail} for e in AUDIT.timeline(txn.id)]


def reset_state() -> None:
    """Test/demo helper — persisted attempt history saaf karo.
    Audit log ko chhuta bhi nahi (append-only invariant intact)."""
    STORE.reset()
