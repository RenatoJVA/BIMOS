"""Static analysis: scan source files for potential secret leaks."""

from pathlib import Path

import pytest

BIMOS_ROOT = Path(__file__).resolve().parent.parent.parent / "bimos"

SUSPICIOUS_PATTERNS = [
    "api_key",
    "api_secret",
    "password",
    "passwd",
    "secret",
    "token",
    "auth_token",
    "access_key",
]

ALLOWED_USES = {
    "password": [
        "settings.py",  # database_url contains "password" in connection string
    ],
    "passwd": [
        "system.py",  # endpoint referring to /etc/passwd in path traversal test
    ],
    "secret": [
        "SECURITY.md",
        "settings.py",
    ],
    "api_key": [],
    "token": [
        "elements.py",
        "pipeline.py",
    ],
}


def _ignored_file(filename: str) -> bool:
    ignores = {"__pycache__", ".pyc", ".pyo", ".git"}
    return any(ig in filename for ig in ignores)


def test_no_hardcoded_passwords() -> None:
    suspicious: list[tuple[Path, int, str]] = []
    for py_file in BIMOS_ROOT.rglob("*.py"):
        if _ignored_file(py_file.name):
            continue
        lines = py_file.read_text(encoding="utf-8", errors="replace").splitlines()
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                continue
            for pattern in SUSPICIOUS_PATTERNS:
                if pattern in stripped.lower():
                    allowed = ALLOWED_USES.get(pattern, [])
                    if not any(fname in py_file.name for fname in allowed):
                        suspicious.append((py_file, i, stripped))
    if suspicious:
        msg = "\n".join(
            f"  {f.relative_to(BIMOS_ROOT)}:{ln}: {line}"
            for f, ln, line in suspicious[:20]
        )
        pytest.fail(f"Found {len(suspicious)} potential secret leaks:\n{msg}")


def test_no_environment_files_committed() -> None:
    env_files = list(BIMOS_ROOT.parent.glob(".env"))
    for f in env_files:
        if f.name == ".env.example":
            continue
        content = f.read_text(encoding="utf-8", errors="replace")
        if "=" in content and not content.startswith("#"):
            pytest.fail(f"Environment file {f} contains potential secrets")


def test_no_api_keys_in_source() -> None:
    api_key_patterns = [
        "sk-",  # OpenAI
        "AIza",  # Google
        "ghp_",  # GitHub PAT
        "gho_",  # GitHub OAuth
        "xoxb-",  # Slack Bot
        "xoxp-",  # Slack User
    ]
    findings: list[tuple[Path, int, str]] = []
    for py_file in BIMOS_ROOT.rglob("*.py"):
        if _ignored_file(py_file.name):
            continue
        lines = py_file.read_text(encoding="utf-8", errors="replace").splitlines()
        for i, line in enumerate(lines, 1):
            for pattern in api_key_patterns:
                if pattern in line and "example" not in line.lower():
                    findings.append((py_file, i, line.strip()))
    if findings:
        msg = "\n".join(
            f"  {f.relative_to(BIMOS_ROOT)}:{ln}: {line}"
            for f, ln, line in findings[:10]
        )
        pytest.fail(f"Found {len(findings)} potential API key leaks:\n{msg}")
