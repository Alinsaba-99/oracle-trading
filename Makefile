.PHONY: install dev lint lint-fix format typecheck test test-venv test-cov test-fast test-unit test-integration docker-up docker-down docker-logs docker-build precommit precommit-install clean fresh docs-tree setup-hooks

# Python
install:
	uv sync --frozen --all-extras --all-groups

dev:
	uv sync --frozen --all-groups

lint:
	uv run --frozen ruff check .

lint-fix:
	uv run --frozen ruff check --fix .

format:
	uv run --frozen ruff format .

typecheck:
	uv run --frozen mypy core/ market/ analytics/ execution/ genetics/ research/ agents/ audit/ policy/ orchestration/

test:
	uv run --frozen pytest tests/ -v

test-venv:
	@if [ ! -x ".venv/bin/python" ]; then \
		echo "ERROR: .venv/bin/python not found. Create it with:"; \
		echo "  uv sync --frozen --all-extras --all-groups"; \
		exit 1; \
	fi
	.venv/bin/python -m pytest tests/ -v

test-cov:
	uv run --frozen pytest tests/ --cov=core --cov=market --cov=analytics --cov-report=term-missing

test-fast:
	uv run --frozen pytest tests/ -v -m "not slow"

test-unit:
	uv run --frozen pytest tests/unit/ -v

test-integration:
	uv run --frozen pytest tests/integration/ -v

# Docker
docker-up:
	docker compose -f infra/docker/docker-compose.yml up -d

docker-down:
	docker compose -f infra/docker/docker-compose.yml down

docker-logs:
	docker compose -f infra/docker/docker-compose.yml logs -f

docker-build:
	docker compose -f infra/docker/docker-compose.yml build

# Pre-commit
precommit:
	uv run --frozen pre-commit run --all-files

precommit-install:
	uv run --frozen pre-commit install

# Project
clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete

fresh: clean install

# Docs
docs-tree:
	tree -I '__pycache__|*.pyc|.git|experiments' --dirsfirst -F

# Git hooks
.PHONY: setup-hooks
setup-hooks:
	git config core.hooksPath .githooks
