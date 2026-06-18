"""FASTA/YAML parsing and Boltz/ESMFold YAML generation."""

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


def read_yaml_sequences(yaml_path: Path) -> list[str]:
    """Return protein sequence strings from a Boltz-compatible YAML file."""
    import yaml as _yaml
    with open(yaml_path, encoding="utf-8") as handle:
        data = _yaml.safe_load(handle)
    sequences = []
    for entry in data.get("sequences", []):
        protein = entry.get("protein", {})
        seq = protein.get("sequence", "")
        if seq:
            sequences.append(seq)
    if not sequences:
        raise ValueError(f"No sequences found in {yaml_path}")
    return sequences


def ensure_yaml(path: Path, output_dir: Path) -> Path:
    """Return a YAML path inside output_dir. If input is FASTA, convert to YAML."""
    yaml_path = output_dir / f"{path.stem}.yaml"
    if path.suffix.lower() in (".yaml", ".yml"):
        if path != yaml_path:
            import shutil
            shutil.copy2(path, yaml_path)
    else:
        write_boltz_yaml(path, yaml_path)
    return yaml_path


def write_boltz_yaml(fasta_path: Path, yaml_path: Path) -> list[str]:
    """Write a Boltz-compatible YAML file from FASTA input."""
    headers: list[str] = []
    sequences: list[str] = []
    with open(fasta_path, encoding="utf-8") as handle:
        current_seq: list[str] = []
        for line in handle:
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if current_seq:
                    sequences.append("".join(current_seq))
                    current_seq = []
                headers.append(line[1:].split()[0])
            else:
                current_seq.append(line)
        if current_seq:
            sequences.append("".join(current_seq))
    if not sequences:
        raise ValueError(f"No sequences found in {fasta_path}")

    lines = ["sequences:"]
    for i, sequence in enumerate(sequences):
        lines.append("  - protein:")
        if i < len(headers):
            lines.append(f"      id: {headers[i]}")
        lines.append(f"      sequence: {sequence}")
    yaml_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return sequences
