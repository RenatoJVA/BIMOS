# CLI Reference

Run `bimos --help` or `bimos <command> --help` for the authoritative details.
Every command below also prints usage examples via its `--help` epilog.

## Global Options

| Option | Description |
|--------|-------------|
| `--debug` | Enable debug logging |
| `--max` | Use all available CPU threads |
| `-g, --gui` | Start the desktop GUI |
| `-M, --manual` | Show the built-in manual |
| `--help` | Show help message |
| `--output-format, --format` | Output format: `text`, `json`, or `csv` |

## Output Directories

When `--output/-o` is omitted, results go under `~/.bimos/workspace/`:

| Pipeline | Default location |
|----------|------------------|
| `predict` | `~/.bimos/workspace/boltz/<name>/` |
| `dock` | `~/.bimos/workspace/docking/<protein>/` |
| `workflow` (Apo) | `~/.bimos/workspace/md/Apo-<protein>/` |
| `workflow` (Holo) | `~/.bimos/workspace/md/Holo-<PROT>-<LIG>/` |
| `qm-orca` / `qm-g16` | Next to the inputs, as `<name>-hirsh.itp` |

`--output` must be a directory (or a non-existing path); pointing it
inside one of the inputs is rejected.

## Jobs & Background Execution

Every calculation runs as a tracked job. Append `-b/--background` to any
pipeline to return immediately, then inspect it later:

```bash
bimos dock receptor.pdb ligands.sdf -b
bimos jobs                    # List all jobs
bimos jobs -l <JOB_ID>        # Show job logs
bimos jobs kill <JOB_ID>      # Cancel a running job
```

Exit codes: validation errors exit non-zero, so commands are safe to use
in scripts (`set -e`).

## Commands

### `bimos predict` / `bimos predict-boltz`

Predict protein structure from a FASTA or Boltz YAML file using Boltz-2
(requires an NVIDIA GPU). Pass `--model boltz1` only to reproduce results from
an older Boltz-1 run.

```bash
bimos predict sequence.fasta -o ./boltz_out
bimos predict input.yaml -o ./boltz_out --models 3
```

### `bimos doctor`

Check whether this machine can run BIMOS. Read-only: nothing is launched and no
file is modified.

```bash
bimos doctor           # human-readable tables
bimos doctor --json    # machine-readable, for dashboards and CI
```

Each process is graded green / yellow / red against the active configuration in
`~/.bimos/config/`:

| Grade | Meaning | Effect |
| --- | --- | --- |
| Green | Supported as configured | Runs silently |
| Yellow | Runs, but above the recommended values | Warning, then runs |
| Red | Very likely to fail | Aborts, unless `--force` is passed |

Thresholds (heuristics, printed by the command): free VRAM 8 GB minimum and
16 GB recommended, per-job RAM above 70% of installed memory, workspace disk
10 GB free minimum and 50 GB recommended, and more requested threads than
physical cores. Values that cannot be measured never block a run.

Fix a yellow by lowering the value in `~/.bimos/config/`. Use `--force` only
when you deliberately want to run anyway:

```bash
bimos predict sequence.fasta -o ./boltz_out --force
```

### `bimos dock`

Screen an SDF set of ligands against a PDB receptor with AutoDock Vina,
or use a curated dataset directly.

```bash
bimos dock receptor.pdb ligands.sdf -o ./docking_out
bimos dock receptor.pdb candidates_1000 --dataset
```

#### Directed docking (site-specific box)

By default the grid covers the whole receptor (blind docking). Target a
pocket with one of these (priority: explicit XYZ > reference > residues):

```bash
# Explicit center + size (Angstroms, receptor frame)
bimos dock receptor.pdb ligands.sdf --center 12.5 3.1 -0.4 --size 20 20 20
# Center on a co-crystallized / reference ligand pose
bimos dock receptor.pdb ligands.sdf --center-on ref_pose.sdf --padding 4
# Center on pocket residues (chain prefix optional, ranges allowed)
bimos dock receptor.pdb ligands.sdf --pocket-residues "A:375,347,351-355" --size 22 22 22
```

The effective box is logged at job start and the rendered Vina config is
archived per complex under `results/<protein>-<ligand>/*.conf`. An
oversized box covering the whole receptor logs a "blind de facto" warning.
Alternatively, set a persistent box in `~/.bimos/config/docking.yaml`
(`grid.mode: manual` + `center_*`/`size_*`).

### `bimos workflow`

Run a GROMACS MD simulation (Prep -> Min -> NVT -> NPT -> SDM -> Analysis).

```bash
# Apo (protein only)
bimos workflow -p protein.pdb -o ./md_apo
# Holo (protein + ligand .gro/.itp pair)
bimos workflow -p protein.pdb --ligand-gro JZ4.gro --ligand-itp JZ4.itp -o ./md_holo
# Batch Holo (every protein x ligand pair)
bimos workflow --protein-dir ./Proteins --ligand-dir ./LIG-DIN -o ./md_batch
```

Holo naming: the ligand **file stem** names the output
(`Holo-<PROT>-<LIG>/`, e.g. `Holo-3HTB-JZ4/`), while the **internal**
residue/moleculetype name found inside the files (typically `UNK`/`LIG`)
drives the GROMACS topology. Mismatches are normalized automatically and
logged; the `.itp` moleculetype wins as the force-field authority.

### `bimos screen`

Run the full virtual screening cascade in one batch:
APO -> Docking -> QM charge refinement -> top-N HOLO + report.

```bash
bimos screen -p protein.pdb --ligands ligands.sdf --ligand-dir ./LIG-DIN -o ./screen_out
bimos screen --protein-eq protein_eq.pdb --ligands ligands.sdf --ligand-dir ./LIG-DIN
bimos screen -p protein.pdb --dataset candidates_1000 --ligand-dir ./LIG-DIN \
    --pocket-residues "A:375,347,351" --qm g16 --min-score -7.0
```

The ligand library (`--ligand-dir`) must hold `.gro` + `.itp` pairs sharing
the SDF candidate stems (e.g. `JZ4.sdf` plus `JZ4.gro`/`JZ4.itp`). Hits are
ranked by Vina energy; the top-N hits with a complete pair (default 5,
`--top-n`) each run QM + a full HOLO into `holo/<CAND>/`. A failed hit is
marked and skipped; the cascade aborts only if every hit fails.
Progress persists in `screen.json`, so re-running resumes after the last
completed stage. The docking grid accepts the same targeted options as
`bimos dock` (`--center/--size`, `--center-on`, `--pocket-residues`).

### `bimos qm-orca` / `bimos qm-g16`

Refine ligand charges (Hirshfeld) with ORCA or Gaussian 16. The directory
must contain matching `.gro` + `.itp` pairs per ligand
(e.g. `JZ4.gro` + `JZ4.itp`); updated topologies are written next to the
inputs as `<name>-hirsh.itp`.

```bash
bimos qm-orca ./ligands -j 4 --charge 0
bimos qm-g16 ./ligands -j 4 --charge 1
```

Requirements (host, validated before the job starts): the QM binary
(`ORCA_PATH` / `GAUSSIAN_PATH` in `~/.bimos/.env`) plus OpenBabel
(`obabel` in `PATH`). These tools are licensed separately and are not
bundled with BIMOS.

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

Manage the BIMOS ligand database. Set `BIMOS_DATABASE_URL` first (PostgreSQL,
for example `postgresql+psycopg://bimos:<password>@localhost/bimos`); the
packaged template intentionally ships it unset.

```bash
bimos db init                 # Initialize PostgreSQL schema
bimos db seed                 # Seed ligand database
bimos db list                 # List available datasets
bimos db query <text>         # Search ligands
bimos db export <dataset> <output>
```

`query` and `export` filter by ligand properties
(`--min-mw/--max-mw`, `--min-logp/--max-logp`, `--max-hbd/hba/rotables/tpsa/lipinski`,
`--min-drug-likeness`, `--min-phase`, `--max-aromatic`, `--natural-product`);
`--druglike` applies the Lipinski/Veber preset (`query` also prints the total match count):

```bash
bimos db query "acid" -d candidates_1000 --druglike --max-mw 450
bimos db export candidates_1000 ./druglike.sdf --druglike
```

### `bimos setup`

Configure the BIMOS environment (user YAML configs + container image).

```bash
bimos setup                   # Full bootstrap
bimos setup --config-only     # Only refresh ~/.bimos/config/*.yaml
bimos setup --force           # Force a clean image rebuild
```

## Output Formats

Use `--format json` or `--format csv` for machine-readable output:

```bash
bimos predict sequence.fasta --format json
bimos dock receptor.pdb ligands.sdf --output-format csv
```

## CLI <-> API Parity Notes

- `POST /dock` accepts the same grid options (`center_x/y/z`,
  `size_x/y/z`, `pocket_residues`, `padding`, `reference` upload) but has
  no curated-dataset mode: upload an SDF exported via `bimos db export`.
- `POST /simulate-holo` takes single protein + ligand files; batch
  protein-x-ligand screening is CLI-only (`--protein-dir/--ligand-dir`).
