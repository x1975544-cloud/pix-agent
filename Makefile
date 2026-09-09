.PHONY: install dev test lint typecheck format run-api run-demo clean

install:
	uv sync --extra memory --extra dev

dev:
	uv run pix serve

test:
	uv run pytest

lint:
	uv run ruff check pix tests
	uv run ruff format --check pix tests

typecheck:
	uv run mypy pix

format:
	uv run ruff format pix tests
	uv run ruff check --fix pix tests

run-api:
	uv run uvicorn pix.api.app:app --reload

run-demo:
	bash scripts/demo.sh

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov
