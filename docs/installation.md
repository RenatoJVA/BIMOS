# Installation

## Pre-built Installers

The Linux `.deb` is built and verified locally under `installer/dist/`.
Windows `.exe` and macOS `.dmg` artifacts are not published yet; they require
their native build hosts and validation. Until then, use the source
installation or point the desktop client at a remote BIMOS API.

## From Source

```bash
git clone https://github.com/RenatoJVA/BIMOS.git
cd BIMOS/backend
pip install -e .

# (Optional) Build the frontend assets
cd ../frontend && bun install && bun run build
```

## Development Install

```bash
cd BIMOS/backend
pip install -e ".[dev]"
```

## Container Image

The scientific engines (AutoDock Vina, GROMACS, Boltz, Meeko, RDKit) run
inside a container image that BIMOS builds locally on first use:

```bash
bimos setup
```

`setup` builds the image from `backend/dockers/` and caches it. From then on,
pipelines invoke it automatically — no `docker pull` is required. See
[NOTICE.md](https://github.com/RenatoJVA/BIMOS/blob/main/NOTICE.md) for the
third-party components included in the image.

## API Server / Desktop UI

```bash
bimos -g                     # desktop UI (pywebview) + API
bimos -g --headless          # API only, no webview (servers, containers)
bimos -g --headless --port 9000
```

The API is served at `http://127.0.0.1:8000` by default (`--host` to change
the interface). To point the desktop UI at a remote BIMOS server, use
`bimos -g --remote https://bimos.example.org`.

## Docker Compose (optional)

A reference stack is provided in the repository root — API plus PostgreSQL:

```bash
docker compose up -d
# API available at http://localhost:8000
```

## Requirements

- Python 3.12+
- Podman or Docker (for containerized compute tools)
- Linux, macOS, or Windows
- An NVIDIA GPU with a working container runtime for Boltz predictions
  (see [README requirements](https://github.com/RenatoJVA/BIMOS#requirements))
- A licensed ORCA or Gaussian 16 installation for the `qm-orca` / `qm-g16`
  commands — neither is distributed with BIMOS (see [TERMS.md](https://github.com/RenatoJVA/BIMOS/blob/main/TERMS.md))
