"""Runtime helpers used by the Nuitka build script."""

from pathlib import Path

import build as backend_build


def test_strip_reads_only_the_elf_header(tmp_path: Path, monkeypatch) -> None:
    elf = tmp_path / "bimos.bin"
    elf.write_bytes(b"\x7fELF" + b"\0" * 4096)
    other = tmp_path / "notes.txt"
    other.write_bytes(b"not an ELF file")

    calls: list[list[str]] = []
    monkeypatch.setattr(backend_build.shutil, "which", lambda _: "/usr/bin/strip")
    monkeypatch.setattr(
        backend_build.subprocess, "run", lambda cmd, **_kwargs: calls.append(cmd)
    )

    def _forbid_full_read(_path: Path) -> bytes:
        raise AssertionError("_strip_debug_binaries must not load whole binaries")

    monkeypatch.setattr(Path, "read_bytes", _forbid_full_read)

    backend_build._strip_debug_binaries(tmp_path)

    assert calls == [["/usr/bin/strip", "--strip-all", str(elf)]]
