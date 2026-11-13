# Development

## Project Structure

```
backend/
├── bimos/
│   ├── cli/              # Click command-line interface
│   ├── api/              # FastAPI REST server
│   ├── config/           # Configuration & settings
│   ├── docking/          # AutoDock Vina pipeline
│   ├── prediction/       # Boltz pipeline
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

# Desktop installers (run from the repository root, inside the pixi env)
cd backend && pixi run builder                 # linux / windows / macos
cd backend && pixi run builder --skip-nuitka   # repackage without recompiling
cd backend && pixi run verify                  # audit the artifacts
```

Always invoke the builder through `pixi run`. Calling the environment's Python
directly leaves the pixi `bin/` out of `PATH`, and Nuitka then fails with
`standalone mode on Linux requires 'patchelf'`.

`fpm` is **not** part of the pixi environment; it is a host dependency that the
CI installs before the build (`gem install fpm`). The gem is tied to the Ruby
version that installed it: after a distribution upgrade from Ruby 3.2 to 3.3,
the old binstub keeps a `#!/usr/bin/ruby3.2` shebang and dies with
`bad interpreter`. Reinstall it for the current interpreter with
`gem install --user-install fpm --no-document` and add the resulting directory
(`~/.local/share/gem/ruby/<version>/bin`) to `PATH`.
