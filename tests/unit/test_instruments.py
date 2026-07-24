"""Tests for the R0.1 InstrumentRegistry."""

from __future__ import annotations

import pytest

from analytics.backtest.instruments import (
    AssetClass,
    DataSource,
    Instrument,
    InstrumentRegistry,
    ProductType,
    Venue,
    default_registry,
)


def test_default_registry_loads_all_assets() -> None:
    reg = default_registry()
    # 41 seeded instruments across all asset classes
    assert len(reg) == 41
    classes = {i.asset_class for i in reg.all()}
    assert classes == {
        AssetClass.FX,
        AssetClass.METAL,
        AssetClass.INDEX,
        AssetClass.ENERGY,
        AssetClass.RATE,
        AssetClass.CRYPTO,
    }


def test_the5ers_venue_is_cfd_spot_only() -> None:
    reg = default_registry()
    ids = {i.id for i in reg.by_venue(Venue.THE5ERS)}
    # The5ers = MT5 CFD: spot FX, spot metals, index CFDs
    assert {"EURUSD", "XAUUSD", "SP500", "NAS100"} <= ids
    # ... NOT exchange futures (those are Lucid)
    assert ids.isdisjoint({"ES", "CL", "6E", "ZN"})


def test_lucid_venue_is_futures_only() -> None:
    reg = default_registry()
    ids = {i.id for i in reg.by_venue(Venue.LUCID)}
    assert {"ES", "NQ", "CL", "GC", "6E", "ZN", "BTF"} <= ids
    # Lucid is futures-only: no spot FX / index CFD
    assert ids.isdisjoint({"EURUSD", "SP500", "XAUUSD"})


def test_free_venue_covers_everything() -> None:
    reg = default_registry()
    assert len(reg.by_venue(Venue.FREE)) == len(reg)


def test_source_filters() -> None:
    reg = default_registry()
    ccxt_ids = {i.id for i in reg.by_source(DataSource.CCXT)}
    assert ccxt_ids == {"BTC", "ETH", "SOL"}
    yf_ids = {i.id for i in reg.by_source(DataSource.YFINANCE)}
    assert {"ES", "CL", "EURUSD", "BTC"} <= yf_ids
    metaapi_ids = {i.id for i in reg.by_source(DataSource.METAAPI)}
    assert {"EURUSD", "XAUUSD", "SP500"} <= metaapi_ids


def test_get_and_membership() -> None:
    reg = default_registry()
    gold = reg.get("XAUUSD")
    assert gold.asset_class is AssetClass.METAL
    assert gold.product_type is ProductType.SPOT
    assert Venue.THE5ERS in gold.venues
    assert "XAUUSD" in reg
    assert "NOPE" not in reg


def test_duplicate_register_raises() -> None:
    reg = default_registry()
    dup = Instrument("EURUSD", "dup", AssetClass.FX, ProductType.SPOT)
    with pytest.raises(ValueError, match="duplicate"):
        reg.register(dup)


def test_instrument_is_frozen() -> None:
    from dataclasses import FrozenInstanceError

    reg = default_registry()
    gold = reg.get("XAUUSD")
    with pytest.raises(FrozenInstanceError):
        gold.name = "mutated"  # type: ignore[misc]


def test_custom_registry() -> None:
    custom = InstrumentRegistry([Instrument("FOO", "Foo", AssetClass.CRYPTO, ProductType.SPOT)])
    assert len(custom) == 1
    assert custom.get("FOO").asset_class is AssetClass.CRYPTO
