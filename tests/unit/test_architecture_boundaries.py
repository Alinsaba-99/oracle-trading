"""Architecture boundary enforcement (P0, closes F-03 enforcement gap).

ARCHITECTURE.md §3.1 declares the dependency rule (inward-only imports);
until now nothing verified it.  This test parses the import graph via AST
and asserts that every first-party package only imports from its allowed
set.  The allowed sets encode the *current* post-P0 reality; each
remaining cross-layer allowance carries a TODO referencing the plan that
removes it (P2 cycle closure).

Rules frozen here:

* ``core`` imports NO other first-party package (kernel is leaf).
* ``market`` imports only ``core``.
* ``execution`` imports only ``core`` and ``application`` (contracts).
* ``application`` imports nothing first-party (pure contracts).
* ``research/orchestration/audit`` are leaf placeholders today.

Remaining known exceptions (tracked, not silently allowed):

* analytics -> execution (qualification parity + MetaApi provider, lazy)
* analytics -> policy (prop-firm challenge simulation)
* policy -> execution (OrderRequest adapter in order_risk.py)
* agents -> analytics/genetics/application (intelligence plane wiring)
* genetics -> analytics (fitness evaluation)

``apps`` is the composition root and may import anything.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

FIRST_PARTY = {
    "agents",
    "analytics",
    "application",
    "apps",
    "audit",
    "core",
    "execution",
    "genetics",
    "market",
    "orchestration",
    "policy",
    "research",
}

# Allowed first-party imports per package (frozen current state).
ALLOWED: dict[str, set[str]] = {
    "core": set(),
    "application": set(),
    "audit": set(),
    "research": set(),
    "orchestration": set(),
    "market": {"core"},
    "execution": {"core", "application"},
    "policy": {"execution"},  # TODO(P2): OrderRequest port in application/contracts
    "analytics": {
        "core",
        "market",
        "policy",
        "genetics",
        # TODO(P2): qualification parity port + MetaApi provider relocation
        "execution",
    },
    "genetics": {"core", "analytics"},  # TODO(P2): SearchStrategy port
    "agents": {"core", "analytics", "application", "genetics"},
    "apps": FIRST_PARTY - {"apps"},  # composition root
}


def _first_party_imports(package: str) -> dict[str, set[str]]:
    """Map relative file path -> set of first-party top-level imports."""
    base = REPO_ROOT / package
    imports: dict[str, set[str]] = {}
    if not base.is_dir():
        return imports
    for path in sorted(base.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError:
            continue
        found: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.module is None or node.level > 0:
                    continue  # relative imports stay inside the package
                names = [node.module.split(".")[0]]
            else:
                continue
            for top in names:
                if top in FIRST_PARTY and top != package:
                    found.add(top)
        if found:
            imports[str(path.relative_to(REPO_ROOT))] = found
    return imports


class TestArchitectureBoundaries:
    @pytest.mark.parametrize("package", sorted(ALLOWED))
    def test_package_respects_allowed_imports(self, package: str) -> None:
        violations: list[str] = []
        for rel_path, imported in _first_party_imports(package).items():
            for target in sorted(imported - ALLOWED[package]):
                violations.append(f"{rel_path} imports {target}")
        assert not violations, (
            f"Architecture boundary violations in '{package}' "
            f"(see docs/ARCHITECTURE.md §3.1):\n  " + "\n  ".join(violations)
        )

    def test_core_imports_no_first_party_package(self) -> None:
        """The kernel must remain a leaf — regression guard for P0 fixes.

        core.kill used to import execution.brokers.types; the broker types
        moved to core.domain.broker so this invariant holds.
        """
        assert _first_party_imports("core") == {}

    def test_market_does_not_import_analytics(self) -> None:
        """Regression guard: IngestionError moved to core.errors.data_errors."""
        imports = _first_party_imports("market")
        for rel_path, targets in imports.items():
            assert "analytics" not in targets, f"{rel_path} imports analytics"
