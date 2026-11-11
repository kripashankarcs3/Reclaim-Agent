"""
models.py — Core data structures.

Ye pure-Python dataclasses hain taaki spine bina DB/network ke chale.
Phase 5 mein inhe SQLAlchemy tables se replace/back kar dena (schema same hai):
Transaction, AuditLog (append-only), Action.
"""
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, Any, Dict, List


@dataclass
class Transaction:
    id: str
    order_id: str
    amount: int                 # paise/rupees — yahan rupees rakhe hain
    method: str                 # upi / card / netbanking
    status: str                 # failed / halted / abandoned / recovered / pending
    customer_id: str
    is_subscription: bool = False
    retry_count: int = 0        # kitni baar pehle try ho chuka (1 original included)
    error_code: Optional[str] = None
    error_source: Optional[str] = None
    error_step: Optional[str] = None
    error_reason: Optional[str] = None
    pre_debit_notice_sent: bool = False
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # --- Ground truth (sirf metrics ke liye — agent isse "cheat" nahi karta) --
    gt_label: Optional[str] = None        # soft / hard / abandoned / halted
    gt_should_recover: Optional[bool] = None
    gt_correct_action: Optional[str] = None


@dataclass
class Action:
    txn_id: str
    action_type: str            # retry / payment_link / nudge / human_review / blocked / none
    status: str = "proposed"    # proposed / executed / blocked
    reason: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class AuditEntry:
    """Append-only. Kabhi update/delete nahi — yahi immutable trail hai."""
    txn_id: str
    stage: str                  # detect / diagnose / decide / policy_check / execute / outcome
    detail: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


def to_dict(obj) -> Dict[str, Any]:
    return asdict(obj)
