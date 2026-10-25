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
- `bimos uninstall`: residue-free purge with `--dry-run`, `--yes`, `--keep-data`, `--deep`, `--remove-app`, `--include-outputs`, `--verify`, `--print-manifest`, `--json` and explicit safety guards. Exit codes distinguish success, errors, aborted confirmation and remaining residues.
- macOS portable bundle: `BIMOS-<version>-macos-arm64.tar.gz` with `BIMOS.app` (Cocoa, no Qt/CUDA), a standalone `Uninstall BIMOS.command` and `LEEME.txt`. No DMG or installer; nothing is written outside the user's home.
- `~/.bimos/paths.json` records the effective workspace/cache/log paths so the uninstaller can find overrides.
- `docs/uninstall.md`, `docs/build-macos.md` and ADR 0001 document the purge contract, the reproducible macOS build and the support scope.

### Changed

- Boltz 2.2.1 is the default model, replacing the previous `git clone` of the repository head. Upstream pins its own dependencies, so a given build tag always installs the same release. This also clears CVE-2025-70560 (HIGH, insecure deserialization in Boltz's molecule loading, which affected every release up to 2.0.0).
- `confidence.json` discovery is recursive and supports the Boltz-2 output layout, with deterministic tie-breaking between models.
- The scientific image is reproducible: GROMACS 2025.4 and AutoDock Vina 1.2.5 are downloaded over a pinned SHA-256, Boltz and Meeko come from PyPI, and no download failure is silenced. Optional Boltz fused kernels are opt-in (`--build-arg INSTALL_BOLTZ_KERNELS=ON`).
- The scientific image runtime stage no longer ships a compiler or Python headers; the GROMACS builder is the only stage that needs one.
- The ligand database adds PostgreSQL `pg_trgm` GIN indexes for leading-wildcard name/CID/SMILES searches; the existing composite index covers logP/molar-mass ranges.
- Ligands gain an `active` flag for soft delete; `init_db` adds it idempotently to existing PostgreSQL schemas.
- `bimos doctor --json` now emits only JSON, with `viable` and `blocked_processes` fields.
- macOS builds with `uv` + Xcode and the native Cocoa backend; PyQt6/QtWebEngine are Linux-only. The macOS artifact is a portable app bundle instead of a DMG.
- Linux `apt purge` and the Windows uninstaller now remove user data (the Windows installer records the installing profile); `apt remove` still keeps it.
- On Linux/Windows, pywebview state is stored under `~/.bimos/cache/webview` so the purge has a single known location.
- `bimos setup` refuses to build the CUDA image on macOS unless `--force` is passed; `--config-only` still works.

### Fixed

- Gaussian `mem` is parsed with its unit. `32GB` was read as 0.03 GB, so the `qm-g16` guard could never block on the packaged default.
- `qm-g16` is graded against the Gaussian configuration instead of inheriting ORCA's memory and job count. `bimos screen` does the same for the backend selected with `--qm`.
- `bimos screen` checks the configured Vina thread count instead of skipping the CPU check.
- MD minimization no longer aborts when `max_min_iterations` is reached without Fmax convergence; it logs a warning and continues with the lowest-energy structure. A completed minimization is detected by `Finished mdrun` in the log instead of the absence of a convergence error.
- `seed_ligands()` now uses a SQLAlchemy 2 `select()` instead of passing a legacy `Query` to `Session.scalars()`.
- The README, installation guide and test guide no longer advertise unpublished Windows/macOS installers or describe ESMFold as the runtime predictor.
- `bimos uninstall --verify` no longer recreates `~/.bimos` (the CLI first-run bootstrap is skipped and the job store creates its directory lazily), which previously made verification report a false residue.
- macOS GUI: `private_mode`/`storage_path` are only passed to `pywebview.start` on Linux/Windows; on Cocoa they made the window close immediately.
- API requests no longer fail when the optional database module is unavailable (default local install).
- macOS build hardening: Mach-O DWARF is audited with `otool`, the portable archive keeps Nuitka's detached signatures with `tar --xattrs`, and `codesign --verify --deep --strict` is part of the release audit.

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
