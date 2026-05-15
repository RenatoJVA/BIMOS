"""FASTA parsing and Boltz/ESMFold YAML generation."""

from pathlib import Path


def read_sequences(fasta_path: Path) -> list[str]:
    """Return protein sequence strings from a FASTA file."""
    sequences: list[str] = []
    current: list[str] = []
    with open(fasta_path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if current:
                    sequences.append("".join(current))
                current = []
            else:
                current.append(line)
    if current:
        sequences.append("".join(current))
    if not sequences:
        raise ValueError(f"No sequences found in {fasta_path}")
    return sequences


def write_boltz_yaml(fasta_path: Path, yaml_path: Path) -> list[str]:
    """Write a Boltz-compatible YAML file from FASTA input."""
    sequences = read_sequences(fasta_path)
    lines = ["sequences:"]
    for sequence in sequences:
        lines.append("  - protein:")
        lines.append(f"      sequence: {sequence}")
    yaml_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return sequences
