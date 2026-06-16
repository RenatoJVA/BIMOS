"""
Mutation testing placeholder.

This test exists so that mutmut can detect the test suite.
Real mutation testing is done with:
    mutmut run --paths-to-mutate bimos/infrastructure/
"""

import pytest


def test_suicide() -> None:
    """Suicide test: always passes. Placeholder for mutmut detection."""
    assert True
