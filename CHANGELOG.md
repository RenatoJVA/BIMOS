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
- Optional native TLS for the API (`BIMOS_TLS_CERTFILE`/`BIMOS_TLS_KEYFILE`); both files are required together and the desktop URL switches to HTTPS.
- Ligand database API (`GET/POST /api/v1/ligands`, `PATCH/DELETE /api/v1/ligands/{cid}`), named API tokens with `admin`/`editor`/`viewer` roles, and an `/admin/ligands` panel with token management, CRUD and soft delete.
- Job result endpoints (`GET /api/v1/jobs/{job_id}/files` and `/files/{path}`) for secure PDB/TRR download, with traversal and workspace checks.

### Changed

- Boltz 2.2.1 is the default model, replacing the previous `git clone` of the repository head. Upstream pins its own dependencies, so a given build tag always installs the same release. This also clears CVE-2025-70560 (HIGH, insecure deserialization in Boltz's molecule loading, which affected every release up to 2.0.0).
- `confidence.json` discovery is recursive and supports the Boltz-2 output layout, with deterministic tie-breaking between models.
- The scientific image is reproducible: GROMACS 2025.4 and AutoDock Vina 1.2.5 are downloaded over a pinned SHA-256, Boltz and Meeko come from PyPI, and no download failure is silenced. Optional Boltz fused kernels are opt-in (`--build-arg INSTALL_BOLTZ_KERNELS=ON`).
- The scientific image runtime stage no longer ships a compiler or Python headers; the GROMACS builder is the only stage that needs one.
- The ligand database adds PostgreSQL `pg_trgm` GIN indexes for leading-wildcard name/CID/SMILES searches; the existing composite index covers logP/molar-mass ranges.
- Ligands gain an `active` flag for soft delete; `init_db` adds it idempotently to existing PostgreSQL schemas.
- `bimos doctor --json` now emits only JSON, with `viable` and `blocked_processes` fields.

### Fixed

- Gaussian `mem` is parsed with its unit. `32GB` was read as 0.03 GB, so the `qm-g16` guard could never block on the packaged default.
- `qm-g16` is graded against the Gaussian configuration instead of inheriting ORCA's memory and job count. `bimos screen` does the same for the backend selected with `--qm`.
- `bimos screen` checks the configured Vina thread count instead of skipping the CPU check.
- MD minimization no longer aborts when `max_min_iterations` is reached without Fmax convergence; it logs a warning and continues with the lowest-energy structure. A completed minimization is detected by `Finished mdrun` in the log instead of the absence of a convergence error.
- `seed_ligands()` now uses a SQLAlchemy 2 `select()` instead of passing a legacy `Query` to `Session.scalars()`.
- The README, installation guide and test guide no longer advertise unpublished Windows/macOS installers or describe ESMFold as the runtime predictor.

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
