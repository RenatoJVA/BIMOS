"""Periodic table atomic numbers for QM multiplicity calculation."""

ATOMIC_NUMBER: dict[str, int] = {
    "H": 1,
    "He": 2,
    "Li": 3,
    "Be": 4,
    "B": 5,
    "C": 6,
    "N": 7,
    "O": 8,
    "F": 9,
    "Ne": 10,
    "Na": 11,
    "Mg": 12,
    "Al": 13,
    "Si": 14,
    "P": 15,
    "S": 16,
    "Cl": 17,
    "Ar": 18,
    "K": 19,
    "Ca": 20,
    "Fe": 26,
    "Cu": 29,
    "Zn": 30,
    "Br": 35,
    "I": 53,
}


def atomic_number(symbol: str) -> int:
    """Resolve element symbol or atomic-number string to Z."""
    token = symbol.strip()
    if token.isdigit():
        return int(token)
    z = ATOMIC_NUMBER.get(token.capitalize())
    if z is None:
        raise ValueError(f"Unknown element: {symbol!r}")
    return z
