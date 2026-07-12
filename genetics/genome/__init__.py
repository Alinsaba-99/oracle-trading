"""Genome module — GP expression encoding and DEAP bridge."""

from genetics.genome.expression_codec import (
    create_primitive_set,
    expr_to_gp_tree,
    gp_tree_to_expr,
    random_expression,
    tree_to_string,
)

__all__ = [
    "create_primitive_set",
    "expr_to_gp_tree",
    "gp_tree_to_expr",
    "random_expression",
    "tree_to_string",
]
