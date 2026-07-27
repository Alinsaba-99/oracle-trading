#!/usr/bin/env python3
"""End-to-end smoke: regime ensemble → paper broker ES/MES → Postgres ledger.

This is the G6 wire-up validation: one full pass through the new stack
built on 2026-07-25.

Run::

    .venv/bin/python scripts/run_regime_paper_smoke.py
    .venv/bin/python scripts/run_regime_paper_smoke.py --instrument MES --storage postgres
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _parse() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--instrument", default="ES", choices=["ES", "MES"])
    p.add_argument("--data", default="data/ohlcv/ES_1d.parquet")
    p.add_argument("--storage", default="memory", choices=["memory", "postgres"])
    p.add_argument("--dsn", default=None)
    return p.parse_args()


async def main() -> int:
    args = _parse()

    import polars as pl

    from analytics.strategy.lorentzian import LorentzianKNN
    from analytics.strategy.regime_ensemble import RegimeAwareEnsemble, SpecialistId
    from analytics.strategy.signals import DonchianBreakout, EmaTrend, RsiReversion
    from core.ledger_factory import create_ledger
    from core.oms_factory import create_oms
    from core.reconciliation import ReconciliationEngine
    from core.recovery import RecoveryService
    from execution.brokers import BrokerConfig
    from execution.brokers.paper import PaperBroker

    print(f"=== G6 regime-ensemble → paper smoke (instrument={args.instrument}) ===")

    # ── 1. Load data ──────────────────────────────────────────────────
    df = pl.read_parquet(args.data)
    # Normalise cols to lowercase for the ensemble/specialists
    df = df.rename({c: c.lower() for c in df.columns})
    print(f"[1] data: {len(df)} bars, cols={df.columns}")

    # ── 2. Build ensemble with all four specialists ───────────────────
    ensemble = RegimeAwareEnsemble(
        specialists={
            SpecialistId.TREND: EmaTrend(fast=10, slow=30),
            SpecialistId.MEAN_REVERSION: RsiReversion(period=14),
            SpecialistId.BREAKOUT: DonchianBreakout(period=20),
            SpecialistId.LORENTZIAN: LorentzianKNN(
                k=4, lookahead=4, max_bars_back=100, feature_count=3
            ),
        }
    )
    decision = ensemble.route(df)
    print(
        f"[2] routing: regime={decision.regime.value} conf={decision.regime_confidence:.2f} "
        f"→ specialist={decision.specialist.value}"
    )

    signal = ensemble.compute(df)
    long_bars = sum(1 for v in signal.to_numpy() if v > 0)
    flat_bars = sum(1 for v in signal.to_numpy() if v == 0)
    print(f"[3] signal: {long_bars} long bars / {flat_bars} flat bars")

    # ── 3. Storage (memory or postgres) ───────────────────────────────
    from typing import Any as _Any

    ledger: _Any
    oms: _Any
    if args.storage == "postgres":
        from apps.cli.trade_commands import _resolve_dsn
        from core.ledger_postgres import PostgresLedger
        from core.oms_postgres import PostgresOMS

        dsn = args.dsn or _resolve_dsn(None)
        ledger = await PostgresLedger.create(dsn=dsn)
        oms = await PostgresOMS.create(ledger=ledger, dsn=dsn)
        # Restart recovery smoke
        svc = RecoveryService(oms=oms, ledger=ledger)
        rep = await svc.recover()
        print(
            f"[4] postgres recovery: {rep.accounts_loaded} accounts, "
            f"{rep.orders_loaded} orders, {len(rep.open_orders)} open"
        )
    else:
        ledger = create_ledger(storage="memory")
        oms = create_oms(storage="memory", ledger=ledger)
        print("[4] storage=memory (in-memory ledger/OMS)")

    # ── 4. Paper broker + reconcile ───────────────────────────────────
    broker = PaperBroker(BrokerConfig())
    engine = ReconciliationEngine(broker, oms, ledger)
    report = await engine.reconcile()
    status = "CLEAN" if report.is_clean else f"{len(report.mismatches)} mismatches"
    print(f"[5] reconcile: {status}")

    # ── 5. OrderManager submit smoke (1-lot ES buy, market) ───────────
    from execution.order_manager.manager import OrderManager
    from execution.order_manager.types import OrderRequest

    class _AllowAll:
        async def check_order(self, request: object) -> bool:  # noqa: ARG002
            return True

    mgr = OrderManager(broker, risk_manager=_AllowAll())
    req = OrderRequest(
        instrument_id=args.instrument,
        side="buy",
        quantity=Decimal("1"),
        order_type="market",
        time_in_force="day",
        source="smoke",
    )
    res = await mgr.submit(req)
    print(f"[6] submit: {res.status} order_id={res.order_id[:8]}…")

    # Final reconcile — should show position
    report2 = await engine.reconcile()
    print(
        f"[7] post-submit reconcile: "
        f"{'CLEAN' if report2.is_clean else f'{len(report2.mismatches)} mismatches'}"
    )

    if args.storage == "postgres":
        await oms.close()
        await ledger.close()

    print("=== smoke OK ===")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
