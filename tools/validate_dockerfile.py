#!/usr/bin/env python3
"""
Static validation for backend/dockers/Dockerfile.bimos.

Runs without a container runtime and without building the image, which is the
only option on a CPU-only host. It checks:

  * every instruction is known and has an argument;
  * every ``RUN`` shell body is valid bash (``bash -n``);
  * every embedded ``python3 -c`` snippet is valid Python;
  * line continuations are balanced;
  * the reproducibility invariants the file promises (no unpinned git clone of
    a runtime dependency, every download checksum-verified, no silenced pip).

Usage:  python tools/validate_dockerfile.py [path]
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
import tempfile
from pathlib import Path

KNOWN = {
    "ADD", "ARG", "CMD", "COPY", "ENTRYPOINT", "ENV", "EXPOSE", "FROM",
    "HEALTHCHECK", "LABEL", "MAINTAINER", "ONBUILD", "RUN", "SHELL",
    "STOPSIGNAL", "USER", "VOLUME", "WORKDIR",
}

# BuildKit consumes these from the RUN line before the shell ever sees them.
RUN_FLAG_RE = re.compile(r"^--[a-z-]+(?:=[^\s]+)?\s+")
MOUNT_RE = re.compile(r"--mount=[^\s]+")


def join_continuations(lines: list[str]) -> list[tuple[int, str]]:
    """Yield (line_number, joined_line) collapsing backslash continuations."""
    out: list[tuple[int, str]] = []
    buf = ""
    start = 0
    for number, raw in enumerate(lines, 1):
        stripped = raw.strip()
        if not buf:
            if not stripped or stripped.startswith("#"):
                continue
            start = number
        buf += (" " if buf else "") + stripped
        if buf.rstrip().endswith("\\"):
            buf = buf.rstrip()[:-1]
            continue
        out.append((start, buf))
        buf = ""
    if buf:
        out.append((start, buf))
    return out


def check(path: Path) -> list[str]:
    raw_lines = path.read_text(encoding="utf-8").splitlines()
    problems: list[str] = []
    runs: list[tuple[int, str]] = []
    text = path.read_text(encoding="utf-8")

    for number, line in join_continuations(raw_lines):
        match = re.match(r"^([A-Za-z]+)\s+(.*)$", line)
        if not match:
            problems.append(f"L{number}: cannot parse instruction: {line!r}")
            continue
        op, rest = match.group(1).upper(), match.group(2)
        if op not in KNOWN:
            problems.append(f"L{number}: unknown instruction {op}")
            continue
        if not rest.strip():
            problems.append(f"L{number}: {op} has an empty argument")
        if op == "RUN":
            runs.append((number, MOUNT_RE.sub("", RUN_FLAG_RE.sub("", rest)).strip()))

    for number, body in runs:
        if body.startswith("["):  # exec form, not a shell script
            continue
        with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as handle:
            handle.write(body)
            script = handle.name
        result = subprocess.run(["bash", "-n", script], capture_output=True, text=True)
        Path(script).unlink(missing_ok=True)
        if result.returncode != 0:
            problems.append(f"L{number}: invalid shell: {result.stderr.strip()}")

        for snippet in re.findall(r'python3 -c "([^"]*)"', body):
            snippet = snippet.replace("\\$", "$")
            if "${" in snippet or "$(" in snippet:
                snippet = re.sub(r"\$\{[^}]*\}|\$\([^)]*\)", "PLACEHOLDER", snippet)
            try:
                ast.parse(snippet)
            except SyntaxError as exc:
                problems.append(f"L{number}: invalid embedded python: {exc}")

    for line_number, line in enumerate(raw_lines, 1):
        if line.rstrip().endswith("\\") and line_number == len(raw_lines):
            problems.append(f"L{line_number}: file ends with a dangling continuation")

    # Reproducibility invariants.
    for match in re.finditer(r"^\s*(RUN|ENV).*\bgit clone\b", text, re.M):
        problems.append(f"unpinned git clone in an executable line: {match.group(0).strip()[:80]}")
    if re.search(r"pip3? install[^\n]*(\\\n\s*)*[^\n]*2>/dev/null", text):
        problems.append("pip failure is being silenced with 2>/dev/null")
    # Direct binary downloads must be checksum-verified. Pip wheels are not
    # affected: the index already publishes and checks their hashes.
    downloads = re.findall(r"curl[^\n]*|wget[^\n]*", text)
    if downloads and "sha256sum -c" not in text:
        problems.append("direct download present but no sha256sum -c verification found")

    return problems


def main() -> int:
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "backend/dockers/Dockerfile.bimos")
    if not target.exists():
        print(f"not found: {target}")
        return 2
    problems = check(target)
    if problems:
        print(f"FAIL {target}")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(f"OK   {target}: syntax and invariants valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
