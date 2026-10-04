"""Moves policies from ACTIVE to a final state from Kalshi results, and pays out without manual steps."""

import threading
from datetime import datetime, timedelta, timezone

from ..integrations.market_data import MarketDataError
from ..integrations.money import BankError
from .catalog import parse_time
from .money import dollars

OPEN = ("ACTIVE", "AWAITING_RESULT")
FINAL_RESULTS = ("yes", "no")


class Settlement:
    def __init__(self, db, market_data, bank, max_attempts, clock=None):
        self.db = db
        self.market_data = market_data
        self.bank = bank
        self.max_attempts = max_attempts
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.lock = threading.Lock()

    def run_cycle(self):
        """One pass over every open policy. Safe to run repeatedly and concurrently with demo resolves."""
        summary = {"checked": 0, "paid": 0, "expired": 0, "waiting": 0, "errors": 0}
        with self.lock:
            for policy in self.db.list_policies(statuses=list(OPEN)):
                summary["checked"] += 1
                summary[self._advance(policy)] += 1
        return summary

    def demo_resolve(self, policy_id, result):
        with self.lock:
            policy = self.db.get_policy(policy_id)
            if policy is None or policy["status"] not in OPEN:
                return policy
            for leg in self.db.legs(policy_id):
                if leg["result"] is None:
                    self.db.update_leg(leg["id"], result=result, forced=1)
            self.db.add_event(policy_id, "demo_resolve", f"Demo: the risk desk settled the markets {result.upper()}.")
            self._advance(self.db.get_policy(policy_id), poll=False)
            return self.db.get_policy(policy_id)

    def _advance(self, policy, poll=True):
        now = self.clock()
        unreachable = False
        if poll:
            for leg in self.db.legs(policy["id"]):
                if leg["result"] is None and parse_time(leg["close_time"]) <= now:
                    try:
                        self._read_result(policy, leg)
                    except MarketDataError:
                        unreachable = True
        legs = self.db.legs(policy["id"])
        if policy["status"] == "ACTIVE":
            if not all(leg["result"] or parse_time(leg["close_time"]) <= now for leg in legs):
                return "waiting"
            self.db.transition(
                policy["id"], ["ACTIVE"], "AWAITING_RESULT", "window_closed", "Trading closed. Waiting for Kalshi's official result."
            )
        if any(leg["result"] is None for leg in legs):
            return "errors" if unreachable else "waiting"
        if any(leg["result"] not in FINAL_RESULTS for leg in legs):
            self.db.transition(
                policy["id"], list(OPEN), "NEEDS_REVIEW", "voided", "A market was voided. The risk desk will refund or settle by hand."
            )
            return "errors"
        owed = sum(leg["contracts"] * 100 for leg in legs if leg["result"] == leg["side"])
        if owed == 0:
            self.db.transition(policy["id"], list(OPEN), "EXPIRED", "expired", "None of the covered outcomes happened. The cover has expired.")
            return "expired"
        return self._pay(policy, owed, now)

    def _read_result(self, policy, leg):
        market = self.market_data.market(leg["ticker"])
        result = (market.get("result") or "").lower()
        if not result:
            return
        self.db.update_leg(leg["id"], result=result if result in FINAL_RESULTS else "void")
        if result in FINAL_RESULTS:
            verdict = "your cover pays" if result == leg["side"] else "no payout for this one"
            self.db.add_event(policy["id"], "result", f"Kalshi settled “{leg['label']}” {result.upper()}: {verdict}.")

    def _pay(self, policy, owed, now):
        key = f"payout:{policy['id']}"
        movement = self.db.claim_movement(policy["id"], "payout", owed, key)
        if movement["status"] == "done":
            self._mark_paid(policy, owed)
            return "paid"
        if policy["next_attempt_at"] and parse_time(policy["next_attempt_at"]) > now:
            return "waiting"
        business = self.db.get_business(policy["business_id"])
        try:
            account_id, transfer_id, moved = self.bank.pay(
                business["bank_customer_id"], business["bank_account_id"], owed, f"HedgeCast payout policy {policy['id']}"
            )
        except BankError as exc:
            return self._payout_failed(policy, key, str(exc), now)
        if account_id != business["bank_account_id"]:
            self.db.set_bank(business["id"], business["bank_customer_id"], account_id)
        self.db.finish_movement(key, "done", transfer_id)
        self._mark_paid(policy, moved)
        return "paid"

    def _mark_paid(self, policy, cents):
        self.db.transition(
            policy["id"],
            list(OPEN),
            "PAID",
            "paid",
            f"Paid {dollars(cents)} into checking. No claim needed.",
            paid_cents=cents,
        )

    def _payout_failed(self, policy, key, error, now):
        attempts = policy["payout_attempts"] + 1
        self.db.finish_movement(key, "failed", detail=error)
        if attempts >= self.max_attempts:
            self.db.transition(
                policy["id"],
                list(OPEN),
                "NEEDS_REVIEW",
                "payout_failed",
                f"Payout failed {attempts} times ({error}). The risk desk will send it by hand.",
                payout_attempts=attempts,
            )
            return "errors"
        retry_at = now + timedelta(minutes=2 ** attempts)
        self.db.update_policy(policy["id"], payout_attempts=attempts, next_attempt_at=retry_at.isoformat())
        self.db.add_event(policy["id"], "payout_retry", f"Payout attempt {attempts} failed ({error}). Retrying automatically.")
        return "errors"
