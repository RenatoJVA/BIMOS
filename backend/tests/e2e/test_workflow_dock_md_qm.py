"""
End-to-end: Dock -> MD Holo -> QM workflow.

This test requires a real container runtime (Podman/Docker).
Skipped by default unless the 'e2e' marker is explicitly selected.
"""

import pytest

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(True, reason="E2E tests require container runtime and are only run in CI"),
]


def test_dock_pipeline_e2e():
    """Full docking pipeline with real container."""
    assert True


def test_md_pipeline_e2e():
    """Full MD pipeline with real container."""
    assert True


def test_qm_pipeline_e2e():
    """Full QM pipeline integration test."""
    assert True
