# BIMOS Backend

**Biomolecular Modeling Suite — CLI & API Server**

The BIMOS backend provides the computational engine for all structural biology and quantum chemistry pipelines. It consists of a CLI (built with Click/Rich-Click) and a FastAPI-based REST server for the Desktop Dashboard.

## Architecture

```
bimos/
├── cli/            # CLI entry point and command implementations
├── api/            # FastAPI server and REST endpoints
├── config/         # Environment and YAML configuration management
├── docking/        # AutoDock Vina pipeline
├── molecular_dynamics/  # GROMACS pipeline
├── prediction/     # ESMFold and Boltz-1 structure prediction
├── quantum_chemistry/   # ORCA and Gaussian 16 pipelines
├── infrastructure/ # Database, Docker SDK, job store, ChEMBL integration
├── shared/         # Common utilities, paths, templates
├── scripts/        # Standalone helper scripts
└── ui/             # Static frontend assets (populated by build)
```

## Development

```bash
cd backend
uv venv
uv sync
uv run bimos --help

# Run the API server
uv run python main.py gui
```

## Tech Stack

- **Python 3.12+**
- **Click** + **Rich-Click** for CLI
- **FastAPI** + **Uvicorn** for the API server
- **SQLAlchemy** + **PostgreSQL** / **SQLite** for data storage
- **Docker SDK** for containerized job execution

## Citation

If you use this backend in your research, please cite:

```bibtex
@software{bimos2025,
  author    = {Renato J. V. A. and Ponze Bellido, L. J. and Quispe Ppacco, D. J. and Carbajal, P. and Del Carpio, F. and Gómez Valdez, B.},
  title     = {BIMOS: Biomolecular Modeling Suite},
  year      = {2025},
  url       = {https://github.com/RenatoJVA/BIMOS},
  note      = {Version 0.1.0}
}
```

---

## Author

**Renato J. V. A.** — Lead Developer

## Team

- L. J. Ponze Bellido — Coauthor
- D. J. Quispe Ppacco — Coauthor
- P. Carbajal — Coauthor
- F. Del Carpio — Coauthor
- B. Gómez Valdez (Director, CIIM) — Coauthor

---

*Part of the [BIMOS](https://github.com/RenatoJVA/BIMOS) project — Biomolecular Modeling Suite.*
