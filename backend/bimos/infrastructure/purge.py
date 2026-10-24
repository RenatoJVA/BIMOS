"""Residue-free uninstall / purge for BIMOS.

Single source of truth for every platform: the ``bimos uninstall`` CLI, the
macOS ``Uninstall BIMOS.command`` helper, the Linux ``postrm`` hook and the
Windows NSIS uninstaller all describe the same locations.

Design rules (never relaxed):

* Only exact, internally generated paths are removed; the CLI never accepts a
  free-form path to delete.
* ``/``, the home directory, its parent, and the platform's top-level
  directories are rejected even if a bug produced them.
* Symlinks are unlinked, never followed.
* A custom ``BIMOS_BASE_PATH`` must look like a BIMOS directory (``.env`` with
  ``BIMOS_`` keys, ``config/*.yaml`` or ``paths.json``) unless ``--force-path``
  is passed.
* Container commands are argv-only (no shell) and never prune the user's whole
  engine by default.
* Removing something that is already gone is a skip, not an error (idempotent).

This module deliberately imports only the standard library so it also works
inside a damaged installation and from the standalone shell helper.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

BUNDLE_ID = "org.bimos.app"
DEFAULT_IMAGE = "localhost/bimos/global:latest"

Kind = Literal["file", "dir", "containers"]
Owner = Literal["user", "system"]


class PurgeError(RuntimeError):
    """Base class for purge failures reported to the user."""


class UnsafePathError(PurgeError):
    """A path failed the safety guards; nothing was deleted for it."""


class ConfirmationError(PurgeError):
    """Destructive option was requested without explicit confirmation."""


@dataclass(frozen=True)
class Residue:
    """One thing BIMOS owns that a purge may remove."""

    kind: Kind
    description: str
    path: Path | None = None
    image: str | None = None
    owner: Owner = "user"
    optional: bool = True

    def exists(self) -> bool:
        if self.kind == "containers":
            runtime = container_runtime()
            if runtime is None or not self.image:
                return False
            if _run([runtime, "image", "exists", self.image]).returncode == 0:
                return True
            return bool(_containers_for(self.image))
        if self.path is None:
            return False
        return self.path.exists() or self.path.is_symlink()

    def label(self) -> str:
        if self.kind == "containers":
            return f"containers/image {self.image}"
        return str(self.path)


@dataclass
class PurgeReport:
    """Outcome of a purge or verification run."""

    removed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    remaining: list[str] = field(default_factory=list)
    dry_run: bool = False

    def ok(self) -> bool:
        return not self.errors and not self.remaining

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok(),
            "dry_run": self.dry_run,
            "removed": self.removed,
            "skipped": self.skipped,
            "errors": self.errors,
            "remaining": self.remaining,
        }


# ── Safety guards ────────────────────────────────────────────────────────────


def _forbidden_paths() -> set[Path]:
    home = Path.home()
    candidates = {
        Path("/"),
        home,
        home.parent,
        Path("/Applications"),
        Path("/System"),
        Path("/Library"),
        Path("/Users"),
        Path("/usr"),
        Path("/etc"),
        Path("/var"),
        Path("/opt"),
        Path("/private"),
    }
    if os.name == "nt":
        candidates.update({Path("C:/"), Path("C:\\")})
        profile = os.environ.get("USERPROFILE")
        if profile:
            candidates.add(Path(profile))
    # Compare both the literal and the canonical form: on macOS /var is a
    # symlink to /private/var, so resolving only one side breaks the guard.
    forbidden: set[Path] = set()
    for candidate in candidates:
        forbidden.add(candidate)
        forbidden.add(candidate.resolve(strict=False))
    return forbidden


def assert_safe_path(path: Path) -> Path:
    """Return the canonical path to delete or raise :class:`UnsafePathError`.

    Symlinks are *not* resolved: the link itself is the residue, its target is
    never touched.
    """
    raw = path.expanduser()
    canonical = (
        raw.parent.resolve(strict=False) / raw.name
        if raw.is_symlink()
        else raw.resolve(strict=False)
    )

    if canonical in _forbidden_paths():
        raise UnsafePathError(f"refusing to remove protected path: {canonical}")
    if canonical == Path(canonical.anchor):
        raise UnsafePathError(f"refusing to remove filesystem root: {canonical}")
    return canonical


def _has_bimos_marker(base: Path) -> bool:
    """True when *base* looks like a BIMOS data directory, not a random folder."""
    if (base / "paths.json").exists():
        return True
    env_file = base / ".env"
    if env_file.is_file():
        try:
            if "BIMOS_" in env_file.read_text(encoding="utf-8", errors="replace"):
                return True
        except OSError:
            pass
    config = base / "config"
    if config.is_dir():
        try:
            if any(config.glob("*.yaml")):
                return True
        except OSError:
            pass
    return False


def _is_inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


# ── Runtime helpers ──────────────────────────────────────────────────────────


def _run(argv: list[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(argv, capture_output=True, text=True, check=check)
    except (OSError, subprocess.SubprocessError) as exc:  # pragma: no cover - env specific
        return subprocess.CompletedProcess(argv, returncode=1, stdout="", stderr=str(exc))


def container_runtime() -> str | None:
    for name in ("podman", "docker"):
        found = shutil.which(name)
        if found:
            return found
    return None


def _containers_for(image: str) -> list[str]:
    runtime = container_runtime()
    if runtime is None:
        return []
    proc = _run([runtime, "ps", "-a", "--filter", f"ancestor={image}", "-q"])
    return proc.stdout.split()


# ── Path discovery ───────────────────────────────────────────────────────────


def default_base_path() -> Path:
    return Path(os.getenv("BIMOS_BASE_PATH", str(Path.home() / ".bimos"))).expanduser()


def _read_paths_manifest(base: Path) -> dict[str, Any]:
    manifest = base / "paths.json"
    if not manifest.is_file():
        return {}
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _effective_external_paths(base: Path) -> list[tuple[Path, str]]:
    """Workspace/cache/logs entries that live *outside* ``base``.

    Those need their own removal because deleting ``base`` would not touch them.
    """
    record = _read_paths_manifest(base)
    candidates = {
        "workspace": os.getenv("BIMOS_WORKSPACE") or record.get("workspace"),
        "cache": os.getenv("BIMOS_CACHE") or record.get("cache"),
        "logs": os.getenv("BIMOS_LOGS") or record.get("logs"),
    }
    base_resolved = base.expanduser().resolve(strict=False)
    external: list[tuple[Path, str]] = []
    seen: set[Path] = set()
    for label, raw in candidates.items():
        if not raw:
            continue
        path = Path(str(raw)).expanduser()
        resolved = path.resolve(strict=False)
        if _is_inside(resolved, base_resolved) or resolved == base_resolved:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        external.append((path, f"BIMOS {label} (custom path)"))
    return external


def _running_app_bundle() -> Path | None:
    executable = Path(sys.executable).expanduser()
    for parent in executable.parents:
        if parent.suffix == ".app":
            return parent
    return None


def app_candidates(extra: list[Path] | None = None) -> list[Path]:
    candidates = [
        Path("/Applications/BIMOS.app"),
        Path.home() / "Applications" / "BIMOS.app",
    ]
    running = _running_app_bundle()
    if running is not None:
        candidates.append(running)
    env_override = os.getenv("BIMOS_APP_PATH")
    if env_override:
        candidates.append(Path(env_override).expanduser())
    for item in extra or []:
        candidates.append(item.expanduser())
    unique: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        key = candidate.expanduser().resolve(strict=False)
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def _macos_web_paths(home: Path) -> list[tuple[Path, str]]:
    return [
        (home / "Library" / "WebKit" / BUNDLE_ID, "WebKit website data"),
        (home / "Library" / "Caches" / BUNDLE_ID, "WebKit HTTP cache"),
        (home / "Library" / "HTTPStorages" / BUNDLE_ID, "HTTP storage state"),
        (
            home / "Library" / "Saved Application State" / f"{BUNDLE_ID}.savedState",
            "saved window state",
        ),
        (home / "Library" / "Preferences" / f"{BUNDLE_ID}.plist", "preferences"),
        (home / "Library" / "Application Support" / BUNDLE_ID, "application support state"),
    ]


def _linux_user_paths(home: Path) -> list[tuple[Path, str]]:
    return [
        (home / ".config" / "BIMOS.conf", "Qt configuration"),
        (home / ".local" / "share" / "BIMOS", "QtWebEngine data"),
        (home / ".cache" / "BIMOS", "QtWebEngine cache"),
        (home / ".pywebview", "pywebview state"),
    ]


def _linux_system_paths() -> list[tuple[Path, str]]:
    return [
        (Path("/opt/bimos"), "application tree"),
        (Path("/usr/bin/bimos"), "CLI wrapper"),
        (Path("/usr/share/applications/bimos.desktop"), "desktop entry"),
        (Path("/usr/share/pixmaps/bimos.png"), "icon"),
        (Path("/usr/share/doc/bimos"), "documentation"),
    ]


def _windows_user_paths() -> list[tuple[Path, str]]:
    local = os.environ.get("LOCALAPPDATA")
    appdata = os.environ.get("APPDATA")
    paths: list[tuple[Path, str]] = []
    if local:
        paths.extend(
            [
                (Path(local) / "pywebview", "pywebview state"),
                (Path(local) / "BIMOS.exe.WebView2", "WebView2 profile"),
            ]
        )
    if appdata:
        paths.append((Path(appdata) / "BIMOS", "application state"))
    return paths


def collect_residues(
    *,
    base_path: Path | None = None,
    include_app: bool = True,
    include_outputs: bool = False,
    system: bool = False,
    extra_app_paths: list[Path] | None = None,
) -> list[Residue]:
    """Return every BIMOS-owned location that exists on this host."""
    home = Path.home()
    base = (base_path or default_base_path()).expanduser()
    residues: list[Residue] = []

    if include_app:
        for candidate in app_candidates(extra_app_paths):
            if candidate.exists() or candidate.is_symlink():
                residues.append(
                    Residue(
                        kind="dir",
                        description="BIMOS application bundle",
                        path=candidate,
                    )
                )

    residues.append(
        Residue(kind="dir", description="BIMOS configuration and data", path=base)
    )
    for path, label in _effective_external_paths(base):
        residues.append(Residue(kind="dir", description=label, path=path))

    if include_outputs:
        for output in _recorded_output_dirs(base):
            residues.append(
                Residue(kind="dir", description="job output recorded by BIMOS", path=output)
            )

    system_name = platform.system()
    if system_name == "Darwin":
        for path, label in _macos_web_paths(home):
            residues.append(
                Residue(
                    kind="file" if path.suffix == ".plist" else "dir",
                    description=f"macOS {label}",
                    path=path,
                )
            )
    elif system_name == "Linux":
        for path, label in _linux_user_paths(home):
            residues.append(
                Residue(
                    kind="file" if path.suffix else "dir",
                    description=f"Linux {label}",
                    path=path,
                )
            )
        if system:
            for path, label in _linux_system_paths():
                residues.append(
                    Residue(
                        kind="file" if path.suffix else "dir",
                        description=f"Linux {label}",
                        path=path,
                        owner="system",
                    )
                )
    elif system_name == "Windows":
        for path, label in _windows_user_paths():
            residues.append(
                Residue(kind="dir", description=f"Windows {label}", path=path)
            )

    residues.append(
        Residue(
            kind="containers",
            description="BIMOS container image and its containers",
            image=os.getenv("BIMOS_IMAGE", DEFAULT_IMAGE),
        )
    )
    return residues


def _recorded_output_dirs(base: Path) -> list[Path]:
    """Output directories recorded by the job store that live outside ``base``."""
    jobs_dir = base / "workspace" / ".jobs"
    if not jobs_dir.is_dir():
        return []
    base_resolved = base.expanduser().resolve(strict=False)
    outputs: list[Path] = []
    seen: set[Path] = set()
    for record in sorted(jobs_dir.glob("*.json")):
        try:
            data = json.loads(record.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        raw = data.get("output_dir") if isinstance(data, dict) else None
        if not raw:
            continue
        path = Path(str(raw)).expanduser()
        resolved = path.resolve(strict=False)
        if _is_inside(resolved, base_resolved) or resolved == base_resolved:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        if path.exists():
            outputs.append(path)
    return outputs


# ── Removal ──────────────────────────────────────────────────────────────────


def _remove_path(residue: Residue, report: PurgeReport, *, dry_run: bool) -> None:
    if residue.path is None:
        report.skipped.append(f"{residue.description} (no path recorded)")
        return
    path = residue.path
    label = str(path)

    if not (path.exists() or path.is_symlink()):
        report.skipped.append(f"{label} (not present)")
        return

    target = assert_safe_path(path)
    if dry_run:
        report.removed.append(f"{label} (would remove)")
        return

    try:
        if target.is_symlink() or target.is_file():
            target.unlink()
        elif target.is_dir():
            shutil.rmtree(target)
        else:
            report.skipped.append(f"{label} (not a file or directory)")
            return
    except OSError as exc:
        report.errors.append(f"{label}: {exc}")
        return
    report.removed.append(label)


def _remove_containers(residue: Residue, report: PurgeReport, *, dry_run: bool) -> None:
    image = residue.image or DEFAULT_IMAGE
    runtime = container_runtime()
    if runtime is None:
        report.skipped.append(
            f"{image} (no container runtime installed; nothing to remove)"
        )
        return

    containers = _containers_for(image)
    exists = _run([runtime, "image", "exists", image]).returncode == 0
    if not containers and not exists:
        report.skipped.append(f"{image} (not present)")
        return

    for container in containers:
        if dry_run:
            report.removed.append(f"container {container} (would remove)")
            continue
        proc = _run([runtime, "rm", "-f", container])
        if proc.returncode != 0:
            report.errors.append(f"container {container}: {proc.stderr.strip()}")
        else:
            report.removed.append(f"container {container}")

    if exists:
        if dry_run:
            report.removed.append(f"image {image} (would remove)")
            return
        proc = _run([runtime, "rmi", "-f", image])
        if proc.returncode != 0:
            report.errors.append(f"image {image}: {proc.stderr.strip()}")
        else:
            report.removed.append(f"image {image}")


def remove_residue(
    residue: Residue, report: PurgeReport, *, dry_run: bool = False
) -> None:
    if residue.kind == "containers":
        _remove_containers(residue, report, dry_run=dry_run)
    else:
        _remove_path(residue, report, dry_run=dry_run)


def _check_base_marker(base: Path, *, force_path: bool) -> None:
    default = Path.home() / ".bimos"
    if force_path:
        return
    if base.expanduser().resolve(strict=False) == default.expanduser().resolve(strict=False):
        return
    if not base.exists():
        return
    if not _has_bimos_marker(base):
        raise UnsafePathError(
            f"custom BIMOS_BASE_PATH ({base}) does not look like a BIMOS directory; "
            "refusing to delete it (use --force-path to override)"
        )


def purge(
    *,
    dry_run: bool = False,
    keep_data: bool = False,
    deep: bool = False,
    remove_app: bool = False,
    include_outputs: bool = False,
    system: bool = False,
    force_path: bool = False,
    remove_machine: bool = False,
    base_path: Path | None = None,
    extra_app_paths: list[Path] | None = None,
) -> PurgeReport:
    """Remove every BIMOS-owned residue and return what happened."""
    base = (base_path or default_base_path()).expanduser()
    _check_base_marker(base, force_path=force_path)

    report = PurgeReport(dry_run=dry_run)
    if not remove_app:
        report.skipped.append("BIMOS.app (kept; pass --remove-app to delete it)")

    residues = collect_residues(
        base_path=base,
        include_app=remove_app,
        include_outputs=include_outputs,
        system=system,
        extra_app_paths=extra_app_paths,
    )
    if keep_data:
        keep_roots = [base]
        keep_roots.extend(path for path, _label in _effective_external_paths(base))
        keep_roots.extend(_recorded_output_dirs(base))
        resolved_roots = [root.expanduser().resolve(strict=False) for root in keep_roots]
        kept: list[Residue] = []
        for residue in residues:
            if residue.path is not None:
                resolved = residue.path.expanduser().resolve(strict=False)
                if any(
                    resolved == root or _is_inside(resolved, root) for root in resolved_roots
                ):
                    report.skipped.append(f"{residue.path} (kept: --keep-data)")
                    continue
            kept.append(residue)
        residues = kept

    # Data first, application last: the app bundle may be in use until the end.
    residues.sort(key=lambda item: item.kind == "dir" and item.description == "BIMOS application bundle")

    for residue in residues:
        try:
            remove_residue(residue, report, dry_run=dry_run)
        except UnsafePathError as exc:
            report.errors.append(str(exc))

    if deep:
        _prune_build_cache(report, dry_run=dry_run)
    if remove_machine:
        _remove_machine(report, dry_run=dry_run)

    if not dry_run:
        report.remaining = [
            residue.label()
            for residue in collect_residues(
                base_path=base,
                include_app=remove_app,
                include_outputs=include_outputs,
                system=system,
                extra_app_paths=extra_app_paths,
            )
            if residue.exists()
        ]
    return report


def verify_purge(
    *,
    base_path: Path | None = None,
    include_outputs: bool = True,
    system: bool = False,
    include_app: bool = False,
    extra_app_paths: list[Path] | None = None,
) -> PurgeReport:
    """Report which BIMOS-owned residues still exist (never deletes)."""
    report = PurgeReport()
    for residue in collect_residues(
        base_path=base_path,
        include_app=include_app,
        include_outputs=include_outputs,
        system=system,
        extra_app_paths=extra_app_paths,
    ):
        if residue.exists():
            report.remaining.append(residue.label())
    return report


def _prune_build_cache(report: PurgeReport, *, dry_run: bool) -> None:
    runtime = container_runtime()
    if runtime is None:
        report.skipped.append("build cache (no container runtime installed)")
        return
    if dry_run:
        report.removed.append("container build cache (would prune)")
        return
    proc = _run([runtime, "builder", "prune", "-f"])
    if proc.returncode != 0:
        report.errors.append(f"build cache: {proc.stderr.strip()}")
    else:
        report.removed.append("container build cache")


def _remove_machine(report: PurgeReport, *, dry_run: bool) -> None:
    runtime = container_runtime()
    if runtime is None or Path(runtime).name != "podman":
        report.skipped.append("podman machine (only applies to Podman)")
        return
    names = _run([runtime, "machine", "list", "--format", "{{.Name}}"]).stdout.split()
    if not names:
        report.skipped.append("podman machine (none)")
        return
    for name in names:
        if dry_run:
            report.removed.append(f"podman machine {name} (would remove)")
            continue
        proc = _run([runtime, "machine", "rm", "-f", name])
        if proc.returncode != 0:
            report.errors.append(f"podman machine {name}: {proc.stderr.strip()}")
        else:
            report.removed.append(f"podman machine {name}")


# ── Static manifest (shared with the macOS helper) ──────────────────────────


def static_manifest() -> dict[str, Any]:
    """Platform-independent description of every location BIMOS may create.

    Paths use ``~``/environment placeholders so the manifest is identical on
    every host and can be embedded verbatim in the shell uninstaller.
    """
    return {
        "version": 1,
        "bundle_id": BUNDLE_ID,
        "image": DEFAULT_IMAGE,
        "app_paths": [
            "/Applications/BIMOS.app",
            "~/Applications/BIMOS.app",
        ],
        "data_paths": [
            "~/.bimos",
        ],
        "macos_paths": [
            "~/Library/WebKit/org.bimos.app",
            "~/Library/Caches/org.bimos.app",
            "~/Library/HTTPStorages/org.bimos.app",
            "~/Library/Saved Application State/org.bimos.app.savedState",
            "~/Library/Preferences/org.bimos.app.plist",
            "~/Library/Application Support/org.bimos.app",
        ],
        "linux_paths": [
            "~/.config/BIMOS.conf",
            "~/.local/share/BIMOS",
            "~/.cache/BIMOS",
            "~/.pywebview",
            "/opt/bimos",
            "/usr/bin/bimos",
            "/usr/share/applications/bimos.desktop",
            "/usr/share/pixmaps/bimos.png",
            "/usr/share/doc/bimos",
        ],
        "windows_paths": [
            "%LOCALAPPDATA%/pywebview",
            "%LOCALAPPDATA%/BIMOS.exe.WebView2",
            "%APPDATA%/BIMOS",
        ],
    }


def print_manifest() -> str:
    return json.dumps(static_manifest(), indent=2, sort_keys=True)
