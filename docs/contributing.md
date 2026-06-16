# Contributing

See [`CONTRIBUTING.md`](https://github.com/ucsm/bimos/blob/main/CONTRIBUTING.md) and [`VERSIONING.md`](https://github.com/ucsm/bimos/blob/main/VERSIONING.md) for the full contribution guidelines.

## Quick Checklist

1. `ruff check bimos/` — zero errors
2. `mypy bimos/ --strict` — no new errors
3. `bandit -r bimos/ -ll` — zero findings
4. `pytest tests/unit/ tests/integration/` — all passing
5. Coverage ≥ 75 %
