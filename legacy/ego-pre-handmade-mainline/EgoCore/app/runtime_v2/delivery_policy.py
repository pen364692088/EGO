from __future__ import annotations

import time

from .contracts import DeliveryIdentity, DeliveryLedger


class RuntimeV2DeliveryPolicy:
    def should_send_busy_notice(self, ledger: DeliveryLedger, dedupe_window_seconds: float = 6.0) -> bool:
        if ledger.last_busy_notice_at is None:
            return True
        return (time.time() - ledger.last_busy_notice_at) > dedupe_window_seconds

    def mark_busy_notice_sent(self, ledger: DeliveryLedger) -> None:
        ledger.last_busy_notice_at = time.time()

    def should_send_failure_notice(self, ledger: DeliveryLedger, text: str, dedupe_window_seconds: float = 8.0) -> bool:
        if ledger.last_failure_notice_at is None or ledger.last_failure_notice_text is None:
            return True
        same_text = ledger.last_failure_notice_text == text
        within_window = (time.time() - ledger.last_failure_notice_at) <= dedupe_window_seconds
        return not (same_text and within_window)

    def mark_failure_notice_sent(self, ledger: DeliveryLedger, text: str) -> None:
        ledger.last_failure_notice_at = time.time()
        ledger.last_failure_notice_text = text

    def should_emit(self, ledger: DeliveryLedger, identity: DeliveryIdentity, ttl_seconds: float = 30.0) -> bool:
        now = time.time()
        expired = [k for k, ts in ledger.sent_keys.items() if (now - ts) > ttl_seconds]
        for key in expired:
            ledger.sent_keys.pop(key, None)
        dedupe_key = identity.dedupe_key()
        if dedupe_key in ledger.sent_keys:
            return False
        ledger.sent_keys[dedupe_key] = now
        return True
