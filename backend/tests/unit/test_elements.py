import pytest

from bimos.quantum_chemistry.elements import atomic_number, ATOMIC_NUMBER


def test_atomic_number_hydrogen() -> None:
    assert atomic_number("H") == 1


def test_atomic_number_carbon() -> None:
    assert atomic_number("C") == 6


def test_atomic_number_oxygen() -> None:
    assert atomic_number("O") == 8


def test_atomic_number_iron() -> None:
    assert atomic_number("Fe") == 26


def test_atomic_number_case_insensitive() -> None:
    assert atomic_number("h") == 1
    assert atomic_number("C") == 6
    assert atomic_number("FE") == 26


def test_atomic_number_numeric_string() -> None:
    assert atomic_number("6") == 6
    assert atomic_number("26") == 26


def test_atomic_number_unknown_raises() -> None:
    with pytest.raises(ValueError, match="Unknown element"):
        atomic_number("Xx")


def test_atomic_number_dict_contents() -> None:
    assert ATOMIC_NUMBER["H"] == 1
    assert ATOMIC_NUMBER["C"] == 6
    assert ATOMIC_NUMBER["N"] == 7
    assert ATOMIC_NUMBER["O"] == 8
    assert ATOMIC_NUMBER["Fe"] == 26
