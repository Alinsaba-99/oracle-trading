"""Tests for SQLite-backed ExperimentRegistry."""

from __future__ import annotations

import pytest

from core.domain.experiment import Experiment, ExperimentContext, ExperimentRegistry


class TestExperimentModel:
    def test_defaults(self) -> None:
        exp = Experiment(experiment_id="test-1", type="backtest")
        assert exp.parent_experiment_id is None
        assert exp.random_seed == 42

    def test_parent_tracking(self) -> None:
        parent = Experiment(experiment_id="parent-1", type="backtest")
        child = Experiment(
            experiment_id="child-1", type="backtest", parent_experiment_id=parent.experiment_id
        )
        assert child.parent_experiment_id == "parent-1"


class TestExperimentContextModel:
    def test_defaults(self) -> None:
        ctx = ExperimentContext()
        assert ctx.experiment_id is not None
        assert ctx.parent_experiment_id is None
        assert ctx.random_seed == 42

    def test_parent_tracking(self) -> None:
        ctx = ExperimentContext(parent_experiment_id="parent-1")
        assert ctx.parent_experiment_id == "parent-1"


class TestExperimentRegistryAsync:
    """Async tests for the SQLite-backed registry."""

    @pytest.fixture
    async def registry(self, tmp_path: pytest.TempPathFactory) -> ExperimentRegistry:
        reg = ExperimentRegistry(str(tmp_path / "experiments.db"))
        yield reg
        # ensure clean state for next test
        await reg._ensure_table()

    async def test_register_and_list(self, registry: ExperimentRegistry) -> None:
        ctx = ExperimentContext(git_commit="abc123")
        await registry.async_register(ctx)
        experiments = await registry.async_list()
        assert len(experiments) == 1
        assert experiments[0].git_commit == "abc123"

    async def test_register_multiple(self, registry: ExperimentRegistry) -> None:
        await registry.async_register(ExperimentContext(git_commit="a"))
        await registry.async_register(ExperimentContext(git_commit="b"))
        assert len(await registry.async_list()) == 2

    async def test_get_by_id(self, registry: ExperimentRegistry) -> None:
        ctx = ExperimentContext(git_commit="findme")
        await registry.async_register(ctx)
        found = await registry.async_get(ctx.experiment_id)
        assert found is not None
        assert found.git_commit == "findme"

    async def test_get_missing(self, registry: ExperimentRegistry) -> None:
        found = await registry.async_get("nonexistent")
        assert found is None

    async def test_persistence(self, tmp_path: pytest.TempPathFactory) -> None:
        db_path = str(tmp_path / "persist.db")
        reg = ExperimentRegistry(db_path)
        ctx = ExperimentContext(git_commit="persist")
        await reg.async_register(ctx)

        # New instance reads the same DB
        reg2 = ExperimentRegistry(db_path)
        experiments = await reg2.async_list()
        assert len(experiments) == 1
        assert experiments[0].git_commit == "persist"

    async def test_empty_registry(self, registry: ExperimentRegistry) -> None:
        assert await registry.async_list() == []

    async def test_parent_tracking(self, registry: ExperimentRegistry) -> None:
        parent = ExperimentContext(git_commit="parent", parent_experiment_id=None)
        await registry.async_register(parent)
        child = ExperimentContext(git_commit="child", parent_experiment_id=parent.experiment_id)
        await registry.async_register(child)

        experiments = await registry.async_list()
        assert len(experiments) == 2
        child_found = next(e for e in experiments if e.parent_experiment_id is not None)
        assert child_found.parent_experiment_id == parent.experiment_id


class TestExperimentRegistrySync:
    """Sync wrapper backward-compatibility tests."""

    def test_register_and_list(self, tmp_path: pytest.TempPathFactory) -> None:
        reg = ExperimentRegistry(str(tmp_path / "sync.db"))
        ctx = ExperimentContext(git_commit="sync-test")
        reg.register(ctx)
        experiments = reg.list()
        assert len(experiments) == 1
        assert experiments[0].git_commit == "sync-test"

    def test_get_by_id(self, tmp_path: pytest.TempPathFactory) -> None:
        reg = ExperimentRegistry(str(tmp_path / "sync-get.db"))
        ctx = ExperimentContext(git_commit="findme")
        reg.register(ctx)
        found = reg.get(ctx.experiment_id)
        assert found is not None
        assert found.git_commit == "findme"

    def test_get_missing(self, tmp_path: pytest.TempPathFactory) -> None:
        reg = ExperimentRegistry(str(tmp_path / "sync-missing.db"))
        assert reg.get("nonexistent") is None

    def test_empty_registry(self, tmp_path: pytest.TempPathFactory) -> None:
        reg = ExperimentRegistry(str(tmp_path / "sync-empty.db"))
        assert reg.list() == []
