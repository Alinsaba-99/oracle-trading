"""Deterministic event-driven replay through risk, OMS, broker, and ledger."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from decimal import ROUND_CEILING, Decimal
from math import sqrt
from time import perf_counter
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import polars as pl

from analytics.backtest.protocol import BacktestSignal
from analytics.qualification.models import (
    ExecutionEvidence,
    IntelligenceArtifact,
    ReplayMetrics,
    ReplayObservation,
    ReplayPeriod,
    ReplayVariant,
)
from analytics.qualification.statistics import (
    bootstrap_luck_p_value,
    factor_attribution,
    returns_from_values,
)
from core.ledger import InMemoryLedger
from core.oms import Fill, InMemoryOMS, Order
from core.reconciliation import ReconciliationEngine
from execution.brokers.paper_engine import (
    FUTURES_CONFIG,
    FillModelConfig,
    PaperFillResult,
    RealisticPaperFillEngine,
)
from execution.brokers.types import BrokerOrder, BrokerPosition
from execution.order_manager.types import OrderRequest
from market.contracts import ContractSpec
from policy.prop_firm.fixtures import TOPSTEP_TC_50K
from policy.prop_firm.governor import Breach, PropFirmRiskGovernor
from policy.prop_firm.order_risk import PropFirmOrderRiskAdapter
from policy.prop_firm.profile import FirmProgramProfile

ENGINE_NAME = "oracle-event-driven-paper-v1"


@dataclass
class _Position:
    quantity: Decimal = Decimal("0")
    entry_price: Decimal = Decimal("0")
    stop_price: Decimal | None = None


@dataclass
class _Audit:
    risk_checks: int = 0
    risk_approvals: int = 0
    risk_rejections: int = 0
    rule_evaluations: int = 0
    orders_persisted: int = 0
    fills_recorded: int = 0
    closed_trades: int = 0
    fill_rejections: int = 0
    execution_cost: Decimal = Decimal("0")
    turnover_notional: Decimal = Decimal("0")
    decision_latencies_ms: list[float] = field(default_factory=list)
    execution_latencies_ms: list[float] = field(default_factory=list)


class QualificationPaperBroker:
    """Independent deterministic broker state used by the replay reconciler."""

    def __init__(self, *, engine: RealisticPaperFillEngine, initial_cash: Decimal) -> None:
        self._engine = engine
        self._cash = initial_cash
        self._positions: dict[str, _Position] = {}
        self._open_orders: dict[str, BrokerOrder] = {}
        self._sequence = 0

    def submit(self, order: Order) -> str:
        """Register one broker-side working order."""
        self._sequence += 1
        broker_order_id = f"qualification-paper-{self._sequence}"
        self._open_orders[broker_order_id] = BrokerOrder(
            broker_order_id=broker_order_id,
            local_order_id=order.order_id,
            namespaced_id=f"paper:{broker_order_id}",
            instrument_id=order.instrument_id,
            side=order.side,
            quantity=order.quantity,
            price=order.price,
            status="submitted",
            created_at=order.created_at.isoformat(),
        )
        return broker_order_id

    def simulate_fill(self, order: Order, reference_price: Decimal) -> PaperFillResult:
        """Run the configured realistic fill model for a submitted order."""
        return self._engine.simulate_fill(
            order.instrument_id,
            float(reference_price),
            int(order.quantity),
            order.order_type,
            limit_price=float(order.price) if order.order_type == "limit" and order.price else None,
            side=order.side,
        )

    def reject(self, broker_order_id: str) -> None:
        """Remove a rejected order from the working set."""
        self._open_orders.pop(broker_order_id, None)

    def apply_fill(self, order: Order, result: PaperFillResult, *, realized_pnl: Decimal) -> None:
        """Update broker cash and positions independently from the Oracle ledger."""
        if not result.filled:
            raise ValueError("Cannot apply an unfilled paper result")
        signed_fill = result.fill_quantity if order.side == "buy" else -result.fill_quantity
        current = self._positions.get(order.instrument_id, _Position())
        new_quantity = current.quantity + signed_fill
        if current.quantity == 0 or _same_sign(current.quantity, signed_fill):
            total_quantity = abs(current.quantity) + abs(signed_fill)
            average = (
                (current.entry_price * abs(current.quantity) + result.fill_price * abs(signed_fill))
                / total_quantity
                if total_quantity
                else Decimal("0")
            )
        elif new_quantity == 0 or _same_sign(current.quantity, new_quantity):
            average = current.entry_price if new_quantity else Decimal("0")
        else:
            average = result.fill_price
        self._positions[order.instrument_id] = _Position(new_quantity, average)
        # BL-023: futures fills do NOT move the full notional — only P&L
        # and commission are cash flows (margin is separate). The previous
        # cash-equity model (price*quantity) debited the entire contract
        # value on entry, which pushed the balance below the prop-firm
        # floor on the first fill of any MES/ES observation and produced
        # bogus hard breaches and drawdowns.
        self._cash += realized_pnl - result.commission
        self._open_orders.pop(str(order.broker_order_id), None)

    async def positions(self) -> list[BrokerPosition]:
        """Return non-flat broker positions for reconciliation."""
        return [
            BrokerPosition(
                instrument_id=instrument_id,
                quantity=position.quantity,
                avg_price=position.entry_price,
            )
            for instrument_id, position in self._positions.items()
            if position.quantity != 0
        ]

    async def open_orders(self) -> list[BrokerOrder]:
        """Return broker-side working orders for reconciliation."""
        return list(self._open_orders.values())

    async def account_summary(self) -> dict[str, Decimal]:
        """Return independently maintained broker cash."""
        return {"cash": self._cash}


class EventDrivenQualificationRunner:
    """Replay one control variant with next-bar execution and auditable state flow."""

    def __init__(
        self,
        *,
        signal: BacktestSignal,
        contract: ContractSpec,
        initial_capital: Decimal,
        symbol: str | None = None,
        quantity: Decimal = Decimal("1"),
        seed: int = 42,
        stop_distance_points: Decimal = Decimal("5"),
        stop_mode: str = "fixed",
        atr_multiple: float = 2.0,
        atr_period: int = 14,
        fill_config: FillModelConfig | None = None,
        prop_profile: FirmProgramProfile = TOPSTEP_TC_50K,
        profile_certified: bool = False,
        periods_per_year: int = 252,
        liquidate_on_hard_breach: bool = True,
    ) -> None:
        if initial_capital <= 0:
            raise ValueError("initial_capital must be positive")
        if quantity <= 0 or quantity != quantity.to_integral_value():
            raise ValueError("Qualification quantity must be a positive whole contract count")
        if stop_distance_points <= 0:
            raise ValueError("stop_distance_points must be positive")
        if stop_mode not in ("fixed", "atr"):
            raise ValueError("stop_mode must be 'fixed' or 'atr'")
        if atr_multiple <= 0:
            raise ValueError("atr_multiple must be positive")
        if atr_period < 2:
            raise ValueError("atr_period must be at least 2")
        if periods_per_year <= 0:
            raise ValueError("periods_per_year must be positive")
        self._signal = signal
        self._contract = contract
        self._initial_capital = initial_capital
        self._symbol = symbol or contract.root_symbol
        self._quantity = quantity
        self._seed = seed
        self._stop_distance_points = stop_distance_points
        self._stop_mode = stop_mode
        self._atr_multiple = atr_multiple
        self._atr_period = atr_period
        self._periods_per_year = periods_per_year
        self._liquidate_on_hard_breach = liquidate_on_hard_breach
        self._prop_profile = prop_profile
        self._profile_certified = profile_certified
        self._fill_config = fill_config or replace(
            FUTURES_CONFIG, market_fill_prob=1.0, partial_fill_prob=0.0, reject_prob=0.0
        )

    @staticmethod
    def supports(
        variant: ReplayVariant, intelligence_artifact: IntelligenceArtifact | None = None
    ) -> bool:
        """Require a matching artifact for every non-control intelligence branch."""
        return variant == ReplayVariant.control() or (
            intelligence_artifact is not None
            and intelligence_artifact.variant_name == variant.name
            and intelligence_artifact.causal
        )

    async def run(
        self,
        data: pl.DataFrame,
        period: ReplayPeriod,
        variant: ReplayVariant,
        intelligence_artifact: IntelligenceArtifact | None = None,
    ) -> ReplayObservation:
        """Execute an immutable period through the complete local paper state chain."""
        if not self.supports(variant, intelligence_artifact):
            raise ValueError(
                f"Event-driven runner cannot fabricate intelligence variant {variant.name}"
            )
        if intelligence_artifact is not None and intelligence_artifact.period_name != period.name:
            raise ValueError("Intelligence artifact does not match the replay period")
        _validate_data(data)

        started = perf_counter()
        governor = PropFirmRiskGovernor(self._prop_profile, float(self._initial_capital))
        risk = PropFirmOrderRiskAdapter(governor, replay_only=True)
        ledger = InMemoryLedger()
        account = ledger.create_account(
            account_type="paper", initial_balance=self._initial_capital, mode="qualification"
        )
        oms = InMemoryOMS(ledger=ledger, futures=True)
        broker = QualificationPaperBroker(
            engine=RealisticPaperFillEngine(self._fill_config, seed=self._seed),
            initial_cash=self._initial_capital,
        )
        audit = _Audit()
        position = _Position()
        breaches: list[Breach] = []
        equity_values = [float(self._initial_capital)]
        rows = data.to_dicts()
        period_start_index = next(
            (index for index, row in enumerate(rows) if _as_utc(row["timestamp"]) >= period.start),
            None,
        )
        if period_start_index is None:
            raise ValueError("Replay data does not reach the requested period start")
        execution_start_index = max(1, period_start_index)
        profile_tz = (
            ZoneInfo(self._prop_profile.daily_loss_reset_timezone)
            if self._prop_profile.daily_loss_reset_timezone
            else UTC
        )
        current_day = (
            _as_utc(rows[execution_start_index]["timestamp"]).astimezone(profile_tz).date()
        )
        strategy_id = f"m31-{variant.name}"
        liquidated = False

        for execution_index in range(execution_start_index, len(rows)):
            decision_started = perf_counter()
            execution_time = _as_utc(rows[execution_index]["timestamp"])
            # BL-307/ENG F-09: daily-loss rollover must fire in the profile's
            # reset timezone (Topstep: America/Chicago), not UTC — otherwise
            # the intraday session is split at midnight UTC on 1h data.
            if execution_time.astimezone(profile_tz).date() != current_day:
                governor.rollover()
                current_day = execution_time.astimezone(profile_tz).date()

            prefix = data.slice(0, execution_index)
            signal_values = self._signal.compute(prefix)
            if len(signal_values) != prefix.height:
                raise ValueError("Signal output must remain aligned with every replay prefix")
            target = int(signal_values[-1])
            if target not in (-1, 0, 1):
                raise ValueError(f"Signal emitted invalid target position {target}")

            # BL-307/ENG F-01: after a hard breach the account is liquidated —
            # no new trades, position forced flat for the rest of the period.
            if liquidated:
                target = 0

            row = rows[execution_index]
            reference_price = _price(row, "open")
            position_sign = _sign(position.quantity)
            if position.quantity != 0 and target != position_sign:
                position = self._close_position(
                    position=position,
                    reference_price=reference_price,
                    event_time=execution_time,
                    account_id=account.account_id,
                    broker=broker,
                    oms=oms,
                    governor=governor,
                    audit=audit,
                    strategy_id=strategy_id,
                )
            if target != 0 and position.quantity == 0:
                # BL-023 P1a: ATR is computed point-in-time on the data
                # prefix (bars strictly before the current execution bar),
                # never on the full slice — no lookahead.
                atr_value = _atr(prefix, self._atr_period) if self._stop_mode == "atr" else None
                position = await self._open_position(
                    target=target,
                    reference_price=reference_price,
                    event_time=execution_time,
                    account_id=account.account_id,
                    broker=broker,
                    oms=oms,
                    risk=risk,
                    audit=audit,
                    strategy_id=strategy_id,
                    atr_value=atr_value,
                )
            stop_fill_price = _stop_fill_price(position, row)
            if stop_fill_price is not None:
                position = self._close_position(
                    position=position,
                    reference_price=stop_fill_price,
                    event_time=execution_time,
                    account_id=account.account_id,
                    broker=broker,
                    oms=oms,
                    governor=governor,
                    audit=audit,
                    strategy_id=strategy_id,
                )

            balance = ledger.get_balance(account.account_id)
            equity = balance + _unrealized_pnl(
                position, _price(row, "close"), self._contract.point_value
            )
            governor.update(float(balance), float(equity))
            bar_breaches = governor.evaluate()
            breaches.extend(bar_breaches)
            audit.rule_evaluations += 1

            # BL-307/ENG F-01: hard breach → liquidate immediately. Close any
            # open position at the current close, force flat, no new trades
            # for the rest of the period (target forced to 0 above).
            if (
                self._liquidate_on_hard_breach
                and not liquidated
                and any(b.severity == "hard" for b in bar_breaches)
            ):
                liquidated = True
                if position.quantity != 0:
                    position = self._close_position(
                        position=position,
                        reference_price=_price(row, "close"),
                        event_time=execution_time,
                        account_id=account.account_id,
                        broker=broker,
                        oms=oms,
                        governor=governor,
                        audit=audit,
                        strategy_id=strategy_id,
                    )
                balance = ledger.get_balance(account.account_id)
                equity = balance
                governor.update(float(balance), float(equity))
                audit.rule_evaluations += 1

            equity_values.append(float(equity))
            audit.decision_latencies_ms.append((perf_counter() - decision_started) * 1000.0)

        if position.quantity != 0:
            final_started = perf_counter()
            final_row = rows[-1]
            position = self._close_position(
                position=position,
                reference_price=_price(final_row, "close"),
                event_time=_as_utc(final_row["timestamp"]),
                account_id=account.account_id,
                broker=broker,
                oms=oms,
                governor=governor,
                audit=audit,
                strategy_id=strategy_id,
            )
            final_balance = ledger.get_balance(account.account_id)
            governor.update(float(final_balance), float(final_balance))
            breaches.extend(governor.evaluate())
            audit.rule_evaluations += 1
            equity_values[-1] = float(final_balance)
            audit.decision_latencies_ms.append((perf_counter() - final_started) * 1000.0)

        reconciliation = await ReconciliationEngine(broker, oms, ledger).reconcile()
        strategy_returns = returns_from_values(equity_values)
        market_prices = [float(row["close"]) for row in rows[max(0, execution_start_index - 1) :]]
        market_returns = returns_from_values(market_prices)
        final_equity = ledger.get_balance(account.account_id)
        broker_cash = (await broker.account_summary())["cash"]
        ledger_entry_delta = sum(
            (entry.amount for entry in ledger.get_entries(account.account_id)), Decimal("0")
        )
        ledger_cash_delta = final_equity - self._initial_capital
        broker_cash_delta = broker_cash - self._initial_capital
        economic_parity = (
            reconciliation.is_clean
            and position.quantity == 0
            and broker_cash == final_equity
            and ledger_entry_delta == ledger_cash_delta
            and broker_cash_delta == ledger_cash_delta
        )
        max_drawdown = _max_drawdown(equity_values)
        net_return = float((final_equity - self._initial_capital) / self._initial_capital)
        execution_cost = float(audit.execution_cost)
        initial_capital = float(self._initial_capital)
        warnings = [
            "Official prop rules are exercised through an explicit historical replay-only gate.",
            "Offline intelligence artifacts are deterministic and make no external model calls.",
        ]
        if not economic_parity:
            warnings.append("Independent broker cash and ledger economics did not reconcile.")
        if audit.risk_rejections:
            warnings.append(f"Risk gate rejected {audit.risk_rejections} opening orders.")
        if audit.fill_rejections:
            warnings.append(f"Paper broker rejected {audit.fill_rejections} submitted orders.")
        if position.quantity != 0:
            warnings.append(f"Replay ended with unflattened position {position.quantity}.")
        if liquidated:
            warnings.append(
                "Observation liquidated on hard breach — position closed at "
                "bar close, trading halted for the remainder of the period."
            )

        return ReplayObservation(
            period_name=period.name,
            regime=period.regime,
            variant_name=variant.name,
            engine=ENGINE_NAME,
            component_path="signal-prefix->next-bar->risk->oms->paper->ledger->reconciliation",
            metrics=ReplayMetrics(
                net_return=net_return,
                sharpe_ratio=_sharpe(strategy_returns, periods_per_year=self._periods_per_year),
                sortino_ratio=_sortino(strategy_returns, periods_per_year=self._periods_per_year),
                calmar_ratio=_calmar(
                    net_return,
                    max_drawdown,
                    len(strategy_returns),
                    periods_per_year=self._periods_per_year,
                ),
                max_drawdown=max_drawdown,
                # BL-307/ENG F-10: count events, not distinct breach types.
                # With liquidation, an observation is either liquidated (1
                # hard breach, the first one) or not (0).
                hard_breaches=1 if liquidated else 0,
                soft_breaches=len(
                    {breach.type for breach in breaches if breach.severity == "soft"}
                ),
                liquidated=liquidated,
                turnover=float(audit.turnover_notional) / initial_capital,
                execution_cost=execution_cost,
                execution_cost_ratio=execution_cost / initial_capital,
                model_cost_usd=(
                    intelligence_artifact.model_cost_usd
                    if intelligence_artifact is not None
                    else 0.0
                ),
                decision_latency_ms_p95=_p95(audit.decision_latencies_ms),
                factor_attribution=factor_attribution(strategy_returns, market_returns),
                luck_p_value=bootstrap_luck_p_value(
                    strategy_returns, periods_per_year=self._periods_per_year
                ),
                total_trades=audit.closed_trades,
                bars=len(rows) - execution_start_index,
                engine_runtime_ms=(perf_counter() - started) * 1000.0,
            ),
            execution_evidence=ExecutionEvidence(
                risk_checks=audit.risk_checks,
                risk_approvals=audit.risk_approvals,
                risk_rejections=audit.risk_rejections,
                rule_evaluations=audit.rule_evaluations,
                orders_persisted=audit.orders_persisted,
                fills_recorded=audit.fills_recorded,
                ledger_entries=len(ledger.get_entries(account.account_id)),
                reconciliation_runs=1,
                reconciliation_mismatches=len(reconciliation.mismatches),
                reconciliation_clean=reconciliation.is_clean,
                flattened=position.quantity == 0,
                final_position_quantity=float(position.quantity),
                simulated_execution_latency_ms_p95=_p95(audit.execution_latencies_ms),
                profile_key=self._prop_profile.version_key,
                profile_certified=self._profile_certified,
                economic_parity_verified=economic_parity,
                independent_cash_delta=float(broker_cash_delta),
                ledger_cash_delta=float(ledger_cash_delta),
                intelligence_artifact=intelligence_artifact,
            ),
            warnings=warnings,
            returns_for_luck_test=strategy_returns.tolist(),
        )

    async def _open_position(
        self,
        *,
        target: int,
        reference_price: Decimal,
        event_time: datetime,
        account_id: str,
        broker: QualificationPaperBroker,
        oms: InMemoryOMS,
        risk: PropFirmOrderRiskAdapter,
        audit: _Audit,
        strategy_id: str,
        atr_value: Decimal | None = None,
    ) -> _Position:
        side = "buy" if target > 0 else "sell"
        stop_price = self._protective_stop(reference_price, target, atr_value)
        request = OrderRequest(
            instrument_id=self._symbol,
            side=side,
            quantity=self._quantity,
            order_type="market",
            price=reference_price,
            stop_price=stop_price,
            source="qualification",
            strategy_id=strategy_id,
        )
        risk.update_market(self._symbol, reference_price, self._contract.point_value)
        audit.risk_checks += 1
        allowed = await risk.check_order(request)
        if not allowed:
            audit.risk_rejections += 1
            reason = risk.last_check.reason if risk.last_check else "Risk gate rejected order"
            oms.create_order(
                Order(
                    account_id=account_id,
                    client_order_id=request.request_id,
                    instrument_id=self._symbol,
                    side=side,
                    quantity=self._quantity,
                    price=reference_price,
                    stop_price=stop_price,
                    status="rejected",
                    source="qualification-risk-gate",
                    strategy_id=strategy_id,
                    reject_reason=reason,
                    created_at=event_time,
                    updated_at=event_time,
                )
            )
            audit.orders_persisted += 1
            return _Position()

        audit.risk_approvals += 1
        result = self._execute_order(
            side=side,
            quantity=self._quantity,
            reference_price=reference_price,
            event_time=event_time,
            account_id=account_id,
            source="qualification-open",
            broker=broker,
            oms=oms,
            audit=audit,
            strategy_id=strategy_id,
        )
        if result is None:
            return _Position()
        fill_result, _ = result
        signed_quantity = fill_result.fill_quantity if target > 0 else -fill_result.fill_quantity
        return _Position(signed_quantity, fill_result.fill_price, stop_price)

    def _close_position(
        self,
        *,
        position: _Position,
        reference_price: Decimal,
        event_time: datetime,
        account_id: str,
        broker: QualificationPaperBroker,
        oms: InMemoryOMS,
        governor: PropFirmRiskGovernor,
        audit: _Audit,
        strategy_id: str,
    ) -> _Position:
        side = "sell" if position.quantity > 0 else "buy"
        quantity = abs(position.quantity)
        result = self._execute_order(
            side=side,
            quantity=quantity,
            reference_price=reference_price,
            event_time=event_time,
            account_id=account_id,
            source="qualification-reduce-only",
            broker=broker,
            oms=oms,
            audit=audit,
            closing_position=position,
            strategy_id=strategy_id,
        )
        if result is None:
            return position
        fill_result, realized_pnl = result
        remaining = position.quantity + (
            fill_result.fill_quantity if side == "buy" else -fill_result.fill_quantity
        )
        governor.record_trade(float(realized_pnl - fill_result.commission))
        audit.closed_trades += int(remaining == 0)
        return _Position(
            remaining,
            position.entry_price if remaining else Decimal("0"),
            position.stop_price if remaining else None,
        )

    def _execute_order(
        self,
        *,
        side: str,
        quantity: Decimal,
        reference_price: Decimal,
        event_time: datetime,
        account_id: str,
        source: str,
        broker: QualificationPaperBroker,
        oms: InMemoryOMS,
        audit: _Audit,
        closing_position: _Position | None = None,
        strategy_id: str,
    ) -> tuple[PaperFillResult, Decimal] | None:
        order = oms.create_order(
            Order(
                account_id=account_id,
                client_order_id=f"{source}-{audit.orders_persisted + 1}-{event_time.isoformat()}",
                instrument_id=self._symbol,
                side=side,
                order_type="market",
                quantity=quantity,
                price=reference_price,
                source=source,
                strategy_id=strategy_id,
                created_at=event_time,
                updated_at=event_time,
            )
        )
        audit.orders_persisted += 1
        broker_order_id = broker.submit(order)
        submitted = oms.update_order(
            Order(
                **{
                    **order.__dict__,
                    "broker_order_id": broker_order_id,
                    "status": "submitted",
                    "updated_at": event_time,
                }
            )
        )
        result = broker.simulate_fill(submitted, reference_price)
        audit.execution_latencies_ms.append(result.latency_ms)
        if not result.filled:
            audit.fill_rejections += 1
            broker.reject(broker_order_id)
            oms.update_order(
                Order(
                    **{
                        **submitted.__dict__,
                        "status": "rejected",
                        "reject_reason": result.rejection_reason,
                        "updated_at": event_time,
                    }
                )
            )
            return None

        realized_pnl = _realized_pnl(closing_position, result, self._contract.point_value)
        # The Fill's ``side`` is the side of the order that generated
        # this fill, which equals the side of the order just submitted
        # to the broker.  This matches what the broker does in
        # ``QualificationPaperBroker.apply_fill`` (which uses
        # ``order.side`` to determine cash direction).  Without
        # explicitly forwarding ``side`` here, the OMS/ledger would
        # default to "buy" and the broker/ledger cash would diverge.
        fill = Fill(
            order_id=submitted.order_id,
            account_id=account_id,
            broker_fill_id=f"{broker_order_id}-fill-1",
            quantity=result.fill_quantity,
            price=result.fill_price,
            commission=result.commission,
            realized_pnl=realized_pnl,
            side=submitted.side,
            fill_time=event_time,
            idempotency_key=f"{broker_order_id}-fill-1",
        )
        oms.record_fill(fill)
        broker.apply_fill(submitted, result, realized_pnl=realized_pnl)
        audit.fills_recorded += 1
        audit.execution_cost += result.commission + (
            abs(result.fill_price - reference_price)
            * self._contract.point_value
            * result.fill_quantity
        )
        audit.turnover_notional += self._contract.notional_value(
            result.fill_price, result.fill_quantity
        )
        return result, realized_pnl

    def _protective_stop(
        self, entry_price: Decimal, target: int, atr_value: Decimal | None = None
    ) -> Decimal:
        # BL-023 P1a: in ATR mode the stop distance is atr_multiple * ATR
        # (point-in-time, computed on the prefix), falling back to the
        # fixed-point distance only when no ATR value is available (e.g.
        # insufficient history) — the fixed distance is still the explicit
        # floor so a degenerate ATR can never produce a zero-distance stop.
        if self._stop_mode == "atr" and atr_value is not None and atr_value > 0:
            distance = atr_value * Decimal(str(self._atr_multiple))
        else:
            distance = Decimal(str(self._stop_distance_points))
        ticks = (distance / self._contract.tick_size).to_integral_value(rounding=ROUND_CEILING)
        distance = max(ticks, Decimal("1")) * self._contract.tick_size
        return entry_price - distance if target > 0 else entry_price + distance


def _validate_data(data: pl.DataFrame) -> None:
    required = {"timestamp", "open", "high", "low", "close", "volume"}
    missing = sorted(required - set(data.columns))
    if missing:
        raise ValueError(f"Event-driven replay is missing columns: {', '.join(missing)}")
    if data.height < 3:
        raise ValueError("Event-driven replay requires at least three bars")


def _price(row: dict[str, Any], column: str) -> Decimal:
    value = row.get(column, row.get("close"))
    return Decimal(str(value))


def _as_utc(value: object) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"Replay timestamp must be datetime, got {type(value).__name__}")
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _same_sign(left: Decimal, right: Decimal) -> bool:
    return (left >= 0 and right >= 0) or (left <= 0 and right <= 0)


def _sign(value: Decimal) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _unrealized_pnl(position: _Position, price: Decimal, point_value: Decimal) -> Decimal:
    if position.quantity == 0:
        return Decimal("0")
    return (price - position.entry_price) * point_value * position.quantity


def _stop_fill_price(position: _Position, row: dict[str, Any]) -> Decimal | None:
    if position.quantity == 0 or position.stop_price is None:
        return None
    open_price = _price(row, "open")
    if position.quantity > 0:
        if open_price <= position.stop_price:
            return open_price
        return position.stop_price if _price(row, "low") <= position.stop_price else None
    if open_price >= position.stop_price:
        return open_price
    return position.stop_price if _price(row, "high") >= position.stop_price else None


def _atr(data: pl.DataFrame, period: int) -> Decimal | None:
    """Point-in-time Average True Range on the last bar of a prefix slice.

    True range is max(high-low, |high-prev_close|, |low-prev_close|),
    smoothed with a simple rolling mean over ``period`` bars. Only bars
    already in the prefix are used, so there is no lookahead. Returns
    ``None`` when the prefix is too short to produce a value.
    """
    if data.height < 2:
        return None
    prev_close = data["close"].shift(1)
    tr = pl.DataFrame(
        {
            "tr1": data["high"] - data["low"],
            "tr2": (data["high"] - prev_close).abs(),
            "tr3": (data["low"] - prev_close).abs(),
        }
    ).max_horizontal()
    window = min(period, data.height)
    atr_series = tr.rolling_mean(window_size=window, min_samples=window)
    value = atr_series[-1]
    if value is None:
        return None
    return Decimal(str(value))


def _realized_pnl(
    position: _Position | None, result: PaperFillResult, point_value: Decimal
) -> Decimal:
    if position is None:
        return Decimal("0")
    signed_quantity = result.fill_quantity if position.quantity > 0 else -result.fill_quantity
    return (result.fill_price - position.entry_price) * point_value * signed_quantity


def _max_drawdown(values: list[float]) -> float:
    if not values:
        return 0.0
    peak = values[0]
    worst = 0.0
    for value in values:
        peak = max(peak, value)
        if peak > 0:
            worst = max(worst, (peak - value) / peak)
    return worst


def _sharpe(returns: np.ndarray[Any, Any], *, periods_per_year: int = 252) -> float:
    if returns.size < 2:
        return 0.0
    deviation = float(np.std(returns, ddof=1))
    return float(np.mean(returns)) / deviation * sqrt(periods_per_year) if deviation > 0 else 0.0


def _sortino(returns: np.ndarray[Any, Any], *, periods_per_year: int = 252) -> float:
    if returns.size < 2:
        return 0.0
    downside = returns[returns < 0]
    deviation = float(np.std(downside, ddof=1)) if downside.size > 1 else 0.0
    return float(np.mean(returns)) / deviation * sqrt(periods_per_year) if deviation > 0 else 0.0


def _calmar(
    net_return: float, max_drawdown: float, periods: int, *, periods_per_year: int = 252
) -> float:
    if max_drawdown <= 0 or periods <= 0 or net_return <= -1:
        return 0.0
    annualized = float((1.0 + net_return) ** (periods_per_year / periods) - 1.0)
    return float(annualized / max_drawdown)


def _p95(values: list[float]) -> float | None:
    if not values:
        return None
    return float(np.percentile(np.asarray(values, dtype=float), 95))
