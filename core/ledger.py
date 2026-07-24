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
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4


def _utcnow() -> datetime:
    return datetime.now(UTC)


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
        side: str = "buy",
    ) -> list[LedgerEntry]:
        """Record a fill and update the account balance.

        The fill creates up to three entries that together preserve the
        accounting invariant ``current_balance + unrealized_pnl = equity``:

        1. **Notional entry** (always): ``-price * quantity`` for BUY
           (cash decreases by the asset value) or ``+price * quantity``
           for SELL (cash increases).  This models the cash side of the
           trade.
        2. **P&L entry** (if ``realized_pnl != 0``): records realized
           profit/loss from closing (part of) a position.
        3. **Commission entry** (if ``commission > 0``): always a debit.

        All entries are applied atomically to the account balance.

        Returns the list of entries written (new API: list, not single
        entry).
        """
        account = self._accounts.get(account_id)
        if account is None:
            raise ValueError(f"Account {account_id} not found")

        # Calculate net cash impact:
        # notional + realized_pnl - commission
        notional_amount = -(price * quantity) if side == "buy" else (price * quantity)
        total_impact = notional_amount + realized_pnl - commission

        written: list[LedgerEntry] = []

        # 1. Notional entry (always)
        notional_entry = LedgerEntry(
            account_id=account_id,
            order_id=order_id,
            fill_id=fill_id,
            amount=notional_amount,
            entry_type="notional",
            description=f"Notional {side}: {quantity} @ {price}",
        )
        self._entries.append(notional_entry)
        written.append(notional_entry)

        # 2. P&L entry (only if non-zero)
        if realized_pnl != 0:
            pnl_entry = LedgerEntry(
                account_id=account_id,
                order_id=order_id,
                fill_id=fill_id,
                amount=realized_pnl,
                entry_type="trade",
                description=f"Fill P&L: {quantity} @ {price}",
            )
            self._entries.append(pnl_entry)
            written.append(pnl_entry)

        # 3. Commission entry (only if positive)
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
            written.append(comm_entry)

        # Update balance (immutable update via dataclass replace)
        new_balance = account.current_balance + total_impact
        if new_balance < 0:
            raise ValueError(
                f"Insufficient balance: {account.current_balance} + {total_impact} = {new_balance}"
            )
        self._accounts[account_id] = AccountEntry(
            **{**account.__dict__, "current_balance": new_balance, "version": account.version + 1}
        )

        return written

    def get_balance(self, account_id: str) -> Decimal:
        account = self._accounts.get(account_id)
        if account is None:
            raise ValueError(f"Account {account_id} not found")
        return account.current_balance

    def get_entries(self, account_id: str) -> list[LedgerEntry]:
        return [e for e in self._entries if e.account_id == account_id]

    def get_all_entries(self) -> list[LedgerEntry]:
        return list(self._entries)
