"""Durable Ledger — double-entry account state with SQL persistence.

The Ledger is the authoritative source of truth for account balances,
equity, and P&L.  Every financial event (fill, commission, deposit,
withdrawal) creates a double entry that preserves the accounting
invariant:

    assets = equity + liabilities  (simplified: balance + unrealized P&L = equity)

In the trading context:
    current_balance + unrealized_pnl = current_equity
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class AccountEntry:
    """A single account with its current balance and invariants."""

    account_id: str = field(default_factory=lambda: str(uuid4()))
    account_type: str = "paper"
    mode: str = "research"
    initial_balance: Decimal = Decimal("0")
    current_balance: Decimal = Decimal("0")
    currency: str = "USD"
    status: str = "active"
    version: int = 1
    created_at: datetime = field(default_factory=_utcnow)

    def check_invariant(self) -> bool:
        """Balance must never be negative."""
        return self.current_balance >= 0


@dataclass(frozen=True)
class LedgerEntry:
    """A single double-entry ledger line."""

    entry_id: str = field(default_factory=lambda: str(uuid4()))
    account_id: str = ""
    order_id: str | None = None
    fill_id: str | None = None

    # Debit / credit (signed: positive = credit, negative = debit)
    amount: Decimal = Decimal("0")
    currency: str = "USD"

    # Entry type
    entry_type: str = "trade"
    # trade, commission, deposit, withdrawal, fee, roll, adjustment

    description: str = ""
    created_at: datetime = field(default_factory=_utcnow)


class InMemoryLedger:
    """In-memory ledger for development/testing.

    Implements the same contract as the PostgreSQL ledger but stores
    state in Python dicts.  All operations maintain the balance
    invariant.
    """

    def __init__(self) -> None:
        self._accounts: dict[str, AccountEntry] = {}
        self._entries: list[LedgerEntry] = []

    # ── Account management ──────────────────────────────────────────────

    def create_account(
        self,
        account_type: str = "paper",
        initial_balance: Decimal = Decimal("0"),
        currency: str = "USD",
        mode: str = "research",
    ) -> AccountEntry:
        account = AccountEntry(
            account_type=account_type,
            initial_balance=initial_balance,
            current_balance=initial_balance,
            currency=currency,
            mode=mode,
        )
        self._accounts[account.account_id] = account
        return account

    def get_account(self, account_id: str) -> AccountEntry | None:
        return self._accounts.get(account_id)

    # ── Ledger entries ──────────────────────────────────────────────────

    def record_fill(
        self,
        account_id: str,
        order_id: str,
        fill_id: str,
        quantity: Decimal,
        price: Decimal,
        commission: Decimal = Decimal("0"),
        realized_pnl: Decimal = Decimal("0"),
    ) -> LedgerEntry:
        """Record a fill and update the account balance.

        The fill creates two entries:
        1. P&L entry (realized_pnl, can be positive or negative)
        2. Commission entry (always negative/debit)

        Both are applied atomically to the account balance.
        """
        account = self._accounts.get(account_id)
        if account is None:
            raise ValueError(f"Account {account_id} not found")

        # Calculate net cash impact
        # For a buy: cash decreases by (price * quantity)
        # For a sell: cash increases by (price * quantity)
        # Simplified: we track realized P&L directly
        total_impact = realized_pnl - commission

        # Create P&L entry
        pnl_entry = LedgerEntry(
            account_id=account_id,
            order_id=order_id,
            fill_id=fill_id,
            amount=realized_pnl,
            entry_type="trade",
            description=f"Fill P&L: {quantity} @ {price}",
        )
        self._entries.append(pnl_entry)

        # Create commission entry
        if commission > 0:
            comm_entry = LedgerEntry(
                account_id=account_id,
                order_id=order_id,
                fill_id=fill_id,
                amount=-commission,
                entry_type="commission",
                description=f"Commission: {commission}",
            )
            self._entries.append(comm_entry)

        # Update balance (immutable update via dataclass replace)
        new_balance = account.current_balance + total_impact
        if new_balance < 0:
            raise ValueError(
                f"Insufficient balance: {account.current_balance} + "
                f"{total_impact} = {new_balance}"
            )
        self._accounts[account_id] = AccountEntry(
            **{**account.__dict__,
               "current_balance": new_balance,
               "version": account.version + 1}
        )

        return pnl_entry

    def get_balance(self, account_id: str) -> Decimal:
        account = self._accounts.get(account_id)
        if account is None:
            raise ValueError(f"Account {account_id} not found")
        return account.current_balance

    def get_entries(self, account_id: str) -> list[LedgerEntry]:
        return [e for e in self._entries if e.account_id == account_id]

    def get_all_entries(self) -> list[LedgerEntry]:
        return list(self._entries)
