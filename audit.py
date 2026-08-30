"""
audit.py — Immutable, append-only audit trail.

Judges ki bar mein sabse zyada miss hone waali cheez = audit trail.
Isliye ye append-only hai: log() sirf add karta hai, koi update/delete API nahi.
Har case ka poora timeline banta hai: detect -> diagnose -> decide ->
policy_check -> execute/block -> outcome.

Do BACKING modes (Phase 6.5):
  store=None   -> pure in-memory Python list. `run_batch.py` isi mode mein
                  chalta hai — batch ka output is phase se bilkul anchhua.
  store=<Store> -> har log() call store.append_audit() se hokar SQLite mein
                  jaati hai; timeline()/all() bhi wahi se padhte hain. Isse
                  agent.py (webhook) ka audit trail process RESTART ke baad
                  bhi zinda rehta hai — pehle ye poori tarah bhool jata tha.

Dono mode mein caller ko farak nahi padta: same class, same methods, same
AuditEntry objects wapas aate hain.
"""
from typing import Dict, Any, List, Optional
from models import AuditEntry


class AuditLog:
    def __init__(self, store: Optional[object] = None):
        self._store = store
        # store None ho to hi in-memory list banti hai — store-backed mode
        # mein DB hi source of truth hai, do jagah state rakhne ka koi fayda
        # nahi (aur drift ka risk hai).
        self._entries: List[AuditEntry] = [] if store is None else None

    def log(self, txn_id: str, stage: str, detail: Dict[str, Any],
            order_id: Optional[str] = None) -> None:
        if self._store is not None:
            self._store.append_audit(txn_id, order_id, stage, detail)
            return
        self._entries.append(AuditEntry(txn_id=txn_id, stage=stage, detail=detail))

    def timeline(self, txn_id: str) -> List[AuditEntry]:
        """Ek case ka pura ordered timeline — yahi UI mein dikhega."""
        if self._store is not None:
            return self._store.audit_timeline(txn_id)
        return [e for e in self._entries if e.txn_id == txn_id]

    def timeline_by_order(self, order_id: str) -> List[AuditEntry]:
        """
        Order_id se poora timeline — ek hi case ke saare payment-id
        re-presentments ek saath. Sirf store-backed mode mein kaam karta hai
        (in-memory AuditEntry order_id save hi nahi karta).
        """
        if self._store is not None:
            return self._store.audit_timeline_by_order(order_id)
        raise NotImplementedError(
            "timeline_by_order sirf store-backed AuditLog par kaam karta hai")

    def all(self) -> List[AuditEntry]:
        if self._store is not None:
            return self._store.audit_all()
        return list(self._entries)

    def watermark(self) -> int:
        """
        Abhi tak kitni entries hain — 'is se pehle sab purana hai' wala marker.
        entries_since() ke saath milke "is delivery ne kya likha" nikalte hain.
        """
        if self._store is not None:
            return self._store.audit_max_id()
        return len(self._entries)

    def entries_since(self, watermark: int, txn_id: str) -> List[AuditEntry]:
        """`watermark` ke BAAD is txn_id ke liye likhi gayi entries."""
        if self._store is not None:
            return self._store.audit_since(watermark, txn_id)
        return [e for e in self._entries[watermark:] if e.txn_id == txn_id]

    def print_timeline(self, txn_id: str) -> None:
        print(f"\n  AUDIT TIMELINE — {txn_id}")
        for e in self.timeline(txn_id):
            print(f"    [{e.stage:<12}] {e.detail}")
