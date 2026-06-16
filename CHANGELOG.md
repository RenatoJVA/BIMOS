# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-06-14

### Added

- Initial release of BIMOS (Biomolecular Modeling Suite)
- CLI interface with 6 commands: `predict`, `predict-boltz`, `dock`, `workflow`, `qm-orca`, `qm-g16`
- Desktop GUI with pywebview + React frontend
- REST API (FastAPI) with endpoints for jobs, prediction, docking, simulation
- Molecular docking pipeline (AutoDock Vina via container)
- MD simulation pipeline (GROMACS via container)
- Protein structure prediction (ESMFold, Boltz-1 via container)
- Quantum chemistry pipeline (ORCA, Gaussian)
- Job store with JSON persistence and concurrent access
- Container runtime abstraction (Podman/Docker)
- Virtual screening with ChEMBL and phytocompound datasets
- PostgreSQL ligand database support
- Comprehensive test suite: 197 tests (unit, integration, E2E, security, performance, mutation)
- CI/CD pipeline with GitHub Actions (lint, unit, integration, security, coverage)
- Pre-commit hooks (ruff, mypy, bandit, format, secrets)
- Static analysis with ruff (69 rules), mypy strict mode, bandit
- Code coverage at 68 % (100 % on pure-logic modules)
- Nuitka-based build for standalone executables
- Cross-platform installers: NSIS (Windows), DMG (macOS), DEB (Linux)
