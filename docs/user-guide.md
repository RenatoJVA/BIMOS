# User guide

This page is for everyday use: installing BIMOS, running a job, finding your
results and fixing the usual problems. If you are building the application
from source, read [Installation](installation.md) and the platform build
guides instead.

BIMOS is a desktop application (GUI + local API + CLI) for molecular modelling.
It does **not** need Python, CUDA or any command line to run a job: you open a
window, drop your files, pick a method and press run.

## 1. Install it

| Platform | What you download | How it installs |
|---|---|---|
| Linux (Ubuntu 24.04) | `bimos_<version>_amd64.deb` | Double-click, or `sudo apt install ./bimos_<version>_amd64.deb` |
| Windows 10/11 | `BIMOS-<version>-Setup.exe` | Run it; choose the install folder. No admin rights needed for the user data |
| macOS (Apple Silicon) | `BIMOS-<version>-macos-arm64.tar.gz` | Unpack and drag `BIMOS.app` to `/Applications` |

There is no account, no license key and no telemetry. Everything BIMOS writes
goes to your user folder (see [section 4](#4-where-your-files-live)).

!!! note "macOS"
    Unpack with `tar --xattrs -xzf BIMOS-<version>-macos-arm64.tar.gz` (or
    Finder's Archive Utility). `--xattrs` keeps the code signatures intact.
    Right-click the app → **Open** → **Open** the first time: the build is
    ad-hoc signed, not notarized, so Gatekeeper asks.

## 2. First launch

1. Open **BIMOS** from your applications menu.
2. A window appears with the launcher. In parallel, BIMOS starts a local API on
   `http://127.0.0.1:8000`.
3. On the very first start it creates `~/.bimos` with the configuration,
   workspace, cache and logs. Nothing else is written elsewhere.

Quick check that the backend is alive (optional):

```bash
curl http://127.0.0.1:8000/api/v1/health
# {"status":"ok", ...}
```

Closing the window stops the API. There is no background service, no daemon
and no autostart entry.

## 3. Run a job

Every job follows the same four steps.

1. **Choose the tool** in the launcher: Boltz-2 (structure prediction),
   AutoDock Vina (docking), GROMACS (molecular dynamics) or ORCA (quantum
   chemistry).
2. **Drop the input files.** The drop zone tells you what it expects:

   | Tool | Input |
   |---|---|
   | Boltz-2 | Protein sequence (`FASTA`) |
   | Docking | Receptor structure (`PDB`) + ligands (`SDF`) |
   | Molecular dynamics | Structure (`PDB`/`GRO`) plus ligand `GRO`/`ITP` when the mode needs it |
   | ORCA | Structure (`PDB`) and the run parameters |

3. **Set the parameters.** Every field has a default taken from
   `~/.bimos/config/`; change only what your experiment needs.
4. **Run.** The job appears in the job grid. Click it to follow the log live.

Results are written to the workspace when the job finishes. A failed job keeps
its log so you can see why it stopped; the most common cause is a missing GPU
or a container runtime that is not running (see [section 6](#6-troubleshooting)).

## 4. Where your files live

Everything is under one folder: `~/.bimos` (`%USERPROFILE%\.bimos` on Windows).

| Folder | What it holds |
|---|---|
| `workspace/` | **Your results.** Keep this if you reinstall |
| `cache/` | Regenerable intermediate files; safe to delete |
| `logs/` | Application logs |
| `config/` | YAML parameter defaults for each tool |
| `.env` | Settings such as the server port or a remote GPU host |

BIMOS records the real paths in `~/.bimos/paths.json`. If you move the data
with `BIMOS_BASE_PATH`, that file keeps the app and the uninstaller pointing at
the right place.

Never delete the folder by hand while a job is running. Use the uninstaller
when you want to remove everything (see [Uninstall](uninstall.md)).

## 5. Working with a Linux GPU server

Boltz-2 and long GPU runs need an NVIDIA GPU. Linux with a GPU is the
recommended setup; Windows and macOS can drive the interface but are limited
locally.

If the heavy compute lives on another machine, put its API address in
`~/.bimos/.env` and restart the app:

```ini
# http://<host>:8000
BIMOS_REMOTE_URL=http://192.168.1.50:8000
```

- The remote host must run the same BIMOS version with the API listening
  outside loopback, and every machine that connects must know the
  `BIMOS_API_TOKEN` if the server sets one.
- With a remote URL, jobs are queued on that server. Your local window becomes
  a client; nothing scientific runs on your laptop.
- Leave the line commented out (`# BIMOS_REMOTE_URL=`) for local-only use.

What each platform can do locally:

| Platform | GUI/API/CLI | Local compute | Boltz |
|---|---|---|---|
| Linux + NVIDIA | Yes | Vina, GROMACS, QM, Boltz | GPU |
| Linux without GPU | Yes | Vina, GROMACS; QM with ORCA/G16 | No |
| Windows 10/11 | Yes | Vina and GROMACS in containers | Only if the container runtime exposes a GPU |
| macOS (Apple Silicon) | Yes | Not local | No |

On macOS the bundle ships no CUDA and `bimos setup` will not build the
scientific image; use `bimos setup --config-only` and a remote Linux host.
Details in [ADR 0001](adr/0001-macos-portable-bundle.md).

## 6. Troubleshooting

| Symptom | What to do |
|---|---|
| macOS: "BIMOS cannot be opened because the developer cannot be verified" | Right-click the app → **Open** → **Open**, or `xattr -dr com.apple.quarantine /Applications/BIMOS.app` |
| White window / interface never loads | Check the port: another program may be using 8000. Change `BIMOS_PORT` in `~/.bimos/.env` and restart |
| `Address already in use` in the log | Same as above: stop whatever holds port 8000, or set another port |
| Job fails immediately | Check the job log. Usually the container runtime is not running (`docker ps`) or the job needs a GPU |
| Boltz aborts: no GPU | Predictions need NVIDIA + container GPU passthrough. Run them on the Linux GPU host |
| Docker/Podman permission denied (Linux) | `sudo usermod -aG docker $USER`, then log out and back in |
| The app cannot reach the API | If `BIMOS_REMOTE_URL` is set, the remote host may be down; comment it out for local mode |
| Everything looks broken, data seems lost | Your results are in `~/.bimos/workspace`. Back that folder up before reinstalling |
| I need a clean slate | Uninstall with the platform helper; it removes app, `~/.bimos`, web state and the image. See [Uninstall](uninstall.md) |

## 7. Update and uninstall

**Update:** install the new package over the old one. Configuration in
`~/.bimos/config/` is kept; `.env` and the workspace are never overwritten.

**Uninstall:** use the platform helper so no residue remains:

- macOS: double-click **Uninstall BIMOS.command** next to the app.
- Linux: `sudo apt remove bimos` (keeps your data) or `sudo apt purge bimos`
  (also purges it).
- Windows: Settings → Apps → BIMOS → Uninstall.

Add `--dry-run` (macOS helper or CLI) to preview what would be removed.
The full contract, guards and proof of deletion are in
[Uninstall and full purge](uninstall.md).

## 8. Getting help

- Full parameter reference: [CLI](cli.md) and [API](api/public.md).
- Building from source or packaging: [Installation](installation.md),
  [macOS build](build-macos.md).
- Legal and privacy: `TERMS.md`, `PRIVACY.md` and `NOTICE.md` in the
  repository.
