"""Tests for Experiment Registry (ADR-007)."""

from core.domain.experiment import ExperimentContext, ExperimentRegistry


class TestExperimentContext:
    def test_defaults(self):
        ctx = ExperimentContext()
        assert ctx.experiment_id is not None
        assert ctx.random_seed == 42
        assert ctx.timestamp is not None
        assert ctx.tags == {}

    def test_custom_fields(self):
        ctx = ExperimentContext(git_commit="abc123", random_seed=7)
        assert ctx.git_commit == "abc123"
        assert ctx.random_seed == 7


class TestExperimentRegistry:
    def test_register_and_list(self, tmp_path):
        reg = ExperimentRegistry(str(tmp_path / "_registry.jsonl"))
        ctx = ExperimentContext(git_commit="abc123")
        reg.register(ctx)
        experiments = reg.list()
        assert len(experiments) == 1
        assert experiments[0].git_commit == "abc123"

    def test_register_multiple(self, tmp_path):
        reg = ExperimentRegistry(str(tmp_path / "_registry.jsonl"))
        reg.register(ExperimentContext(git_commit="a"))
        reg.register(ExperimentContext(git_commit="b"))
        assert len(reg.list()) == 2

    def test_get_by_id(self, tmp_path):
        reg = ExperimentRegistry(str(tmp_path / "_registry.jsonl"))
        ctx = ExperimentContext(git_commit="findme")
        reg.register(ctx)
        found = reg.get(ctx.experiment_id)
        assert found is not None
        assert found.git_commit == "findme"

    def test_get_missing(self, tmp_path):
        reg = ExperimentRegistry(str(tmp_path / "_registry.jsonl"))
        assert reg.get("nonexistent") is None

    def test_persistence(self, tmp_path):
        path = str(tmp_path / "_registry.jsonl")
        reg = ExperimentRegistry(path)
        ctx = ExperimentContext(git_commit="persist")
        reg.register(ctx)

        # New instance reads the same file
        reg2 = ExperimentRegistry(path)
        assert len(reg2.list()) == 1
        assert reg2.list()[0].git_commit == "persist"

    def test_empty_registry(self, tmp_path):
        reg = ExperimentRegistry(str(tmp_path / "empty.jsonl"))
        assert reg.list() == []
