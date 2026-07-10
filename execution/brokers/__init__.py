"""Broker adapters — protocol, config, base, paper, and registry."""

from __future__ import annotations

from execution.brokers.base import BaseBroker
from execution.brokers.ccxt_broker import CCXTBroker
from execution.brokers.config import BrokerConfig
from execution.brokers.ibkr import IBKRBroker
from execution.brokers.paper import PaperBroker
from execution.brokers.protocol import BrokerProtocol
from execution.brokers.registry import BrokerRegistry

__all__ = [
    "BaseBroker",
    "BrokerConfig",
    "BrokerProtocol",
    "BrokerRegistry",
    "CCXTBroker",
    "IBKRBroker",
    "PaperBroker",
]
