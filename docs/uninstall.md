# Uninstall and full purge

BIMOS is licensed for institutional use with a **no-residue** requirement: a
normal uninstall must remove everything the software owns. This page documents
what that means, how to do it on each platform, and how to prove that nothing
was left behind.

## What BIMOS writes

| Item | macOS | Linux | Windows |
|---|---|---|---|
| Application | `BIMOS.app` (wherever it was unpacked, usually `/Applications`) | `/opt/bimos`, `/usr/bin/bimos`, desktop entry | `%LOCALAPPDATA%\Programs\BIMOS` (NSIS `$INSTDIR`) |
| Configuration, workspace, cache, logs | `~/.bimos` | `~/.bimos` | `%USERPROFILE%\.bimos` |
| Web UI state | `~/Library/WebKit/org.bimos.app` and related caches | `~/.bimos/cache/webview` (Qt) | `~/.bimos/cache/webview` (WebView2) |
| Container image | rootless Podman/Docker store | rootless Podman/Docker store | Podman/Docker store |
| PATH / shortcuts / services | none | desktop entry (package) | PATH entry, Start Menu shortcuts |

`~/.bimos` is the single data root. It can be relocated with
`BIMOS_BASE_PATH`; the app records the effective workspace/cache/log paths in
`~/.bimos/paths.json` so the uninstaller can find them even when they point
elsewhere.

## macOS

The macOS distribution is a portable bundle, not an installer:

```text
BIMOS-0.1.0-macos-arm64.tar.gz
├── BIMOS.app
├── Uninstall BIMOS.command
└── LEEME.txt
```

### Recommended: double-click the helper

`Uninstall BIMOS.command` is standalone: it works even when `BIMOS.app` is
damaged or cannot start.

1. Quit BIMOS.
2. Double-click **Uninstall BIMOS.command**.
3. Read the result: `PASS` means no BIMOS-owned residue remains.

The helper runs unattended.

The helper asks the app's own purger first (`bimos uninstall`), then falls
back to its embedded manifest. It removes the app bundle, `~/.bimos`, the
WebKit/HTTP state, preferences, saved window state and the BIMOS container
image if it exists.

Preview without deleting:

```bash
./Uninstall\ BIMOS.command --dry-run
```

### Terminal alternative

```bash
# from the unpacked folder
./BIMOS.app/Contents/MacOS/bimos.bin uninstall --dry-run
./BIMOS.app/Contents/MacOS/bimos.bin uninstall --yes
./BIMOS.app/Contents/MacOS/bimos.bin uninstall --verify
```

Add `--remove-app` to delete `BIMOS.app` from the CLI as well. The helper does
that automatically.

## Linux

With the `.deb` package:

```bash
sudo apt remove bimos     # keeps ~/.bimos
sudo apt purge bimos      # also purges the installing user's data
```

`apt purge` removes `/opt/bimos`, the wrapper, desktop entry, icon and docs,
plus `~/.bimos`, the Qt configuration (`~/.config/BIMOS.conf`) and QtWebEngine
state for `$SUDO_USER`. The container image is removed from that user's
rootless store.

Per-user purge (recommended before removing the package, and the only option on
multi-user machines):

```bash
bimos uninstall --yes            # data + image, keeps /opt/bimos
bimos uninstall --yes --verify   # prove it is gone (exit 3 if not)
```

Because `postrm` runs as root and the package files are already gone at that
point, it cannot call the CLI. It removes the same paths directly. On
multi-user hosts each user must run `bimos uninstall` themselves; `apt purge`
can only clean the account that invoked it.

## Windows

Use **Settings → Apps → BIMOS → Uninstall**, or the Start Menu uninstaller.
The installer records the installing user's profile in the registry, so the
uninstaller (which runs elevated) purges the correct account:

- `$INSTDIR` (application tree), shortcuts, PATH entry and registry key.
- `%USERPROFILE%\.bimos`.
- WebView2/pywebview state.

On multi-user machines, each additional user must run:

```powershell
%LOCALAPPDATA%\Programs\BIMOS\bimos.exe uninstall --yes
```

## CLI reference

```text
bimos uninstall [--dry-run] [--yes] [--keep-data] [--deep]
                [--remove-app] [--include-outputs] [--verify]
                [--print-manifest] [--force-path] [--base-path PATH] [--json]
```

| Flag | Effect |
|---|---|
| *(none)* | Removes data, web state and image; asks to type `PURGE` |
| `--dry-run` | Lists what would be removed; deletes nothing |
| `--yes` | No confirmation (required in scripts) |
| `--keep-data` | Keeps `~/.bimos` and custom workspace/cache/log paths |
| `--deep` | Also prunes the container engine's **global** build cache |
| `--remove-app` | Also deletes the application bundle/CLI install |
| `--include-outputs` | Also deletes job outputs recorded outside `~/.bimos` |
| `--verify` | Only verifies; exit `3` when residues remain |
| `--print-manifest` | Prints the static manifest as JSON |
| `--force-path` | Allows a custom `BIMOS_BASE_PATH` without BIMOS markers |
| `--json` | Machine-readable report (useful as a deletion certificate) |

Exit codes: `0` success/nothing to remove, `1` error, `2` aborted by a safety
guard or missing confirmation, `3` residues remain.

The purger never writes logs inside `~/.bimos` (they would recreate the
directory it is deleting). Output goes to stdout/stderr only.

### Proof of deletion

```bash
# Keep the bundle until verification is done: the CLI lives inside it.
bimos uninstall --yes --deep
bimos uninstall --verify --json
echo $?    # 0 = clean, 3 = residues

# Then remove the app (the macOS helper does both and verifies afterwards).
bimos uninstall --yes --remove-app
```

Attach `uninstall-report.json` to the institutional evidence package.

## Safety guards

- Only internally generated paths are deleted; the CLI never accepts a
  free-form path.
- `/`, the home directory, its parent and platform top-level directories
  (`/Applications`, `/usr`, `/opt`, `/System`, …) are rejected.
- Symbolic links are unlinked; their targets are never touched.
- A custom `BIMOS_BASE_PATH` must look like a BIMOS directory (`.env` with
  `BIMOS_` keys, `config/*.yaml` or `paths.json`) unless `--force-path` is
  used.
- Container commands use argv arrays (no shell) and never run a blanket
  `system prune`.
- The Podman machine is only removed with the hidden `--remove-machine` flag
  **and** a typed confirmation. It is shared infrastructure, not BIMOS data.

## What is deliberately out of scope

No uninstaller can erase OS-owned history; these are documented as outside the
application purge:

- Time Machine backups and APFS snapshots.
- The macOS unified log, Spotlight/LaunchServices indexes and crash reports.
- Shell history (commands the user ran).
- Files the user saved outside BIMOS paths (for example with `--output`).
  `--include-outputs` covers only outputs the job store recorded.
- Safari/Chrome data if the web UI was opened in a normal browser.
- ORCA/Gaussian installations owned by the user; BIMOS never distributes them.
- The downloaded `.tar.gz`/`.deb`/`.exe` and the unpacked distribution folder.
- iCloud/Dropbox/institutional backups.

The defensible statement for an auditor is:

> BIMOS leaves **no application-owned residue**: app, configuration, data,
> web state, container image and caches under its control are removed and the
> result is verifiable. OS-managed artifacts and user-created files outside
> BIMOS paths are explicitly out of scope.
