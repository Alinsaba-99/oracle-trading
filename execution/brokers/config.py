"""Broker configuration — shared across all broker types."""

from __future__ import annotations

from pydantic import BaseModel


class BrokerConfig(BaseModel):
    """Single configuration model for all broker types (live, paper, reconnection)."""

    # -- Active broker selection -------------------------------------------
    active_broker: str = "paper"  # paper | ibkr | ccxt

    # -- Interactive Brokers (IB Gateway / TWS) ----------------------------
    ibkr_host: str = "127.0.0.1"
    ibkr_port: int = 7497  # TWS live; 7496 for IB Gateway
    ibkr_client_id: int = 1
    ibkr_account: str = ""

    # -- CCXT (centralised exchanges) --------------------------------------
    ccxt_exchange: str = "binance"
    ccxt_api_key: str = ""
    ccxt_secret: str = ""
    ccxt_sandbox: bool = True

    # -- Paper trading (simulation) ----------------------------------------
    paper_spread_bps: int = 0  # basis points (0 = no spread)
    paper_slippage_bps: int = 50  # 0.5 %
    paper_partial_fill_prob: float = 0.0  # 0 = always full fill
    paper_latency_ms: int = 0  # 0 = no simulated latency
    paper_commission_per_contract: float = 0.0  # e.g. 0.85 for ES

    # -- Reconnection (exponential back-off) -------------------------------
    reconnect_max_retries: int = 5
    reconnect_base_delay_s: float = 1.0
    reconnect_max_delay_s: float = 60.0
