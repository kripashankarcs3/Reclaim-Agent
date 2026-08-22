"""
policy_engine.py — ⭐ THE STAR. Deterministic compliance gate.

Core design (interview mein must bolna):
    "LLM PROPOSE karta hai, policy engine DECIDE karta hai." (propose-verify split)
    LLM kabhi seedha paisa move nahi karta. Har proposed action pehle yahan
    se pass hota hai. Koi bhi rule fail = action BLOCKED + reason audit mein.

Har rule chhota, testable function hai jo (allowed: bool, reason: str) deta hai.
check() applicable rules chalata hai aur saare fail-reasons collect karta hai.
"""
from datetime import datetime
from typing import Tuple, List, Dict
import config


# --- Individual rules --------------------------------------------------------
# Convention: (allowed, reason). allowed=True -> "" reason.

def rule_retry_cap(action: str, txn) -> Tuple[bool, str]:
    """NPCI 1+3 cap: total 4 attempts. retry_count>=3 -> koi aur retry BLOCK."""
    if action == "retry" and txn.retry_count >= config.MAX_RETRIES:
        return False, (f"RETRY_CAP: NPCI 1+3 cap exhausted "
                       f"({txn.retry_count + 1}/{config.MAX_TOTAL_ATTEMPTS} attempts used)")
    return True, ""


def rule_hard_decline(action: str, txn, label: str) -> Tuple[bool, str]:
    """Hard decline (insufficient funds/blocked card) -> silent auto-retry BLOCK."""
    if action == "retry" and label == "hard":
        return False, "HARD_DECLINE: hard decline not eligible for silent retry (link only)"
    return True, ""


def rule_afa_threshold(action: str, txn) -> Tuple[bool, str]:
    """> Rs.15,000 pe silent recurring debit BLOCK — AFA/customer auth chahiye."""
    silent_debit = action in ("retry",)
    if silent_debit and txn.amount > config.AFA_THRESHOLD:
        return False, (f"AFA_THRESHOLD: amount Rs.{txn.amount} > Rs.{config.AFA_THRESHOLD} "
                       f"requires AFA (no silent debit)")
    return True, ""


def rule_pre_debit_notice(action: str, txn) -> Tuple[bool, str]:
    """Subscription retry se 24hr pehle notice bheja hona chahiye."""
    if action == "retry" and txn.is_subscription and not txn.pre_debit_notice_sent:
        return False, "PRE_DEBIT_NOTICE: 24-hour pre-debit notification not sent"
    return True, ""


def rule_contact_window(action: str, txn, now: datetime) -> Tuple[bool, str]:
    """Customer contact (nudge/link+nudge) sirf 8AM-7PM ke andar."""
    contacts_customer = action in ("nudge", "payment_link", "recovery_link")
    if contacts_customer:
        hour = now.hour
        if not (config.CONTACT_WINDOW_START <= hour < config.CONTACT_WINDOW_END):
            return False, (f"CONTACT_WINDOW: {now.strftime('%H:%M')} outside "
                           f"{config.CONTACT_WINDOW_START}:00-{config.CONTACT_WINDOW_END}:00 window")
    return True, ""


def rule_trai_messaging(action: str, txn, customer_state: Dict) -> Tuple[bool, str]:
    """Nudge sirf consent ke saath; opt-out ke 90 din tak nahi."""
    if action == "nudge":
        if customer_state.get("opted_out_within_cooldown"):
            return False, (f"TRAI_MESSAGING: customer opted out within "
                           f"{config.OPT_OUT_COOLDOWN_DAYS}-day cooldown")
        if not customer_state.get("has_consent", True):
            return False, "TRAI_MESSAGING: no messaging consent on record"
    return True, ""


def rule_spend_cap(action: str, txn, customer_state: Dict) -> Tuple[bool, str]:
    """Ek customer ko din mein N se zyada recovery attempts nahi (over-contact)."""
    attempts_today = customer_state.get("attempts_today", 0)
    if action in ("retry", "payment_link", "recovery_link", "nudge"):
        if attempts_today >= config.MAX_RECOVERY_ATTEMPTS_PER_CUSTOMER_PER_DAY:
            return False, (f"SPEND_CAP: {attempts_today} attempts today >= cap "
                           f"{config.MAX_RECOVERY_ATTEMPTS_PER_CUSTOMER_PER_DAY}")
    return True, ""


# --- The gate ----------------------------------------------------------------

def check(action: str, txn, label: str, now: datetime = None,
          customer_state: Dict = None) -> Dict:
    """
    Saare applicable rules chalao. Ek bhi fail -> allowed=False.
    Returns: {allowed: bool, reasons: [str], checks: [{rule, passed, reason}]}
    """
    now = now or datetime.now()
    customer_state = customer_state or {}

    results = [
        ("RETRY_CAP",       rule_retry_cap(action, txn)),
        ("HARD_DECLINE",    rule_hard_decline(action, txn, label)),
        ("AFA_THRESHOLD",   rule_afa_threshold(action, txn)),
        ("PRE_DEBIT_NOTICE", rule_pre_debit_notice(action, txn)),
        ("CONTACT_WINDOW",  rule_contact_window(action, txn, now)),
        ("TRAI_MESSAGING",  rule_trai_messaging(action, txn, customer_state)),
        ("SPEND_CAP",       rule_spend_cap(action, txn, customer_state)),
    ]

    checks = [{"rule": name, "passed": ok, "reason": reason}
              for name, (ok, reason) in results]
    fail_reasons = [reason for _, (ok, reason) in results if not ok]

    return {
        "allowed": len(fail_reasons) == 0,
        "reasons": fail_reasons,
        "checks": checks,
    }
