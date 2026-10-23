# Deployment

This guide covers the supported ways to run BIMOS after installation. The
short version: compute pipelines belong on a machine with Podman/Docker (and a
GPU for Boltz), while the API/UI can run either next to them or in a small
API-only container.

## Execution model

| Component | Runs on | Notes |
|---|---|---|
| CLI, GUI, FastAPI | Host (native) | Installed from `.deb`, `.exe`, `.dmg` or `pip install` |
| Boltz, Vina, GROMACS, Meeko | Podman/Docker container | Image `localhost/bimos/global:latest`, built by `bimos setup` |
| ORCA / Gaussian 16 | Host | User-provided license; never distributed with BIMOS |
| PostgreSQL | Optional | Only used by the reference Compose stack |

`BIMOS_EXECUTION_MODE=local` (default) launches jobs on the host.
`BIMOS_EXECUTION_MODE=disabled` serves the API/UI but rejects job submission
with HTTP 503 — this is the mode used for the API-only Compose deployment.

## Native host deployment

1. Install BIMOS and a container runtime (Podman recommended).
2. Run the first-time setup:

   ```bash
   bimos setup
   ```

   This creates `~/.bimos/.env` plus the per-process YAML files under
   `~/.bimos/config/` and builds the scientific image. Runtime data lives in
   `~/.bimos/workspace`, `~/.bimos/cache` and `~/.bimos/logs`.

3. Edit `~/.bimos/.env` only if you need to change paths, the image tag or
   resource defaults. `bimos setup --config-only` refreshes the YAML files
   without rebuilding the image.

4. For GPU predictions, verify the driver and container GPU passthrough:

   ```bash
   nvidia-smi
   podman run --rm --device nvidia.com/gpu=all localhost/bimos/global:latest nvidia-smi
   ```

   Boltz refuses to fall back to CPU: the job fails fast when the GPU is not
   visible inside the container.

## API server and desktop UI

```bash
bimos -g                  # desktop UI (pywebview) + local API
bimos -g --headless       # API + dashboard only, no webview
bimos -g --headless --host 0.0.0.0 --port 8000
```

Loopback binds (`127.0.0.1`, `localhost`, `::1`) do not need a token. Any
non-loopback bind requires a strong `BIMOS_API_TOKEN`, otherwise startup fails
closed:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
BIMOS_API_TOKEN=<token> bimos -g --headless --host 0.0.0.0
```

The built dashboard is same-origin: it calls `/api/v1` on whatever host serves
it. For frontend development against a separate API, set `VITE_API_BASE` before
`bun run dev` (defaults to `http://localhost:8000/api/v1`).

## Reference Docker Compose stack

The root `docker-compose.yml` runs the API/UI plus PostgreSQL. It does **not**
mount `docker.sock` and cannot execute pipelines; scientific jobs stay on the
compute host.

```bash
export BIMOS_API_TOKEN=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
export BIMOS_DB_PASSWORD=$(python -c "import secrets; print(secrets.token_urlsafe(24))")
docker compose up -d
docker compose ps          # bimos-api healthy, bimos-db healthy
```

Both services bind to loopback only. For remote access you can enable native
TLS in BIMOS or terminate TLS in a reverse proxy:

- Native TLS: set `BIMOS_TLS_CERTFILE` and `BIMOS_TLS_KEYFILE` to the PEM
  certificate and key. Both files are required together, and the desktop UI
  switches to `https://` automatically.
- Proxy TLS: terminate TLS at Caddy/nginx/Traefik and forward to
  `127.0.0.1:8000`; leave both TLS variables empty.
- Always send `Authorization: Bearer <BIMOS_API_TOKEN>` from API clients; the
  dashboard itself relies on TLS or an SSH tunnel for transport security.
- Do not expose PostgreSQL (`127.0.0.1:5432`) to the network.

Native TLS example:

```bash
export BIMOS_TLS_CERTFILE=/etc/bimos/tls/server.crt
export BIMOS_TLS_KEYFILE=/etc/bimos/tls/server.key
bimos -g --headless --host 0.0.0.0 --port 8443
curl --cacert /etc/bimos/tls/ca.crt \
  -H "Authorization: Bearer $BIMOS_API_TOKEN" \
  https://127.0.0.1:8443/api/v1/health
```

For interactive use over an untrusted network, an SSH tunnel is the simplest
option:

```bash
ssh -L 8000:127.0.0.1:8000 user@compute-host
bimos -g --remote http://127.0.0.1:8000
```

## Building releases

The version is defined once in `backend/pyproject.toml`; the API, CLI and
frontend read it from there.

```bash
cd backend
pixi run python ../builder.py            # frontend + Nuitka + installer
pixi run python ../builder.py --skip-nuitka
pixi run python ../builder.py --verify   # audit existing artifacts only
```

CI/CD is prepared but intentionally **not activated**: the workflow only runs
via `workflow_dispatch` because hosted-runner minutes are budget-limited. Do not
activate or run it until the release gate is approved:

- Feature freeze at roughly 95% of the release scope.
- Version and tag agreed; the tag must be exactly `v` + the
  `pyproject.toml` version (for example `v0.1.0`).
- Local gates green: lint, test suite, frontend build, full integration run,
  `builder.py`/`--verify`, and the API image smoke test.

Then run **one** Linux build, download the artifact and repeat `--verify` on the
downloaded `.deb`. Windows/macOS builds remain out of scope until `R-ROAD-01`
is explicitly approved.

`builder.py --verify` checks the binary smoke test (`bimos --version`), stripped
debug symbols, the bundled NSS chain and the `.deb` payload (binary, wrapper,
desktop entry, docs and the Dockerfile under `/opt/bimos/lib/dockers`).

## Upgrade and rollback

- Keep `~/.bimos/config/*.yaml`: user edits are preserved across upgrades and
  deep-merged over new packaged defaults.
- Replace the binary/package for upgrades; roll back by reinstalling the
  previous release artifact.
- The scientific image is versioned by tag (`BIMOS_IMAGE`); rebuild with
  `bimos setup --force` after changing pins in the Dockerfile.

## Deployment checklist

- [ ] Container runtime installed and healthy (`podman info` / `docker info`).
- [ ] `bimos setup` completed and the image runs (`podman images`).
- [ ] GPU visible inside the container for Boltz (`nvidia-smi`).
- [ ] `~/.bimos/.env` reviewed (paths, image tag, `BIMOS_USE_GPU`).
- [ ] Non-loopback API binds protected by `BIMOS_API_TOKEN` and TLS.
- [ ] ORCA/Gaussian paths (`ORCA_PATH`, `GAUSSIAN_PATH`) set only on hosts with
      valid licenses.
- [ ] Backups of `~/.bimos/workspace` if job outputs matter.
