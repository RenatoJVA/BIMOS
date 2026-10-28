# Building the macOS portable bundle

macOS runs the GUI/API/CLI natively, but scientific compute is delegated to a
Linux GPU host: the bundle ships no CUDA stack and `bimos setup` does not build
the scientific image locally. This is a hardware limitation, not a UI-only
scope. The canonical build environment for Linux stays `pixi`; macOS uses
`uv` + Xcode. See [ADR 0001](adr/0001-macos-portable-bundle.md) for the
rationale.

## Prerequisites

- Apple Silicon Mac (arm64). The bundle is not universal2.
- Xcode command line tools (Apple clang, `codesign`, `iconutil`):

  ```bash
  xcode-select --install
  xcodebuild -version
  clang --version
  ```

- [`uv`](https://docs.astral.sh/uv/) for the isolated Python 3.12 environment.
- [`bun`](https://bun.sh) for the frontend build.
- `ccache` is optional; Nuitka auto-detects it.

No `create-dmg`, no DMG, no installer, no administrator rights.

## 1. Environment

```bash
cd BIMOS
uv venv --python 3.12
source .venv/bin/activate
uv pip install -e "backend[build,db,monitoring]" pywebview pytest ruff mypy
```

Do **not** install `backend[gui]` on macOS: that extra is for Linux (Qt). The
macOS GUI is Cocoa through `pywebview`/PyObjC.

Smoke check:

```bash
python -c "import webview, objc, Foundation, AppKit, WebKit; print('cocoa ok')"
python -m nuitka --version
```

## 2. Icon and frontend

```bash
iconutil -c icns installer/assets/bimos.iconset -o installer/assets/bimos.icns

cd backend
python build.py --skip-nuitka      # bun install + build + sync into bimos/ui
```

`backend/bimos/ui/index.html` is tracked in git although the build overwrites
it. After producing the artifact, restore it:

```bash
git checkout -- backend/bimos/ui
rm -rf backend/bimos/ui/assets
```

The application already contains its own copy of the UI inside the bundle.

## 3. Compile

```bash
cd backend
python build.py --skip-frontend 2>&1 | tee ../test/logs/macos_build.log
```

`backend/build.py` uses, on macOS:

- `--disable-plugin=pywebview` and explicit `--include-module=webview` /
  `webview.platforms.cocoa` (the plugin conflicts with explicit includes).
- `--macos-create-app-bundle --macos-app-name=BIMOS --macos-app-mode=gui`.
  Nuitka requires an app bundle for PyObjC in standalone mode; it also gives
  WKWebView a stable application identity.
- No Qt flags. PyQt6/QtWebEngine must never appear in the macOS bundle.

Smoke test the compiled payload **before** packaging:

```bash
./dist/main.app/Contents/MacOS/bimos.bin --version
./dist/main.app/Contents/MacOS/bimos.bin    # no args on darwin starts the GUI
```

`backend/main.py` injects `-g` when a frozen macOS binary is launched with no
arguments, so double-clicking works even without a wrapper.

## 4. Package

```bash
cd ..
python builder.py --target macos 2>&1 | tee test/logs/macos_package.log
```

This runs `installer/build_macos_bundle.sh`, which:

1. Uses Nuitka's own `main.app` (PyObjC requires an app bundle). Nuitka keeps
   the executable and its libraries in `Contents/MacOS`; `main.py` injects
   `-g` when the frozen binary gets no CLI arguments.
2. Falls back to `main.dist` + the compiled `macos_launcher.c` only if Nuitka
   emitted a plain standalone tree.
3. Writes `Info.plist` (`org.bimos.app`, `NSAllowsLocalNetworking`, minimum
   macOS 12, icon).
4. Ships legal documents and `Uninstall BIMOS.command`.
5. Signs ad-hoc. For the Nuitka bundle only the re-sealed bundle is signed;
   `xattr -cr` is deliberately **not** run because Nuitka stores detached
   signatures for payload files in extended attributes.
6. Creates `installer/dist/BIMOS-<version>-macos-arm64.tar.gz` with
   `BIMOS.app`, `Uninstall BIMOS.command` and `LEEME.txt` using
   `COPYFILE_DISABLE=1 tar --xattrs` (the xattrs carry those signatures).

## 5. Verify

```bash
python builder.py --target macos --verify
```

The verifier extracts the archive and checks:

- `BIMOS.app/Contents/MacOS/BIMOS`, `Info.plist`, icon, helper and `LEEME.txt`.
- Helper executable bit.
- `CFBundleIdentifier=org.bimos.app` and `NSAllowsLocalNetworking`.
- `codesign --verify --deep --strict`.
- `lipo -archs` = `arm64`.
- `otool -L` has no `/opt/homebrew`, `/usr/local` or `/Users/...` paths.
- Archive ≤ 200 MB and its SHA256, also written to `SHA256SUMS`.

Manual audit:

```bash
du -sh installer/staging/BIMOS.app installer/dist/*.tar.gz
find installer/staging/BIMOS.app \( -iname '*qt*' -o -iname '*torch*' -o -iname '*cuda*' \)
lipo -archs installer/staging/BIMOS.app/Contents/MacOS/bimos.bin
```

## 6. First-run validation

```bash
mkdir -p /tmp/bimos-test && cd /tmp/bimos-test
tar --xattrs -xzf /path/to/BIMOS-0.1.0-macos-arm64.tar.gz
open BIMOS.app
```

`tar --xattrs` keeps Nuitka's detached signatures for payload data files, so
`codesign --verify --deep --strict` also passes after extraction. Finder's
Archive Utility preserves them too.

- The UI opens (Cocoa, no white screen).
- `curl -fsS http://127.0.0.1:8000/api/v1/health` → `{"status":"ok"}`.
- Load `test/PREDICT/lysozyme.fasta` and `test/APO/1AKI.pdb`.
- Set time/topology and select GROMACS and ORCA.
- Closing the window stops the process and frees port 8000.
- `~/.bimos` exists and contains `.env`, `config/`, `workspace/`, `cache/`,
  `logs/` and `paths.json`.

If Gatekeeper blocks the app, right-click → **Open** → **Open**, or:

```bash
xattr -dr com.apple.quarantine /Applications/BIMOS.app
```

## 7. Uninstall validation

```bash
./BIMOS.app/Contents/MacOS/bimos.bin uninstall --dry-run
./BIMOS.app/Contents/MacOS/bimos.bin uninstall --yes
./BIMOS.app/Contents/MacOS/bimos.bin uninstall --verify   # exit 0

# The CLI lives inside the app, so remove the bundle last (the helper does
# this and verifies afterwards):
./Uninstall\ BIMOS.command
```

Then reinstall, open/close the app and run `Uninstall BIMOS.command`: it must
end in `PASS`. Full procedure and scope: [Uninstall](uninstall.md).

## 8. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `Conflict between user and plugin decision for module 'webview.platforms.*'` | The pywebview plugin is enabled together with explicit includes. Keep `--disable-plugin=pywebview`. |
| `package 'Foundation' requires '--mode=app'` | PyObjC needs an app bundle. Keep `--macos-create-app-bundle`. |
| `codesign` fails on the launcher | Use the compiled `macos_launcher.c`; a shell script is not a signable main executable. |
| `webview.start()` returns immediately / no window | On Cocoa, pywebview 6.2 returns immediately when `private_mode`/`storage_path` are passed. Pass them only on Linux/Windows. |
| `codesign --verify --deep --strict` fails after extraction | The archive was created without `--xattrs`, stripping Nuitka's detached signatures for data files. Use `tar --xattrs` (build and extract). |
| `create-dmg` not found | Not needed anymore. The artifact is a `.tar.gz`. |
| Gatekeeper blocks on another Mac | Ad-hoc signature, not notarized. Developer ID + notarization is a separate decision. |
| Port 8000 already in use | `lsof -nP -iTCP:8000 -sTCP:LISTEN`; close the stale BIMOS process. |
| `bimos setup` refuses to build | Expected on macOS (no CUDA). Use `--config-only` or `BIMOS_REMOTE_URL`. |

## 9. Cleanup of the build machine

```bash
deactivate
rm -rf .venv backend/dist installer/staging installer/dist
git checkout -- backend/bimos/ui
rm -rf backend/bimos/ui/assets
rm -f installer/assets/bimos.icns
```

Never commit build artifacts, `.venv`, `node_modules`, the icon, the app or
the archive. `git status` must stay clean.
