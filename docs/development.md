# Development

## Project Structure

```
backend/
├── bimos/
│   ├── cli/              # Click command-line interface
│   ├── api/              # FastAPI REST server
│   ├── config/           # Configuration & settings
│   ├── docking/          # AutoDock Vina pipeline
│   ├── prediction/       # ESMFold & Boltz-1 pipelines
│   ├── molecular_dynamics/  # GROMACS pipeline
│   ├── quantum_chemistry/   # ORCA & Gaussian pipelines
│   ├── infrastructure/   # Container, job store, database
│   └── shared/           # Common utilities
├── tests/                # Test suites
└── dockers/              # Dockerfiles for tools
```

## Quality Gates

Before submitting a PR, run:

```bash
ruff check bimos/
mypy bimos/ --strict
bandit -r bimos/ -ll
pytest tests/unit/ tests/integration/
```

## Building

```bash
# Python wheel
cd backend && pip install build && python -m build

# Desktop installers
python builder.py --target linux    # or macos, windows
```
