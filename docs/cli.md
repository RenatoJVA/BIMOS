# CLI Reference

## Global Options

| Option | Description |
|--------|-------------|
| `--debug` | Enable debug logging |
| `--max` | Use all available CPU threads |
| `-g, --gui` | Start the desktop GUI |
| `-M, --manual` | Show the built-in manual |
| `--help` | Show help message |
| `--output-format, --format` | Output format: `text`, `json`, or `csv` |

## Commands

### `bimos predict`

Predict protein structure from a FASTA file using ESMFold.

```bash
bimos predict <fasta_file> [--output DIR] [--recycles N]
```

### `bimos predict-boltz`

Predict protein structure using Boltz-1.

```bash
bimos predict-boltz <fasta_file> [--output DIR] [--models N]
```

### `bimos dock`

Run molecular docking pipeline (receptor + ligands).

```bash
bimos dock <protein.pdb> <ligands.sdf> [--output DIR] [--dataset]
```

### `bimos workflow`

Run a GROMACS MD simulation pipeline.

```bash
bimos workflow -p <protein.pdb> [--ligand-gro FILE] [--ligand-itp FILE] [--output DIR]
```

### `bimos qm-orca`

Run ORCA Hirshfeld pipeline on a directory of .gro files.

```bash
bimos qm-orca <directory> [--jobs N] [--charge N]
```

### `bimos qm-g16`

Run Gaussian Hirshfeld pipeline on a directory of .gro files.

```bash
bimos qm-g16 <directory> [--jobs N] [--charge N]
```

### `bimos completion`

Generate shell completion script for bash, zsh, or fish.

```bash
eval "$(bimos completion bash)"
eval "$(bimos completion zsh)"
bimos completion fish > ~/.config/fish/completions/bimos.fish
```

### `bimos jobs`

List, inspect, and manage running jobs.

```bash
bimos jobs                    # List all jobs
bimos jobs --logs <job-id>    # Show job logs
bimos jobs kill <job-id>      # Cancel a job
```

### `bimos db`

Manage the BIMOS ligand database.

```bash
bimos db init                 # Initialize PostgreSQL schema
bimos db seed                 # Seed ligand database
bimos db list                 # List available datasets
bimos db query <text>         # Search ligands
bimos db export <dataset> <output>
```

### `bimos setup`

Configure BIMOS environment.

## Output Formats

Use `--format json` or `--format csv` for machine-readable output:

```bash
bimos predict sequence.fasta --format json
bimos dock receptor.pdb ligands.sdf --output-format csv
```
