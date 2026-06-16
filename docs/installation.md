# Installation

## From PyPI

```bash
pip install bimos
```

## From Source

```bash
git clone https://github.com/ucsm/bimos.git
cd bimos/backend
pip install -e .
```

## Development Install

```bash
pip install -e ".[dev]"
```

## Container Image

```bash
docker pull ghcr.io/ucsm/bimos:latest

# Run CLI commands
docker run --rm ghcr.io/ucsm/bimos predict --help

# Start API server
docker run --rm -p 8000:8000 ghcr.io/ucsm/bimos serve
```

## Docker Compose

```bash
docker compose up -d
# API available at http://localhost:8000
```

## Requirements

- Python 3.12+
- Podman or Docker (for containerized compute tools)
- Linux, macOS, or Windows
