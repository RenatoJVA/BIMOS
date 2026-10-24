# Installation

## Pre-built Installers

The Linux `.deb` is built and verified locally under `installer/dist/`.
Windows `.exe` is not published yet; it requires its native build host and
validation. The macOS artifact is a portable bundle built on Apple Silicon
(`installer/dist/BIMOS-<version>-macos-arm64.tar.gz`).

### macOS (Apple Silicon)

Unpack the archive and run `BIMOS.app` in place, or drag it to
`/Applications`. There is no installer and no administrator password; data
lives in `~/.bimos`, never inside the app bundle.

```bash
tar --xattrs -xzf BIMOS-0.1.0-macos-arm64.tar.gz
open BIMOS.app
```

Use `tar --xattrs` (also works in Finder's Archive Utility): the archive keeps
Nuitka's detached signatures, which `codesign --verify --deep --strict`
expects.

The package uses an ad-hoc signature (not notarized). On first launch macOS
may block it: right-click the app → **Open** → **Open**, or run:

```bash
xattr -dr com.apple.quarantine /Applications/BIMOS.app
```

macOS is a UI/API client: it does not ship CUDA and `bimos setup` will not
build the scientific image (use `bimos setup --config-only`, or point the app
at a Linux GPU server with `BIMOS_REMOTE_URL`). See
[Uninstall](uninstall.md) for the standalone purge helper and
[ADR 0001](adr/0001-macos-portable-bundle.md) for the support scope.

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

On macOS there is no NVIDIA/CUDA: the app works as a UI/API client and the
scientific image is not built locally. See
[Uninstall](uninstall.md) for the complete purge procedure.
