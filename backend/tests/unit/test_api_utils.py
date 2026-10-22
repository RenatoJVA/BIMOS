"""Utilities shared by API endpoints: unique dirs and bounded uploads."""

import asyncio
import io
from pathlib import Path

import pytest
from fastapi import HTTPException, UploadFile

from bimos.api.utils import new_job_dir, read_upload


def test_new_job_dir_is_unique(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from bimos.config.settings import settings

    monkeypatch.setattr(settings, "workspace_path", tmp_path)
    first = new_job_dir("predict", "protein")
    second = new_job_dir("predict", "protein")

    assert first != second
    assert first.is_dir() and second.is_dir()
    assert first.parent == second.parent == tmp_path / "predict"


def test_read_upload_enforces_limit() -> None:
    upload = UploadFile(filename="ligand.sdf", file=io.BytesIO(b"0123456789"))
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(read_upload(upload, max_bytes=4))
    assert exc_info.value.status_code == 413


def test_read_upload_accepts_within_limit() -> None:
    upload = UploadFile(filename="ligand.sdf", file=io.BytesIO(b"0123456789"))
    assert asyncio.run(read_upload(upload, max_bytes=10)) == b"0123456789"
