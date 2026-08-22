"""
seed.py — 50+ synthetic transactions (tumhara held-out batch).

Har txn pe ground-truth label + correct action store hai taaki Phase 6 mein
precision aur false-positive cost HONESTLY measure kar sako.
Deterministic (seed=42) taaki demo kabhi stall/change na ho.
"""
import random
from models import Transaction

random.seed(42)

# Real error codes Razorpay official list se (fake na lage)
_SOFT = ["GATEWAY_ERROR", "payment_timeout", "gateway_timeout", "SERVER_ERROR"]
_HARD = ["insufficient_funds", "card_declined", "invalid_vpa", "card_expired"]


# --- TRAI TCCCPR customer state (deterministic; batch ke saath rehta hai) -----
# Do customers messaging rules ko HAR run mein exercise karte hain: unka
# payment link ban jayega (link banana koi contact nahi hai) par nudge gate pe
# block hoga. Warna rule_trai_messaging kabhi chalta hi nahi tha.
OPTED_OUT_CUSTOMERS = {"cust_030"}    # 90-din opt-out cooldown ke andar
NO_CONSENT_CUSTOMERS = {"cust_033"}   # DLT messaging consent record pe nahi


def messaging_state(customer_id: str) -> dict:
    """policy_engine.check() ko dene ke liye per-customer TRAI state."""
    return {
        "has_consent": customer_id not in NO_CONSENT_CUSTOMERS,
        "opted_out_within_cooldown": customer_id in OPTED_OUT_CUSTOMERS,
    }


def _mk(i, **kw):
    base = dict(
        id=f"txn_{i:03d}",
        order_id=f"order_{i:03d}",
        amount=random.choice([199, 499, 999, 1499, 2999, 4999]),
        method=random.choice(["upi", "card", "netbanking"]),
        customer_id=f"cust_{i:03d}",   # mostly unique; ek pair deliberately repeat (neeche)
        is_subscription=False,
        retry_count=0,
        status="failed",
    )
    base.update(kw)
    return Transaction(**base)


def generate():
    txns = []
    i = 0

    # 1) Soft / transient (15) — half mandate-backed, half one-time.
    #    Mandate-backed  -> retry legitimately allowed (recoverable).
    #    One-time        -> koi token nahi, silent retry possible hi nahi:
    #                       gate MANDATE_REQUIRED pe block karega -> link.
    #    Draw order (code -> is_sub -> retry_count -> _mk) preserve karna zaroori
    #    hai warna poora batch shift ho jayega.
    for _ in range(15):
        i += 1
        code = random.choice(_SOFT)
        is_sub = random.random() < 0.5
        rc = random.choice([0, 1])
        txns.append(_mk(i, status="failed", error_code=code,
                        error_source="gateway", error_step="authorization",
                        is_subscription=is_sub,
                        pre_debit_notice_sent=True, retry_count=rc,
                        gt_label="soft", gt_should_recover=True,
                        gt_correct_action="retry" if is_sub else "payment_link"))

    # 2) Hard decline (12) — stop retry -> link
    for _ in range(12):
        i += 1
        txns.append(_mk(i, status="failed", error_code=random.choice(_HARD),
                        error_source="bank", error_step="authorization",
                        retry_count=random.choice([0, 2, 3]),
                        gt_label="hard", gt_should_recover=True, gt_correct_action="payment_link"))

    # 3) Abandoned checkout (10) — recovery link + 1 nudge
    for _ in range(10):
        i += 1
        txns.append(_mk(i, status="abandoned", error_code=None,
                        error_source=None, error_step=None,
                        gt_label="abandoned", gt_should_recover=True,
                        gt_correct_action="recovery_link"))

    # 4) Halted subscription (8) — stop -> link, pending
    for _ in range(8):
        i += 1
        txns.append(_mk(i, status="halted", error_code="insufficient_funds",
                        error_source="bank", error_step="authorization",
                        is_subscription=True, retry_count=3, pre_debit_notice_sent=True,
                        gt_label="halted", gt_should_recover=True,
                        gt_correct_action="payment_link"))

    # 5) Edge / compliance cases (6) — MUST be blocked -> human review
    #    high amount + odd time; hard + odd time; etc. (graceful-failure proof)
    edge = [
        dict(amount=25000, is_subscription=True, error_code="insufficient_funds",
             status="failed", retry_count=3, pre_debit_notice_sent=True,
             gt_label="hard", gt_should_recover=True, gt_correct_action="payment_link"),
        dict(amount=49999, is_subscription=True, error_code="GATEWAY_ERROR",
             status="failed", retry_count=1, pre_debit_notice_sent=True,
             gt_label="soft", gt_should_recover=False, gt_correct_action="human_review"),
        dict(amount=18000, is_subscription=False, error_code="card_declined",
             status="failed", retry_count=0,
             gt_label="hard", gt_should_recover=True, gt_correct_action="payment_link"),
        dict(amount=999, is_subscription=True, error_code="GATEWAY_ERROR",
             status="failed", retry_count=0, pre_debit_notice_sent=False,  # notice NOT sent
             gt_label="soft", gt_should_recover=False, gt_correct_action="human_review"),
        dict(amount=1499, is_subscription=False, error_code="insufficient_funds",
             status="failed", retry_count=3,   # cap already exhausted
             gt_label="hard", gt_should_recover=True, gt_correct_action="payment_link"),
        dict(amount=30000, is_subscription=True, error_code="insufficient_funds",
             status="halted", retry_count=3, pre_debit_notice_sent=True,
             gt_label="halted", gt_should_recover=False, gt_correct_action="human_review"),
        # Same customer, teen baar. Ye ONE-TIME payments hain (deliberately —
        # inhe subscription bana dena sirf recovery number bachane ke liye hota,
        # aur wahi cheating hai). Pehla: retry MANDATE_REQUIRED pe block -> link
        # (+nudge) = 2 attempts. Uske baad SPEND_CAP contact actions pe lag jata
        # hai, to doosra/teesra human review. Cap ab wahi demonstrate karta hai
        # jiske liye wo bana tha: over-CONTACT rokna.
        dict(customer_id="cust_repeat", amount=499, error_code="GATEWAY_ERROR",
             status="failed", pre_debit_notice_sent=True,
             gt_label="soft", gt_should_recover=True, gt_correct_action="payment_link"),
        dict(customer_id="cust_repeat", amount=499, error_code="GATEWAY_ERROR",
             status="failed", pre_debit_notice_sent=True,
             gt_label="soft", gt_should_recover=False, gt_correct_action="human_review"),
        dict(customer_id="cust_repeat", amount=499, error_code="GATEWAY_ERROR",
             status="failed", pre_debit_notice_sent=True,
             gt_label="soft", gt_should_recover=False, gt_correct_action="human_review"),
    ]
    for e in edge:
        i += 1
        txns.append(_mk(i, error_source="bank", error_step="authorization", **e))

    return txns


if __name__ == "__main__":
    b = generate()
    print(f"Generated {len(b)} transactions")
    from collections import Counter
    print(Counter(t.gt_label for t in b))
    print(f"Total at-risk: Rs.{sum(t.amount for t in b):,}")
