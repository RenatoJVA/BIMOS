# Contributing to BIMOS

## Development Setup

```bash
git clone <repo>
cd BIMOS
uv sync --project backend/
```

## Pre-commit Hooks

```bash
pip install pre-commit
pre-commit install
```

Hooks run automatically on `git commit`: ruff (lint + format), mypy (strict), bandit (security), and general sanity checks.

## Code Standards

- Python 3.12+, type hints required on all public functions
- Google-style docstrings
- Maximum 110 characters per line
- Variable names and comments in English
- Conventional commits: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `ci:`

## Pre-merge Requirements

1. `ruff check backend/bimos/` — 0 errors
2. `mypy backend/bimos/ --strict` — 0 errors
3. `bandit -r backend/bimos/ -ll` — 0 findings (high/medium severity)
4. `pytest backend/tests/ -m "not e2e and not gpu" --ignore=backend/tests/e2e` — 100% passing
5. Overall coverage ≥ 75%
6. Coverage must not decrease in the modified module

## Running Tests

```bash
# All tests (except E2E/GPU)
pytest backend/tests/ -m "not e2e and not gpu" --ignore=backend/tests/e2e

# With coverage
pytest backend/tests/unit/ backend/tests/integration/ --cov=bimos --cov-report=html

# Security tests
pytest backend/tests/security/ -v -m security

# Mutation testing
pip install mutmut
mutmut run --paths-to-mutate backend/bimos/infrastructure/
mutmut results
```

## Git Workflow

```
main: Protected — merges only via PR with green CI and 1 reviewer
  ↑
develop: Integration branch — CI required
  ↑
feature/*: Feature branches
```

## Project Structure

```
backend/
├── bimos/              # Main package
├── tests/              # Test suites
│   ├── unit/           # Unit tests (no I/O)
│   ├── integration/    # Integration tests (mocked externals)
│   ├── security/       # Security tests
│   ├── performance/    # Performance benchmarks
│   ├── mutation/       # Mutation testing
│   ├── e2e/            # End-to-end (Docker required)
│   ├── fixtures/       # Test data files
│   └── mocks/          # External dependency mocks
└── pyproject.toml      # Project configuration
```
