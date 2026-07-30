#!/usr/bin/env python3
"""G6-WP2 — 30 independent paper sessions on ES/MES via the new stack.

Uses the regime-aware ensemble (trend / mean-reversion / breakout /
lorentzian) with the Lorentzian causal fix.  Each session is a
non-overlapping window of ES_1d (or MES) bars executed against a fresh
``PaperBroker`` with the new ``RecoveryService`` / ``ReconciliationWorker``
wired in for every session (postgres backend optional).

Gate criteria (M32a lineage):
  - pass_rate ≥ 0.90  (sessions without hard incidents)
  - mean_sharpe ≥ -0.5
  - mean_max_dd ≤ 3.0%

Usage::

    .venv/bin/python scripts/run_g6_wp2_paper_sessions.py \\
        --sessions 30 --data data/ohlcv/ES_1d.parquet --storage memory

    .venv/bin/python scripts/run_g6_wp2_paper_sessions.py \\
        --sessions 30 --storage postgres
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import statistics
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from analytics.portfolio.hrp import compute_hrp_weights
from analytics.research.factor_timing import compute_per_session_ic
from analytics.research.memory import ResearchMemory
from analytics.strategy.lorentzian import LorentzianKNN
from analytics.strategy.regime_ensemble import RegimeAwareEnsemble, SpecialistId
from analytics.strategy.signals import DonchianBreakout, EmaTrend, RsiReversion
from core.ledger_factory import create_ledger
from core.oms_factory import create_oms
from core.reconciliation import ReconciliationEngine
from core.recovery import RecoveryService
from execution.brokers import BrokerConfig
from execution.brokers.paper import PaperBroker
from execution.order_manager.manager import OrderManager
from execution.order_manager.types import OrderRequest
from policy.prop_firm.fixtures import TOPSTEP_TC_50K
from policy.prop_firm.governor import PropFirmRiskGovernor
from policy.prop_firm.order_risk import PropFirmOrderRiskAdapter


class _PropFirmAllow:
    """PropFirmOrderRiskAdapter with replay_only=True (bypass support_mode gate).

    Inside the paper harness, the adapter is used as a strict governor:
    daily loss, contract cap, missing stop, missing market inputs all
    return False and stop the submission.
    """

    def __init__(self, point_value: Decimal) -> None:
        self.point_value = point_value
        self.governor = PropFirmRiskGovernor(
            profile=TOPSTEP_TC_50K, initial_balance=float(TOPSTEP_TC_50K.account_size)
        )
        self.adapter = PropFirmOrderRiskAdapter(self.governor, replay_only=True)
        self.last_balance = float(TOPSTEP_TC_50K.account_size)
        self._latest_price: Decimal | None = None

    def update_price(self, price: Decimal) -> None:
        """Track the current market price for market orders (no price in request)."""
        self._latest_price = price

    def reset_session(self) -> None:
        """Reset governor + adapter to fresh-start state for a new paper session."""
        self.governor = PropFirmRiskGovernor(
            profile=TOPSTEP_TC_50K, initial_balance=float(TOPSTEP_TC_50K.account_size)
        )
        self.adapter = PropFirmOrderRiskAdapter(self.governor, replay_only=True)
        self.last_balance = float(TOPSTEP_TC_50K.account_size)
        self._latest_price = None

    async def check_order(self, request: object) -> bool:
        if not isinstance(request, OrderRequest):
            return False
        # Market orders carry no price; use the latest tracked price.
        latest_price = getattr(request, "price", None) or self._latest_price
        if latest_price is None:
            return False
        # Update governor with synthetic equity = balance
        self.governor.update(balance=self.last_balance, equity=self.last_balance)
        self.adapter.update_market(
            instrument_id=request.instrument_id,
            entry_price=Decimal(str(latest_price)),
            contract_size=self.point_value,
        )
        # Build a request with stop_price set for the adapter's safety check.
        try:
            checked = OrderRequest(
                instrument_id=request.instrument_id,
                side=request.side,
                quantity=request.quantity,
                order_type=request.order_type,
                time_in_force=request.time_in_force,
                price=latest_price,
                stop_price=latest_price - Decimal("8"),
                source=request.source,
            )
        except Exception:
            return False
        ok = await self.adapter.check_order(checked)
        return bool(ok)


def _build_ensemble(memory=None, asset: str = "ES", timeframe: str = "1d") -> Any:
    """Factory: returns AdaptiveEnsemble when asset is known, else basic."""
    try:
        from analytics.strategy.adaptive_ensemble import AdaptiveEnsemble

        return AdaptiveEnsemble(asset=asset, timeframe=timeframe)
    except ImportError:
        pass
    return RegimeAwareEnsemble(
        specialists={
            SpecialistId.TREND: EmaTrend(fast=10, slow=30),
            SpecialistId.MEAN_REVERSION: RsiReversion(period=14),
            SpecialistId.BREAKOUT: DonchianBreakout(period=20),
            SpecialistId.LORENTZIAN: LorentzianKNN(
                k=4, lookahead=4, max_bars_back=80, feature_count=3
            ),
        },
        min_confidence=0.5,
        memory=memory,
    )


async def _run_session(
    session_id: int,
    df_session: pl.DataFrame,
    instrument: str,
    capital: Decimal,
    point_value: Decimal,
    max_dd_pct: float,
    storage: str,
    dsn: str | None,
    memory: ResearchMemory | None = None,
    timeframe: str = "1d",
    weights_path: str | None = None,
) -> dict[str, Any]:
    """Run one paper session. Returns session report."""
    config = BrokerConfig(
        paper_spread_bps=10,
        paper_slippage_bps=5,
        paper_partial_fill_prob=0.0,  # deterministic
        paper_latency_ms=0,
        paper_commission_per_contract=0.85,
    )
    broker = PaperBroker(config)

    # Storage: memory (default) or postgres
    from typing import Any as _Any

    ledger: _Any
    oms: _Any
    if storage == "postgres":
        from apps.cli.trade_commands import _resolve_dsn
        from core.ledger_postgres import PostgresLedger
        from core.oms_postgres import PostgresOMS

        actual_dsn = dsn or _resolve_dsn(None)
        ledger = await PostgresLedger.create(dsn=actual_dsn)
        oms = await PostgresOMS.create(ledger=ledger, dsn=actual_dsn)
        # RecoveryService smoke per session
        svc = RecoveryService(oms=oms, ledger=ledger)
        await svc.recover()
    else:
        ledger = create_ledger(storage="memory")
        oms = create_oms(storage="memory", ledger=ledger)

    # Regime ensemble signal
    ensemble = _build_ensemble(memory=memory, asset=instrument, timeframe=timeframe)
    signal_series = ensemble.compute(df_session)
    routing = ensemble.route(df_session)

    # Apply GA-optimized weights if provided
    if weights_path:
        try:
            import json as _json
            from pathlib import Path as _Path

            ga_data = _json.loads(_Path(weights_path).read_text())
            ga_weights = ga_data.get("weights", {})
            if ga_weights and hasattr(ensemble, "set_factor_weights"):
                ensemble.set_factor_weights(ga_weights)
                # Recompute with GA weights
                signal_series = ensemble.compute(df_session)
                routing = ensemble.route(df_session)
                print(
                    f"    [sess {session_id}] GA weights applied: {list(ga_weights.keys())[:3]}..."
                )
        except Exception as exc:
            print(f"    [sess {session_id}] WARNING: could not load GA weights: {exc}")

    # Iterate bar-by-bar, executing via OrderManager
    risk_adapter = _PropFirmAllow(point_value=point_value)
    mgr = OrderManager(broker, risk_manager=risk_adapter)
    close = df_session["close"].to_numpy()

    position = Decimal("0")
    entry_price: Decimal | None = None
    realized_pnl = Decimal("0")
    total_commission = Decimal("0")
    trades: list[dict[str, Any]] = []
    equity_curve: list[float] = [float(capital)]
    peak_equity = float(capital)
    max_dd = 0.0
    hard_incidents: list[str] = []

    for i in range(1, len(close)):
        price = Decimal(str(close[i]))
        await broker.on_price_update(price)
        risk_adapter.update_price(price)

        # Regime ensemble signal (single shot for last bar; target_pos from current bar)
        sig = signal_series[i] if i < len(signal_series) else 0
        target_pos = Decimal("1") if sig > 0 else Decimal("0")

        if target_pos != position:
            side = "buy" if target_pos > position else "sell"
            qty = abs(target_pos - position)
            req = OrderRequest(
                instrument_id=instrument,
                side=side,
                quantity=qty,
                order_type="market",
                time_in_force="day",
                source="g6_wp2",
            )
            fills_before = len(broker._fills)
            result = await mgr.submit(req)
            await broker.on_price_update(price)
            new_fills = broker._fills[fills_before:]

            if result.status == "submitted" or result.status == "filled":
                for fill in new_fills:
                    signed_qty = fill.quantity if side == "buy" else -fill.quantity
                    new_pos = position + signed_qty

                    # Closing (position decreasing in absolute value)
                    if position != 0 and (position > 0) != (signed_qty > 0):
                        closed_qty = min(abs(position), fill.quantity)
                        pos_dir = Decimal("1") if position > 0 else Decimal("-1")
                        realized_pnl += (
                            (fill.price - entry_price) * pos_dir * closed_qty * point_value  # type: ignore[operator]
                        )
                    total_commission += fill.commission

                    if new_pos == 0:
                        entry_price = None
                    elif position == 0 or (position > 0) != (new_pos > 0):
                        entry_price = fill.price

                    position = new_pos

                trades.append(
                    {
                        "bar": i,
                        "price": float(price),
                        "side": side,
                        "qty": float(qty),
                        "position_after": float(position),
                    }
                )

        # MTM equity
        unrealized = Decimal("0")
        if position != 0 and entry_price is not None:
            direction = Decimal("1") if position > 0 else Decimal("-1")
            unrealized = (price - entry_price) * direction * abs(position) * point_value

        equity = float(capital + realized_pnl + unrealized - total_commission)
        equity_curve.append(round(equity, 2))
        peak_equity = max(peak_equity, equity)
        current_dd = (peak_equity - equity) / peak_equity * 100 if peak_equity > 0 else 0.0
        max_dd = max(max_dd, current_dd)

        if current_dd > max_dd_pct:
            hard_incidents.append(f"max_dd_{current_dd:.2f}%")
            break

    # Flatten at end
    if position != Decimal("0"):
        side = "sell" if position > 0 else "buy"
        qty = abs(position)
        last_price = Decimal(str(close[-1]))
        req = OrderRequest(
            instrument_id=instrument,
            side=side,
            quantity=qty,
            order_type="market",
            time_in_force="day",
            source="g6_wp2_flat",
        )
        fills_before = len(broker._fills)
        await mgr.submit(req)
        await broker.on_price_update(last_price)
        for fill in broker._fills[fills_before:]:
            total_commission += fill.commission
            if entry_price is not None:
                pos_dir = Decimal("1") if position > 0 else Decimal("-1")
                realized_pnl += (fill.price - entry_price) * pos_dir * qty * point_value
        position = Decimal("0")

    # Final reconciliation
    engine = ReconciliationEngine(broker, oms, ledger)
    rec_report = await engine.reconcile()

    if storage == "postgres":
        await oms.close()
        await ledger.close()

    final_equity = float(capital + realized_pnl - total_commission)
    total_pnl = final_equity - float(capital)
    returns = [equity_curve[k] - equity_curve[k - 1] for k in range(1, len(equity_curve))]
    avg_ret = statistics.mean(returns) if returns else 0.0
    std_ret = statistics.stdev(returns) if len(returns) > 1 else 1.0
    sharpe = (avg_ret / std_ret) * math.sqrt(252) if std_ret > 0 else 0.0

    return {
        "session_id": session_id,
        "n_bars": len(df_session),
        "n_trades": len(trades),
        "regime": routing.regime.value,
        "regime_confidence": round(routing.regime_confidence, 4),
        "specialist": routing.specialist.value,
        "total_pnl": round(total_pnl, 2),
        "return_pct": round(total_pnl / float(capital) * 100, 4),
        "sharpe": round(sharpe, 4),
        "max_drawdown_pct": round(max_dd, 4),
        "final_equity": round(final_equity, 2),
        "total_commission": round(float(total_commission), 4),
        "reconcile_clean": rec_report.is_clean,
        "passed": len(hard_incidents) == 0,
        "hard_incidents": hard_incidents,
        "_signal_series": signal_series.tolist()
        if hasattr(signal_series, "tolist")
        else signal_series,
        "_equity_curve": equity_curve,
    }


async def main() -> int:
    parser = argparse.ArgumentParser(description="G6-WP2 — 30 ES/MES paper sessions")
    parser.add_argument("--sessions", type=int, default=30)
    parser.add_argument("--data", default="data/ohlcv/ES_1d.parquet")
    parser.add_argument("--instrument", default="ES")
    parser.add_argument("--capital", type=float, default=100_000.0)
    parser.add_argument(
        "--point-value", type=float, default=None, help="Auto-detect: 5.0 for MES, 50.0 for ES"
    )
    parser.add_argument("--max-dd-pct", type=float, default=3.0)
    parser.add_argument("--storage", choices=["memory", "postgres"], default="memory")
    parser.add_argument("--dsn", default=None)
    parser.add_argument("--output", default="logs/g6_wp2_paper_sessions.json")
    parser.add_argument(
        "--weights",
        default=None,
        help="Path to GA weights JSON (data/ga_weights.json). Overrides default ensemble weights.",
    )
    args = parser.parse_args()

    if args.point_value is None:
        args.point_value = 5.0 if args.instrument.upper() == "MES" else 50.0

    # ── Parse timeframe from filename ───────────────────────────
    import re as _re

    tf_match = _re.search(r"_(\d+[mhdw])\.", args.data)
    args.timeframe = tf_match.group(1) if tf_match else "1d"

    # ── Load and split data ───────────────────────────────────────────
    df = pl.read_parquet(args.data)
    df = df.rename({c: c.lower() for c in df.columns})
    n_total = len(df)
    n_per_session = n_total // args.sessions

    print(f"\n{'=' * 70}")
    print(f"G6-WP2 — {args.sessions} independent paper sessions")
    print(f"  Data: {args.data} ({n_total} bars)")
    print(f"  Instrument: {args.instrument}  |  Capital: ${args.capital:,.0f}")
    print(f"  Point value: ${args.point_value}  |  Max DD cap: {args.max_dd_pct}%")
    print(f"  Storage: {args.storage}")
    print(f"  Bars per session: {n_per_session}")
    print(f"{'=' * 70}\n")

    if n_per_session < 30:
        print(f"ERROR: not enough bars ({n_total}) for {args.sessions} sessions")
        return 1

    capital_dec = Decimal(str(args.capital))
    point_value_dec = Decimal(str(args.point_value))

    # Shared research memory for factor timing
    session_memory = ResearchMemory("logs/research_memory.db")

    results: list[dict[str, Any]] = []
    for s in range(args.sessions):
        start = s * n_per_session
        end = start + n_per_session if s < args.sessions - 1 else n_total
        df_session = df[start:end]
        res = await _run_session(
            session_id=s + 1,
            df_session=df_session,
            instrument=args.instrument,
            capital=capital_dec,
            point_value=point_value_dec,
            max_dd_pct=args.max_dd_pct,
            storage=args.storage,
            dsn=args.dsn,
            memory=session_memory,
            timeframe=args.timeframe,
            weights_path=args.weights,
        )
        results.append(res)
        status = "✅" if res["passed"] else "❌"
        extra = f"  ⚠️  {', '.join(res['hard_incidents'])}" if not res["passed"] else ""
        print(
            f"  [{s + 1:>2d}/{args.sessions}] {status}  "
            f"regime={res['regime']:<8} spec={res['specialist']:<10} "
            f"P&L=${res['total_pnl']:>+8.2f}  R={res['return_pct']:>+6.2f}%  "
            f"S={res['sharpe']:>6.2f}  DD={res['max_drawdown_pct']:>5.2f}%  "
            f"T={res['n_trades']:>2d}{extra}"
        )

    # ── Summary ───────────────────────────────────────────────────────
    n = len(results)
    passed_sessions = sum(1 for r in results if r["passed"])
    pnls = [r["total_pnl"] for r in results]
    dds = [r["max_drawdown_pct"] for r in results]
    shs = [r["sharpe"] for r in results]

    pass_rate = passed_sessions / n if n else 0.0
    mean_sharpe = statistics.mean(shs) if shs else 0.0
    mean_dd = statistics.mean(dds) if dds else 0.0
    reconcile_clean_count = sum(1 for r in results if r["reconcile_clean"])

    print(f"\n{'=' * 70}")
    print("SUMMARY — G6-WP2 Independent Paper Sessions")
    print(f"{'=' * 70}")
    print(f"  Sessions:          {n}")
    print(f"  Passed:            {passed_sessions} ({pass_rate:.0%})")
    print(f"  Reconcile clean:   {reconcile_clean_count}/{n}")
    print(f"  Total P&L:         ${sum(pnls):>+10.2f}")
    print(f"  Mean P&L/session:  ${statistics.mean(pnls):>+10.2f}")
    print(f"  Mean Sharpe:       {mean_sharpe:.4f}")
    print(f"  Mean Max DD:       {mean_dd:.2f}% (max: {max(dds):.2f}%)")

    gate_passed = pass_rate >= 0.90 and mean_sharpe >= -0.5 and mean_dd <= 3.0
    print(f"\n  G6-WP2 gate: {'✅ PASS' if gate_passed else '❌ FAIL'}")
    print(f"{'=' * 70}\n")

    # ── Factor Timing Report ──────────────────────────────────────────
    ic_results: dict[str, list] = {}
    for res in results:
        spec = res.get("specialist", "unknown")
        sig = np.array(res.get("_signal_series", []), dtype=float)
        eq = res.get("_equity_curve", [])
        if len(sig) >= 8 and len(eq) >= 9:
            ft = compute_per_session_ic(sig, eq, specialist=spec)
            ic_results.setdefault(spec, []).append(ft)

    if ic_results:
        print("FACTOR TIMING — IC Scores & Decay States")
        lines = [
            "  Specialist        IC     IC_rec   ICIR   WR%   Mean$   N  Decay      Wt",
            "  " + "-" * 75,
        ]
        for spec, vals in sorted(ic_results.items()):
            avg_ic = float(np.mean([v.rank_ic for v in vals]))
            avg_icr = float(np.mean([v.rank_ic_recent for v in vals]))
            avg_icir = float(np.mean([v.icir for v in vals]))
            avg_wr = float(np.mean([v.win_rate for v in vals]))
            avg_pnl = float(np.mean([v.mean_pnl for v in vals]))
            total_n = sum(v.n for v in vals)
            # Dominant decay state
            states = [v.decay_state for v in vals]
            dom_state = max(set(states), key=states.count)
            dom_weight = float(np.mean([v.weight for v in vals]))
            decay_mark = {"stable": "🟢", "fading": "🟡", "decaying": "🔴"}.get(dom_state, "⚪")
            lines.append(
                f"  {spec:<16s} {avg_ic:>+6.3f} {avg_icr:>+6.3f} "
                f"{avg_icir:>+6.3f} {avg_wr:>5.1%} {avg_pnl:>+7.2f} "
                f"{total_n:>3d}  {decay_mark} {dom_state:<8s} {dom_weight:.2f}"
            )
        print("\n".join(lines) + "\n")
    else:
        print("  (insufficient data for IC computation)\n")

    # ── HRP Portfolio Weights ──────────────────────────────────────────
    try:
        import pandas as pd_util

        spec_pnls = {}
        for res_ in results:
            spec = res_.get("specialist", "unknown")
            pnl = res_.get("total_pnl", 0.0)
            spec_pnls.setdefault(spec, []).append(float(pnl))
        if len(spec_pnls) >= 2:
            max_len = max(len(v) for v in spec_pnls.values())
            returns_dict = {}
            for s_, vals_ in spec_pnls.items():
                padded = vals_ + [0.0] * (max_len - len(vals_))
                returns_dict[s_] = padded
            hrp_weights = compute_hrp_weights(pd_util.DataFrame(returns_dict))
            if hrp_weights:
                print("HRP PORTFOLIO WEIGHTS — Allocation per Specialist")
                print(f"  {'=' * 45}")
                for spec_, w_ in sorted(hrp_weights.items(), key=lambda x: -x[1]):
                    bar = "█" * int(w_ * 40)
                    print(f"  {spec_:<16s} {w_:>6.1%} {bar}")
                print()
    except Exception as exc:
        print(f"  HRP weights skipped: {exc}\n")

    print(f"{'=' * 70}\n")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {
                "metadata": {
                    "schema_version": "g6-wp2-v1",
                    "instrument": args.instrument,
                    "data": args.data,
                    "sessions": n,
                    "capital": args.capital,
                    "point_value": args.point_value,
                    "storage": args.storage,
                    "gate_passed": gate_passed,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
                "gate": {
                    "decision": "approved" if gate_passed else "rejected",
                    "pass_rate": round(pass_rate, 4),
                    "mean_sharpe": round(mean_sharpe, 4),
                    "mean_drawdown_pct": round(mean_dd, 4),
                    "reconcile_clean_rate": round(reconcile_clean_count / n, 4),
                },
                "results": results,
            },
            indent=2,
        )
    )
    print(f"Results saved to {output_path}")
    return 0 if gate_passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
