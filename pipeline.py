"""
pipeline.py — EK transaction ka poora recovery flow, ek hi jagah.

Ye single source of truth hai. Do entry points isse call karte hain:
  run_batch.py -> 54 seeded txns par loop (offline batch)
  agent.py     -> ek webhook event par LangGraph graph

Pehle ye logic dono files mein copy tha (cust_state, count_attempt, escalation
flow). Wahi drift ka asli khatra tha: Phase 3.5 mein gate aur counter alag ho
gaye the, aur Phase 5 mein agent ne ek extra audit entry likh di thi jo batch
nahi likhta tha. Ab dono ek hi implementation call karte hain.

Structure jaan-boojh kar do hisson mein hai:
  1. STEPS      — har step ek chhota function (st, ctx). Yahi asli kaam karte hain.
  2. ROUTES     — kaunsa step agle number pe. Predicates alag rakhe hain taaki
                  run_batch ka sequential loop AUR agent ka LangGraph graph
                  bilkul WAHI routing use karein, do copies nahi.

⚠️ INVARIANTS: yahan koi policy nahi banti. Label diagnoser se, proposal decider
se, DECISION policy_engine.check se, action executor se, message notifications
se, aur har stage audit mein. Fallback bhi dobara gate se guzarta hai.
"""
from typing import Any, Callable, Dict, Optional

import config
import decider
import diagnoser
import executor
import notifications
import policy_engine
from store import Store


def _default_messaging_state(_customer_id: str) -> Dict[str, Any]:
    return {"has_consent": True, "opted_out_within_cooldown": False}


class Ctx:
    """
    Run-level context: audit log, clock, live-mode knobs, aur per-customer
    attempt tally. Ek batch run ka ek Ctx; agent ka ek long-lived Ctx.
    """

    def __init__(self, log, now, live: bool = False, live_limit: int = 1,
                 show_notifications: bool = False,
                 messaging_state: Optional[Callable[[str], Dict[str, Any]]] = None,
                 store: Optional[Store] = None):
        self.log = log
        self.now = now
        self.live = live
        self.live_limit = live_limit
        self.live_created = 0
        self.show_notifications = show_notifications
        self.messaging_state = messaging_state or _default_messaging_state
        # Attempt history + contact tally ab SQLite mein (store.py dekho).
        # Default `:memory:` = throwaway, batch ke deterministic run ke liye.
        self.store = store if store is not None else Store(":memory:")

    def day(self) -> str:
        """Spend cap ka bucket. Date key mein hai to cap ROZ reset hota hai."""
        return self.now.date().isoformat()

    def hydrate(self, txn):
        """Persisted attempt-history txn par chadhao (webhook mein ye fields nahi aate)."""
        return self.store.hydrate(txn)

    def cust_state(self, txn) -> Dict[str, Any]:
        """Policy ke liye customer state (spend cap + TRAI consent)."""
        s = dict(self.messaging_state(txn.customer_id))
        s["attempts_today"] = self.store.attempts_today(txn.customer_id, self.day())
        return s

    def count_attempt(self, txn, act: str) -> None:
        """
        Spend-cap tally. Wahi definition jo rule_spend_cap use karta hai
        (config.CONTACT_ACTIONS) — warna rule aur counter alag hisaab lagayenge
        aur cap chupke se galat ho jayega. Ab ye DB mein jata hai, isliye
        restart ke baad bhi zinda rehta hai.
        """
        if (not config.SPEND_CAP_COUNTS_CONTACTS_ONLY
                or act in config.CONTACT_ACTIONS):
            self.store.increment_attempt(txn.customer_id, self.day())


def new_state(txn) -> Dict[str, Any]:
    """Ek txn ka mutable state. Yahi aage metrics ka result dict ban jata hai."""
    return {"txn": txn, "label": None, "explanation": None,
            "proposed_action": None, "candidate": None, "action": None,
            "escalated_from": None, "escalation_kind": None,
            "escalation_label": None, "pending_kind": None, "allowed": None,
            "outcome": None, "link": None, "nudge": None,
            "reasons": [], "failed_rules": [], "fallback_used": False,
            "verdict": None}


# --- STEPS --------------------------------------------------------------------

def detect(st, ctx: Ctx) -> None:
    txn = st["txn"]
    # Store se attempt-history chadhao. Ye jaan-boojh kar koi AUDIT ENTRY nahi
    # likhta — timeline ka shape waisa hi rehna chahiye jo pehle tha.
    ctx.hydrate(txn)
    ctx.log.log(txn.id, "detect", {"status": txn.status, "amount": txn.amount,
                                   "error_code": txn.error_code},
                order_id=txn.order_id)


def diagnose(st, ctx: Ctx) -> None:
    """Label deterministic (classify); explanation sirf prose."""
    txn = st["txn"]
    label, explanation = diagnoser.diagnose(txn)
    ctx.log.log(txn.id, "diagnose", {"label": label, "explanation": explanation},
                order_id=txn.order_id)
    st["label"], st["explanation"] = label, explanation


def decide(st, ctx: Ctx) -> None:
    """PROPOSE only — deliberately naive, see decider.py."""
    txn = st["txn"]
    proposed = decider.propose(txn, st["label"])
    ctx.log.log(txn.id, "decide", {"proposed_action": proposed}, order_id=txn.order_id)
    st["proposed_action"] = st["candidate"] = st["action"] = proposed


def gate(st, ctx: Ctx) -> None:
    """⭐ Refusal SIRF yahan se aata hai. Fallback bhi yahin dobara aata hai."""
    txn = st["txn"]
    cand = st["candidate"]
    verdict = policy_engine.check(cand, txn, st["label"], now=ctx.now,
                                  customer_state=ctx.cust_state(txn))
    if st["fallback_used"]:
        detail = {"action": cand, "escalated_from": st["escalation_label"],
                  "allowed": verdict["allowed"], "failed_rules": verdict["reasons"]}
    else:
        detail = {"action": cand, "allowed": verdict["allowed"],
                  "failed_rules": verdict["reasons"]}
    ctx.log.log(txn.id, "policy_check", detail, order_id=txn.order_id)

    st["verdict"] = verdict
    st["failed_rules"] = st["failed_rules"] + list(verdict["failed_rules"])
    if st["allowed"] is None:            # pehle check ka natija hi "allowed" hai
        st["allowed"] = verdict["allowed"]
    if not verdict["allowed"]:
        st["reasons"] = st["reasons"] + list(verdict["reasons"])


def execute(st, ctx: Ctx) -> None:
    """
    Single execution seam — sab executor.py se. Live call fail hui to MOCK par
    fallback NAHI: error audit mein, case human_review. Fake link kabhi nahi.
    """
    txn = st["txn"]
    cand = st["candidate"]
    use_live = (ctx.live and cand in ("payment_link", "recovery_link")
                and (ctx.live_limit == 0 or ctx.live_created < ctx.live_limit))
    try:
        outcome, artifact = executor.execute(cand, txn, dry_run=not use_live)
    except Exception as exc:
        err = f"EXECUTOR_ERROR: {type(exc).__name__}: {exc}"
        ctx.log.log(txn.id, "execute_error",
                    {"action": cand, "live": use_live, "error": err},
                    order_id=txn.order_id)
        st["action"], st["outcome"] = "human_review", "human_review"
        # Pehla execute -> reason replace; fallback ke baad -> append.
        st["reasons"] = (st["reasons"] + [err]) if st["fallback_used"] else [err]
        return

    if artifact is not None and artifact.get("live"):
        ctx.live_created += 1
        print(f"  [LIVE] {txn.id}: payment link created -> {artifact['short_url']}")
    ctx.log.log(txn.id, "execute",
                {"action": cand, "outcome": outcome,
                 "live": bool(artifact and artifact.get("live")),
                 "artifact": artifact},
                order_id=txn.order_id)
    ctx.count_attempt(txn, cand)
    if cand == "retry":
        # Re-presentment ho gaya -> attempt history DB mein badhao, taaki agla
        # event (naye process mein bhi) NPCI 1+3 sahi gin sake.
        ctx.store.record_retry(txn)
    st["outcome"], st["action"] = outcome, cand
    if artifact is not None:
        st["link"] = artifact
    if st["fallback_used"]:
        # Escalation tabhi "hui" maani jayegi jab fallback ACTUALLY execute ho.
        # Agar fallback bhi gate pe ruk gaya to case human_review hai, escalation
        # nahi — warna metrics ka "Blocked debit -> link" inflate ho jata hai.
        st["escalation_kind"] = st["pending_kind"]
        st["escalated_from"] = (st["proposed_action"]
                                if st["pending_kind"] == "gate_blocked" else "retry")


def fallback(st, ctx: Ctx) -> None:
    """
    Compliant alternative PROPOSE karo (link). Ye bhi sirf proposal hai —
    route wapas gate par jata hai, koi bypass nahi.

    Do wajah se yahan aate hain:
      gate_blocked  -> gate ne debit block kiya
      retry_failed  -> retry allow tha, chala, par recover nahi hua
    """
    if st["verdict"]["allowed"]:
        st["pending_kind"] = "retry_failed"
        st["escalation_label"] = "retry (attempted, not recovered)"
        st["candidate"] = "payment_link"
        st["fallback_used"] = True
        return

    fb = decider.fallback(st["candidate"], st["verdict"]["failed_rules"])
    if not fb:
        st["fallback_used"] = False       # koi compliant alternative nahi
        return
    st["pending_kind"] = "gate_blocked"
    st["escalation_label"] = st["proposed_action"]
    st["candidate"] = fb
    st["fallback_used"] = True


def nudge(st, ctx: Ctx) -> None:
    """Link banana contact nahi; BATANA contact hai — alag action, alag gate."""
    txn = st["txn"]
    link = st["link"]
    if link is None:
        return
    v = policy_engine.check("nudge", txn, st["label"], now=ctx.now,
                            customer_state=ctx.cust_state(txn))
    ctx.log.log(txn.id, "policy_check",
                {"action": "nudge", "allowed": v["allowed"],
                 "failed_rules": v["reasons"]},
                order_id=txn.order_id)
    if v["allowed"]:
        record = notifications.send(txn.customer_id, txn.amount, txn.order_id,
                                    link["short_url"], now=ctx.now,
                                    verbose=ctx.show_notifications)
        ctx.log.log(txn.id, "notify", record, order_id=txn.order_id)
        ctx.count_attempt(txn, "nudge")
        st["nudge"] = {"status": "sent", "reasons": []}
    else:
        ctx.log.log(txn.id, "notify",
                    {"suppressed": True, "reasons": v["reasons"]},
                    order_id=txn.order_id)
        st["failed_rules"] = st["failed_rules"] + list(v["failed_rules"])
        st["nudge"] = {"status": "suppressed", "reasons": list(v["reasons"])}


def escalate(st, ctx: Ctx) -> None:
    """Koi automated rasta nahi bacha -> human review, reasons ke saath."""
    if st["proposed_action"] == "human_review" and not st["reasons"]:
        st["reasons"] = ["unclassified failure - no automated action proposed"]
    st["action"], st["outcome"] = "human_review", "human_review"


def finalize(st, ctx: Ctx) -> None:
    txn = st["txn"]
    ctx.log.log(txn.id, "outcome",
                {"outcome": st["outcome"], "reasons": st["reasons"],
                 "escalated_from": st["escalated_from"],
                 "escalation_kind": st["escalation_kind"]},
                order_id=txn.order_id)


# --- ROUTES (dono entry points yahi predicates use karte hain) -----------------

def route_after_decide(st) -> str:
    return "escalate" if st["proposed_action"] == "human_review" else "gate"


def route_after_gate(st) -> str:
    if st["verdict"]["allowed"]:
        return "execute"
    if st["fallback_used"]:
        return "escalate"            # fallback bhi blocked -> human, reasons ke saath
    return "fallback"


def route_after_execute(st) -> str:
    if st["outcome"] == "human_review":      # executor error
        return "finalize"
    # retry chala par recover nahi hua -> ek compliant link do (ek hi baar)
    if (st["candidate"] == "retry" and st["outcome"] != "recovered"
            and not st["fallback_used"]):
        return "fallback"
    return "nudge"


def route_after_fallback(st) -> str:
    return "gate" if st["fallback_used"] else "escalate"


STEPS = {"detect": detect, "diagnose": diagnose, "decide": decide, "gate": gate,
         "execute": execute, "fallback": fallback, "nudge": nudge,
         "escalate": escalate, "finalize": finalize}

ROUTES = {"decide": route_after_decide, "gate": route_after_gate,
          "execute": route_after_execute, "fallback": route_after_fallback}


def process_txn(txn, ctx: Ctx) -> Dict[str, Any]:
    """
    Ek transaction ka poora flow, sequentially. run_batch isi ko loop mein
    call karta hai. agent.py wahi STEPS/ROUTES LangGraph edges ke roop mein
    chalata hai — logic dono jagah ek hi hai.
    """
    st = new_state(txn)
    detect(st, ctx)
    diagnose(st, ctx)
    decide(st, ctx)

    node = route_after_decide(st)
    while node != "finalize":
        STEPS[node](st, ctx)
        if node in ROUTES:
            node = ROUTES[node](st)
        else:                        # nudge / escalate -> seedha finalize
            node = "finalize"
    finalize(st, ctx)
    return st
