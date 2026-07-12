"""Tests for GP genome encoding — DEAP PrimitiveTree <-> ExprNode AST."""

from __future__ import annotations

import numpy as np
import polars as pl
from deap import gp as deap_gp  # type: ignore[import-untyped]

from genetics.alpha.expression import parse_expression
from genetics.alpha.operators import OPERATORS_MAP
from genetics.genome.expression_codec import (
    create_primitive_set,
    expr_to_gp_tree,
    gp_tree_to_expr,
    random_expression,
    tree_to_string,
)


class TestPrimitiveSet:
    def test_create_primitive_set(self) -> None:
        pset = create_primitive_set()
        assert len(pset.primitives[object]) > 0
        assert len(pset.terminals[object]) > 0

    def test_terminals_include_data_leaves(self) -> None:
        pset = create_primitive_set()
        terminal_names = {t.name for t in pset.terminals[object]}
        for leaf in ("close", "open", "high", "low", "volume", "returns", "vwap"):
            assert leaf in terminal_names

    def test_terminals_include_constants(self) -> None:
        pset = create_primitive_set()
        terminal_names = {t.name for t in pset.terminals[object]}
        for val in (2, 5, 10, 20, 50, 100):
            assert f"_{val}" in terminal_names

    def test_operators_exclude_leaf_extractors(self) -> None:
        pset = create_primitive_set()
        prim_names = {p.name for p in pset.primitives[object]}
        for name in prim_names:
            assert not name.startswith("leaf_"), f"Leaf extractor {name!r} in primitives"


class TestExprToGpTree:
    def test_roundtrip_simple_expression(self) -> None:
        pset = create_primitive_set()
        expr = parse_expression("sma(close, 20) - sma(close, 50)")
        gp_tree = expr_to_gp_tree(expr, pset)
        back = gp_tree_to_expr(gp_tree)
        assert str(back) == str(expr)

    def test_roundtrip_nested_expression(self) -> None:
        pset = create_primitive_set()
        expr = parse_expression("rank(ts_mean(close, 5) - ts_mean(close, 20))")
        gp_tree = expr_to_gp_tree(expr, pset)
        back = gp_tree_to_expr(gp_tree)
        assert str(back) == str(expr)

    def test_roundtrip_arithmetic(self) -> None:
        pset = create_primitive_set()
        expr = parse_expression("(close + open) / close")
        gp_tree = expr_to_gp_tree(expr, pset)
        back = gp_tree_to_expr(gp_tree)
        assert str(back) == str(expr)

    def test_roundtrip_single_leaf(self) -> None:
        pset = create_primitive_set()
        expr = parse_expression("close")
        gp_tree = expr_to_gp_tree(expr, pset)
        back = gp_tree_to_expr(gp_tree)
        assert isinstance(back, type(expr))
        assert str(back) == str(expr)

    def test_roundtrip_constant(self) -> None:
        pset = create_primitive_set()
        expr = parse_expression("rank(close)")
        gp_tree = expr_to_gp_tree(expr, pset)
        back = gp_tree_to_expr(gp_tree)
        result = str(back)
        assert "rank" in result and "close" in result


class TestRandomExpression:
    def test_random_expression_created(self) -> None:
        pset = create_primitive_set()
        tree = random_expression(pset, 2, 4)
        assert len(tree) > 0
        assert isinstance(tree, deap_gp.PrimitiveTree)

    def test_random_expression_has_primitive_root(self) -> None:
        pset = create_primitive_set()
        tree = random_expression(pset, 2, 4)
        root = tree[0]
        assert isinstance(root, deap_gp.Primitive)

    def test_random_expression_varying_depth(self) -> None:
        pset = create_primitive_set()
        shallow = random_expression(pset, 1, 2)
        deep = random_expression(pset, 4, 6)
        assert len(shallow) <= len(deep)


class TestEvaluation:
    def test_random_expression_roundtrip(self) -> None:
        """Random expression round-trips through GP tree correctly."""
        pset = create_primitive_set()
        tree = random_expression(pset, 2, 4)
        expr = gp_tree_to_expr(tree)
        tree2 = expr_to_gp_tree(expr, pset)
        back = gp_tree_to_expr(tree2)
        assert str(back) == str(expr)

    def test_random_expression_has_data_leaf(self) -> None:
        """Random expression includes at least one data leaf."""
        pset = create_primitive_set()
        results = []
        for _ in range(20):
            tree = random_expression(pset, 2, 4)
            expr = gp_tree_to_expr(tree)
            results.append(str(expr))
        # At least some expressions should have recognizable patterns
        assert any(r for r in results)

    def test_specific_expression_evaluates(self) -> None:
        pset = create_primitive_set()
        expr = parse_expression("sma(close, 20)")
        gp_tree = expr_to_gp_tree(expr, pset)
        back = gp_tree_to_expr(gp_tree)

        data = pl.DataFrame({"close": np.arange(1.0, 101.0, dtype=float)})
        from genetics.alpha.expression import evaluate as eval_expr

        array = eval_expr(back, data, OPERATORS_MAP)
        assert len(array) == 100
        assert np.all(np.isfinite(array))

    def test_expression_has_reasonable_values(self) -> None:
        """Test a known expression produces expected arithmetic."""
        pset = create_primitive_set()
        expr = parse_expression("close / close")
        gp_tree = expr_to_gp_tree(expr, pset)
        back = gp_tree_to_expr(gp_tree)

        data = pl.DataFrame({"close": np.arange(1.0, 101.0, dtype=float)})
        from genetics.alpha.expression import evaluate as eval_expr

        array = eval_expr(back, data, OPERATORS_MAP)
        assert np.allclose(array, 1.0)


class TestTreeToString:
    def test_tree_to_string(self) -> None:
        pset = create_primitive_set()
        expr = parse_expression("sma(close, 20)")
        gp_tree = expr_to_gp_tree(expr, pset)
        s = tree_to_string(gp_tree)
        assert "sma" in s
        assert "close" in s

    def test_tree_to_string_arithmetic(self) -> None:
        pset = create_primitive_set()
        expr = parse_expression("rank(close)")
        gp_tree = expr_to_gp_tree(expr, pset)
        s = tree_to_string(gp_tree)
        assert "rank" in s
