# OpenAPI-MCP Makefile
# Common development tasks

.PHONY: help install install-dev test lint format type-check security build clean run

# Default target
help:
	@echo "OpenAPI-MCP Development Commands"
	@echo "================================"
	@echo ""
	@echo "Setup:"
	@echo "  make install      - Install package in production mode"
	@echo "  make install-dev  - Install package with dev dependencies"
	@echo ""
	@echo "Development:"
	@echo "  make test         - Run all tests"
	@echo "  make test-cov     - Run tests with coverage report"
	@echo "  make lint         - Run linting checks"
	@echo "  make format       - Format code with black and isort"
	@echo "  make type-check   - Run mypy type checking"
	@echo "  make security     - Run security checks with bandit"
	@echo "  make check        - Run all checks (lint, type-check, security, test)"
	@echo ""
	@echo "Build:"
	@echo "  make build        - Build package for distribution"
	@echo "  make clean        - Remove build artifacts"
	@echo ""
	@echo "Run:"
	@echo "  make run          - Run the MCP server (requires OPENAPI_URL env var)"
	@echo "  make run-example  - Run with example Petstore API"

# Installation
install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"
	pip install black isort flake8 bandit mypy pre-commit
	pre-commit install

# Testing
test:
	PYTHONPATH=src pytest test/ -v

test-cov:
	PYTHONPATH=src pytest test/ -v --cov=src/openapi_mcp --cov-report=term-missing --cov-report=html

# Code quality
lint:
	flake8 src/openapi_mcp --max-line-length=120 --ignore=E501,W503,E203
	isort --check-only --profile=black --line-length=120 src/openapi_mcp

format:
	black --line-length=120 src/openapi_mcp
	isort --profile=black --line-length=120 src/openapi_mcp

type-check:
	mypy src/openapi_mcp --ignore-missing-imports

security:
	bandit -r src/openapi_mcp -c pyproject.toml

# Run all checks
check: lint type-check security test
	@echo "All checks passed!"

# Build
build: clean
	python -m build

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf src/*.egg-info
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

# Run server
run:
	@if [ -z "$$OPENAPI_URL" ]; then \
		echo "Error: OPENAPI_URL environment variable is required"; \
		echo "Example: OPENAPI_URL=https://petstore3.swagger.io/api/v3/openapi.json make run"; \
		exit 1; \
	fi
	python -m openapi_mcp.fastmcp_server

run-example:
	OPENAPI_URL=https://petstore3.swagger.io/api/v3/openapi.json \
	SERVER_NAME=petstore \
	python -m openapi_mcp.fastmcp_server
