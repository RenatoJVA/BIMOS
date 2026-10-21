# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `bimos doctor`: read-only hardware report that grades every process green / yellow / red against the active configuration. `--json` emits machine-readable output for dashboards and CI.
- Hardware guardrail on every pipeline command (`predict`, `predict-boltz`, `dock`, `workflow`, `screen`, `qm-orca`, `qm-g16`). Red aborts with an actionable message; `--force` overrides it.
- `--model` for `bimos predict`, accepting `boltz1` or `boltz2`. An existing `boltz.yaml` without the key keeps working and warns that it carries Boltz-1 values.
- `tools/validate_dockerfile.py`: static validation of the Dockerfiles (instruction syntax, shell and embedded Python, checksum-verified downloads, no unpinned clones), so image changes are checked without a CUDA host.

### Changed

- Boltz 2.2.1 is the default model, replacing the previous `git clone` of the repository head. Upstream pins its own dependencies, so a given build tag always installs the same release. This also clears CVE-2025-70560 (HIGH, insecure deserialization in Boltz's molecule loading, which affected every release up to 2.0.0).
- `confidence.json` discovery is recursive and supports the Boltz-2 output layout, with deterministic tie-breaking between models.
- The scientific image is reproducible: GROMACS 2025.4 and AutoDock Vina 1.2.5 are downloaded over a pinned SHA-256, Boltz and Meeko come from PyPI, and no download failure is silenced. Optional Boltz fused kernels are opt-in (`--build-arg INSTALL_BOLTZ_KERNELS=ON`).
- The scientific image runtime stage no longer ships a compiler or Python headers; the GROMACS builder is the only stage that needs one.
- `bimos doctor --json` now emits only JSON, with `viable` and `blocked_processes` fields.

### Fixed

- Gaussian `mem` is parsed with its unit. `32GB` was read as 0.03 GB, so the `qm-g16` guard could never block on the packaged default.
- `qm-g16` is graded against the Gaussian configuration instead of inheriting ORCA's memory and job count. `bimos screen` does the same for the backend selected with `--qm`.
- `bimos screen` checks the configured Vina thread count instead of skipping the CPU check.

## [0.1.0] - 2026-06-14

### Added

- Initial release of BIMOS (Biomolecular Modeling Suite)
- CLI interface with 6 commands: `predict`, `predict-boltz`, `dock`, `workflow`, `qm-orca`, `qm-g16`
- Desktop GUI with pywebview + React frontend
- REST API (FastAPI) with endpoints for jobs, prediction, docking, simulation
- Molecular docking pipeline (AutoDock Vina via container)
- MD simulation pipeline (GROMACS via container)
- Protein structure prediction (Boltz via container)
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
