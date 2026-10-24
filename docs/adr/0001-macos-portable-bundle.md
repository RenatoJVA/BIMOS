# ADR 0001 — macOS support scope and portable bundle

- **Status:** Accepted
- **Date:** 2026-10-24
- **Context:** Hito 1 (E1 executable, R1 interface), institutional licenses with
  a no-residue requirement.

## Context

BIMOS is developed on Linux, where the scientific stack (AutoDock Vina,
GROMACS, Boltz-2, RDKit) runs in a CUDA container image. The Hito 1 contract
requires executables for Linux, Windows and macOS. The available macOS machine
is an Apple Silicon laptop with no NVIDIA GPU and no Apple Developer ID.

The project also needs a defensible answer to “how do we uninstall this
completely?”, including configuration, web state and container artifacts.

## Decision

1. **macOS is a compliance port, not a compute platform.** It delivers the
   desktop UI/API/CLI against the same backend. Scientific jobs remain
   validated on Linux + NVIDIA; macOS may connect to a Linux GPU server with
   `BIMOS_REMOTE_URL`.
2. **Artifact: portable bundle, not an installer.** Ship
   `BIMOS-<version>-macos-arm64.tar.gz` containing `BIMOS.app`,
   `Uninstall BIMOS.command` and `LEEME.txt`. There is no DMG or `.pkg`: the
   user unpacks and runs the app (Vina/Gaussian-style), and nothing is written
   outside the user's home.
3. **GUI stack:** `pywebview` with the native Cocoa backend (PyObjC). Qt,
   PyQt6 and QtWebEngine are Linux-only and must not enter the macOS bundle.
4. **Build toolchain:** `uv` (Python 3.12) + Xcode/Apple clang, documented in
   `docs/build-macos.md`. The canonical Linux build keeps `pixi`; no
   `pixi_mac.toml` and no `osx-arm64` platform are added now.
5. **No scientific image on macOS.** `bimos setup` refuses to build the CUDA
   image on Darwin unless `--force` is passed; `--config-only` still works.
6. **Signing:** ad-hoc (`codesign --sign -`), inside-out. Gatekeeper will warn
   on other Macs; notarization is a separate decision that requires an Apple
   Developer Program membership and is only needed for external evaluators.
7. **Purge is part of the product.** `bimos uninstall` and the standalone
   helper remove the app, `~/.bimos`, web state, preferences and the container
   image, with `--dry-run`, `--verify` and a JSON deletion report. “No
   residue” means no *application-owned* residue; OS-managed backups, logs and
   indexes are documented as out of scope.
8. **CI/CD is the last roadmap step.** The macOS build is validated locally
   first; CI jobs are designed but not enabled in this change.

## Consequences

- The macOS build is reproducible through a runbook plus recorded tool
  versions, not through a lockfile-only environment.
- Users get a native `.app` with a bundle identifier (needed by WKWebView)
  without an installation step or administrator rights.
- Unpacking preserves the ad-hoc signature and the helper's executable bit.
- macOS evidence covers R1 (UI) and E1 (executable). It does **not** claim
  Boltz/docking/MD parity; that evidence stays on Linux/GPU and Windows.
- If macOS ever becomes a supported compute platform, the project should move
  it into the hermetic pixi environment and add signing/notarization plus CI.
- External distribution to non-technical evaluators will require Developer ID
  signing and notarization; that is an explicit future decision.

## Exit criteria

- `installer/dist/BIMOS-<version>-macos-arm64.tar.gz` exists and verifies
  (`codesign`, `lipo`, `otool`, size, hash).
- The UI checklist for R1 passes on macOS.
- `bimos uninstall --verify` returns 0 and the helper reports `PASS`.
- Windows and FMP008 remain tracked as pending; E1 is not declared complete.
