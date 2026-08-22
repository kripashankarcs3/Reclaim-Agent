"""
audit.py — Immutable, append-only audit trail.

Judges ki bar mein sabse zyada miss hone waali cheez = audit trail.
Isliye ye append-only hai: log() sirf add karta hai, koi update/delete API nahi.
Har case ka poora timeline banta hai: detect -> diagnose -> decide ->
policy_check -> execute/block -> outcome.
"""
from typing import Dict, Any, List
from models import AuditEntry


class AuditLog:
    def __init__(self):
        self._entries: List[AuditEntry] = []   # append-only in-memory (Phase 5: DB)

    def log(self, txn_id: str, stage: str, detail: Dict[str, Any]) -> None:
        self._entries.append(AuditEntry(txn_id=txn_id, stage=stage, detail=detail))

    def timeline(self, txn_id: str) -> List[AuditEntry]:
        """Ek case ka pura ordered timeline — yahi UI mein dikhega."""
        return [e for e in self._entries if e.txn_id == txn_id]

    def all(self) -> List[AuditEntry]:
        return list(self._entries)

    def print_timeline(self, txn_id: str) -> None:
        print(f"\n  AUDIT TIMELINE — {txn_id}")
        for e in self.timeline(txn_id):
            print(f"    [{e.stage:<12}] {e.detail}")
