"""Tests for futures ContractSpec and catalog."""

from __future__ import annotations

from decimal import Decimal

import pytest

from market.contracts import CATALOG, CL, ES, GC, MES, MNQ, NQ, get_contract, pnl_check


class TestContractSpec:
    """ContractSpec invariants and computed helpers."""

    def test_tick_value_from_tick_size(self) -> None:
        """tick_value must equal tick_size × point_value / multiplier? No — it's direct."""
        # ES: tick_size=0.25, point_value=50 → tick_value = 0.25 × 50 = 12.50
        assert ES.tick_value == Decimal("12.50")

    def test_mes_tick_value(self) -> None:
        assert MES.tick_value == Decimal("1.25")

    def test_nq_tick_value(self) -> None:
        assert NQ.tick_value == Decimal("5.00")

    def test_mnq_tick_value(self) -> None:
        assert MNQ.tick_value == Decimal("0.50")

    def test_gc_tick_value(self) -> None:
        assert GC.tick_value == Decimal("10.00")

    def test_cl_tick_value(self) -> None:
        assert CL.tick_value == Decimal("10.00")

    def test_pnl_per_point_es(self) -> None:
        assert ES.pnl_per_point(Decimal("1")) == Decimal("50")
        assert ES.pnl_per_point(Decimal("10")) == Decimal("500")
        assert ES.pnl_per_point(Decimal("0.5")) == Decimal("25")

    def test_pnl_per_point_mes(self) -> None:
        assert MES.pnl_per_point(Decimal("1")) == Decimal("5")

    def test_pnl_per_tick(self) -> None:
        assert ES.pnl_per_tick(Decimal("1")) == Decimal("12.50")
        assert ES.pnl_per_tick(Decimal("10")) == Decimal("125.00")

    def test_notional_value(self) -> None:
        # ES at 5500 with 1 contract = 5500 × 50 × 1 = 275,000
        assert ES.notional_value(Decimal("5500"), Decimal("1")) == Decimal("275000")
        # MES at 5500 with 1 contract = 5500 × 5 × 1 = 27,500
        assert MES.notional_value(Decimal("5500"), Decimal("1")) == Decimal("27500")

    def test_es_mes_ratio(self) -> None:
        """10 MES = 1 ES."""
        es_notional = ES.notional_value(Decimal("5500"), Decimal("1"))
        mes_notional = MES.notional_value(Decimal("5500"), Decimal("10"))
        assert es_notional == mes_notional


class TestCatalog:
    """Contract catalog integrity."""

    def test_all_symbols_have_spec(self) -> None:
        assert len(CATALOG) == 8

    def test_get_contract_known(self) -> None:
        spec = get_contract("ES")
        assert spec.root_symbol == "ES"
        assert spec.multiplier == Decimal("50")

    def test_get_contract_unknown(self) -> None:
        with pytest.raises(KeyError, match="Unknown contract symbol"):
            get_contract("FAKE")

    def test_pnl_check_es(self) -> None:
        """1 ES moving 10 points = $500."""
        assert pnl_check("ES", Decimal("1"), Decimal("10")) == Decimal("500")

    def test_pnl_check_mes(self) -> None:
        """1 MES moving 10 points = $50."""
        assert pnl_check("MES", Decimal("1"), Decimal("10")) == Decimal("50")

    def test_pnl_check_nq(self) -> None:
        assert pnl_check("NQ", Decimal("1"), Decimal("10")) == Decimal("200")

    def test_all_specs_have_positive_values(self) -> None:
        for symbol, spec in CATALOG.items():
            assert spec.multiplier > 0, f"{symbol} multiplier"
            assert spec.point_value > 0, f"{symbol} point_value"
            assert spec.tick_size > 0, f"{symbol} tick_size"
            assert spec.tick_value > 0, f"{symbol} tick_value"


class TestMiniMicro:
    """Mini/micro equivalence properties."""

    def test_es_mes_ratio_matches(self) -> None:
        assert ES.mini_symbol == "MES"
        assert ES.mini_ratio == Decimal("10")

    def test_nq_mnq_ratio_matches(self) -> None:
        assert NQ.mini_symbol == "MNQ"
        assert NQ.mini_ratio == Decimal("10")

    def test_gc_mgc_ratio_matches(self) -> None:
        assert GC.micro_symbol == "MGC"
        assert GC.micro_ratio == Decimal("10")

    def test_cl_mcl_ratio_matches(self) -> None:
        assert CL.micro_symbol == "MCL"
        assert CL.micro_ratio == Decimal("10")


class TestSerialization:
    """to_dict and round-trip."""

    def test_to_dict_contains_keys(self) -> None:
        d = ES.to_dict()
        assert d["root_symbol"] == "ES"
        assert d["multiplier"] == "50"
        assert d["tick_value"] == "12.50"
        assert d["settlement"] == "cash"

    def test_to_dict_decimal_as_string(self) -> None:
        d = GC.to_dict()
        assert isinstance(d["multiplier"], str)
        assert d["multiplier"] == "100"
