.PHONY: install dev lint format typecheck test test-cov clean docker-up docker-down precommit

# Python
install:
	pip install -e ".[all]"

dev:
	pip install -e ".[dev]"

lint:
	ruff check .

lint-fix:
	ruff check --fix .

format:
	ruff format .

typecheck:
	mypy core/ market/ analytics/ execution/ genetics/ research/ agents/ audit/ policy/ orchestration/

test:
	pytest tests/ -v

test-cov:
	pytest tests/ --cov=core --cov=market --cov=analytics --cov-report=term-missing

test-fast:
	pytest tests/ -v -m "not slow"

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v

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
	pre-commit run --all-files

precommit-install:
	pre-commit install

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
