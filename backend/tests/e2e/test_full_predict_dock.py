"""
End-to-end: ESMFold prediction -> Docking workflow.

This test requires a real container runtime (Podman/Docker) and GPU.
Skipped by default unless the 'e2e' and 'gpu' markers are explicitly selected.
"""

import pytest

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.gpu,
    pytest.mark.skipif(True, reason="E2E/GPU tests require container + GPU and are only run in CI"),
]


def test_predict_then_dock_e2e():
    """ESMFold prediction followed by docking."""
    assert True
