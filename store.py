"""
store.py — chhota SQLite layer (stdlib sqlite3, koi ORM nahi).

KYUN ZAROORI HAI (ye Phase 6 ka poora point hai):
Razorpay ke webhook payload mein `retry_count` aur `pre_debit_notice_sent`
hote hi NAHI. Wo hamari apni state hai. Aur per-customer attempts abhi tak ek
in-memory dict mein thi. Matlab live webhook par:
  - har event "attempt #1" lagta -> NPCI 1+3 cap kabhi fire hi nahi karta,
  - process restart par spend cap zero ho jata -> over-contact guard bekaar,
  - 24-hour pre-debit notice ka record hi nahi bachta.
Gate sahi tha, par usse ginne ke liye data hi nahi tha. Ye file wo data deti hai.

DO TABLES, dono chhote:
  seen_events       -> x-razorpay-event-id (webhook idempotency). Razorpay
                       retries bhejta hai; ye table restart ke baad bhi duplicate
                       pehchan leta hai — in-memory set nahi kar pata tha.
  txn_state         -> order_id ke against attempt history (order_id isliye ki
                       Razorpay har re-presentment par NAYA payment id deta hai,
                       par order/invoice wahi rehta hai).
  customer_attempts -> (customer_id, day) ke against tally. `day` key mein hone
                       se cap ROZ apne aap reset hota hai — process restart par
                       nahi, jaisa in-memory dict mein hota tha.

DETERMINISM: batch run `:memory:` store use karta hai jo har run par khaali
banta hai aur pehle touch par seed.py ki ground truth se khud bhar jata hai
(hydrate ka insert branch). Isliye offline batch ka output bilkul waisa hi
rehta hai; DB sirf webhook path ko durability deti hai.

AUDIT: ye file audit log ko haath nahi lagati. Append-only invariant waisa hi.
"""
import sqlite3
import threading
from datetime import datetime
from typing import Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS txn_state (
    order_id              TEXT PRIMARY KEY,
    retry_count           INTEGER NOT NULL DEFAULT 0,
    pre_debit_notice_sent INTEGER NOT NULL DEFAULT 0,
    updated_at            TEXT    NOT NULL
);
CREATE TABLE IF NOT EXISTS seen_events (
    event_id    TEXT PRIMARY KEY,
    received_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS customer_attempts (
    customer_id TEXT    NOT NULL,
    day         TEXT    NOT NULL,
    attempts    INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (customer_id, day)
);
"""


def _stamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Store:
    """Ek chhota, sync sqlite wrapper. `:memory:` = throwaway (batch ke liye)."""

    def __init__(self, path: str = ":memory:"):
        self.path = path
        # check_same_thread=False + ek lock: sqlite connection by default us
        # thread se bandha hota hai jisne use banaya. Webhook server module
        # import ek thread par karta hai aur request doosre par handle karta hai,
        # to default connection wahan ProgrammingError deta hai. Lock is liye
        # hai ki ek hi writer chale (SQLite ka apna write lock waise bhi
        # serialize karta hai; hamara volume chhota hai).
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self.conn.executescript(SCHEMA)
            self.conn.commit()

    # --- attempt history (NPCI 1+3 + pre-debit notice) ------------------------

    def hydrate(self, txn):
        """
        Txn par persisted attempt-history chadha do.

        Pehli baar dikhe to uski MAUJUDA values insert kar deta hai — isi wajah
        se batch apne aap seed ho jata hai aur uska output nahi badalta. Baad ke
        events (webhook) par stored values jeet'ti hain, kyunki webhook payload
        mein ye fields hote hi nahi.
        """
        with self._lock:
            row = self.conn.execute(
                "SELECT retry_count, pre_debit_notice_sent FROM txn_state WHERE order_id = ?",
                (txn.order_id,),
            ).fetchone()
            if row is None:
                self.conn.execute(
                    "INSERT INTO txn_state (order_id, retry_count, pre_debit_notice_sent, updated_at)"
                    " VALUES (?, ?, ?, ?)",
                    (txn.order_id, int(txn.retry_count),
                     int(bool(txn.pre_debit_notice_sent)), _stamp()),
                )
                self.conn.commit()
                return txn
        txn.retry_count = int(row[0])
        txn.pre_debit_notice_sent = bool(row[1])
        return txn

    def record_retry(self, txn) -> int:
        """Ek re-presentment ho gaya — attempt history badha do. Naya count return."""
        with self._lock:
            self.conn.execute(
                "UPDATE txn_state SET retry_count = retry_count + 1, updated_at = ?"
                " WHERE order_id = ?",
                (_stamp(), txn.order_id),
            )
            self.conn.commit()
            row = self.conn.execute(
                "SELECT retry_count FROM txn_state WHERE order_id = ?", (txn.order_id,)
            ).fetchone()
        return int(row[0]) if row else 0

    def mark_pre_debit_notice(self, txn) -> None:
        """24-hour pre-debit notice bhej diya — record rakho (Phase 7+ ke liye)."""
        with self._lock:
            self.conn.execute(
                "UPDATE txn_state SET pre_debit_notice_sent = 1, updated_at = ?"
                " WHERE order_id = ?",
                (_stamp(), txn.order_id),
            )
            self.conn.commit()

    # --- webhook idempotency ---------------------------------------------------

    def claim_event(self, event_id: str) -> bool:
        """
        Event id par "dawa" thoko. True = pehli baar (process karo),
        False = duplicate (ignore karo).

        INSERT OR IGNORE + PRIMARY KEY = atomic check-and-set, isliye do
        concurrent deliveries mein se sirf ek hi jeetega. In-memory set se ye
        restart par bhool jata tha aur Razorpay ka retry dobara process ho jata.
        """
        with self._lock:
            cur = self.conn.execute(
                "INSERT OR IGNORE INTO seen_events (event_id, received_at) VALUES (?, ?)",
                (event_id, _stamp()),
            )
            self.conn.commit()
            return cur.rowcount == 1

    def event_seen(self, event_id: str) -> bool:
        with self._lock:
            row = self.conn.execute(
                "SELECT 1 FROM seen_events WHERE event_id = ?", (event_id,)
            ).fetchone()
        return row is not None

    # --- per-customer contact tally (spend cap) -------------------------------

    def attempts_today(self, customer_id: str, day: str) -> int:
        with self._lock:
            row = self.conn.execute(
                "SELECT attempts FROM customer_attempts WHERE customer_id = ? AND day = ?",
                (customer_id, day),
            ).fetchone()
        return int(row[0]) if row else 0

    def increment_attempt(self, customer_id: str, day: str) -> int:
        """(customer, day) tally +1. `day` key mein hai to cap roz reset hota hai."""
        with self._lock:
            self.conn.execute(
                "INSERT INTO customer_attempts (customer_id, day, attempts) VALUES (?, ?, 1)"
                " ON CONFLICT(customer_id, day) DO UPDATE SET attempts = attempts + 1",
                (customer_id, day),
            )
            self.conn.commit()
        return self.attempts_today(customer_id, day)

    # --- helpers ---------------------------------------------------------------

    def snapshot(self, order_id: str = None, customer_id: str = None,
                 day: str = None) -> dict:
        """Demo/debug ke liye padhne layak state (koi write nahi)."""
        out = {}
        if order_id:
            with self._lock:
                row = self.conn.execute(
                    "SELECT retry_count, pre_debit_notice_sent FROM txn_state WHERE order_id = ?",
                    (order_id,),
                ).fetchone()
            out["retry_count"] = int(row[0]) if row else None
            out["pre_debit_notice_sent"] = bool(row[1]) if row else None
        if customer_id and day:
            out["attempts_today"] = self.attempts_today(customer_id, day)
        return out

    def reset(self) -> None:
        """SIRF test/demo ke liye. Audit log ko chhuta bhi nahi."""
        with self._lock:
            self.conn.execute("DELETE FROM txn_state")
            self.conn.execute("DELETE FROM customer_attempts")
            self.conn.execute("DELETE FROM seen_events")
            self.conn.commit()

    def close(self) -> None:
        self.conn.close()
