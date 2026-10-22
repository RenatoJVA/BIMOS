# BIMOS User Manual
## Biomolecular Modeling Suite

BIMOS unifies structural biology and quantum chemistry pipelines behind one CLI and one Desktop Dashboard: protein structure prediction (Boltz-2), molecular docking (AutoDock Vina), molecular dynamics (GROMACS), QM charge refinement (ORCA / Gaussian 16), and a full screening cascade (`bimos screen`) that chains them together.

> Tip: every command prints usage examples with `bimos <command> --help`, and the full CLI reference lives in [`docs/cli.md`](./docs/cli.md).

---

## 1. How BIMOS Works (Big Picture)

```
                    ┌──────────────┐
                    │  bimos CLI   │  or Desktop Dashboard (bimos -g)
                    └──────┬───────┘
                           │ every calculation becomes a tracked Job
              ┌────────────┼────────────────┐
              ▼            ▼                ▼
        Podman/Docker   Host binaries   Job store (~/.bimos)
        image: Vina,     (QM only):      status, logs,
        GROMACS, Boltz,  ORCA / G16 +    cancelation
        Meeko, RDKit     obabel
```

- **Heavy computing runs in containers** (`localhost/bimos/global:latest`, built once with `bimos setup`). You only need Podman (recommended) or Docker installed.
- **QM is the exception**: ORCA / Gaussian 16 run on your host (licensed separately, never bundled). BIMOS checks the toolchain *before* starting the job.
- **Everything is a job**: foreground, background (`-b`), or GUI (`-g`). Logs stream live; `bimos jobs` lists history; `bimos jobs kill <ID>` frees CPU/GPU immediately.
- **Results** default under `~/.bimos/workspace/` (override any time with `-o`).

> [!IMPORTANT]
> **Always run BIMOS globally.**
> Once installed, the `bimos` executable is available system-wide.
> Never execute scripts from inside `./backend` — work from your project directory.

---

## 2. Setup

```bash
bimos setup                  # full bootstrap: configs + container image
bimos setup --config-only    # only refresh ~/.bimos/config/*.yaml
bimos setup --force          # force a clean image rebuild
```

First launch creates `~/.bimos/` (`.env`, `config/*.yaml`, `workspace/`).

---

## 3. Core Concepts

### 3.1 Jobs & Background Execution

```bash
bimos dock protein.pdb phytocompounds_300 --dataset -b   # returns a Job ID at once
bimos jobs               # list all jobs and statuses
bimos jobs -l <JOB_ID>   # view logs for a job
bimos jobs kill <JOB_ID> # cancel a running job, kill its containers
```

Jobs can also be canceled from the Dashboard by closing/deleting the job card.

### 3.2 Exit Codes & Output Formats

Validation errors exit non-zero, so commands are script-safe (`set -e`).
Machine-readable output is available everywhere:

```bash
bimos predict sequence.fasta --format json
bimos dock receptor.pdb ligands.sdf --output-format csv
```

### 3.3 Where Results Go

| Pipeline | Default location |
|----------|------------------|
| `predict` | `~/.bimos/workspace/boltz/<name>/` |
| `dock` | `~/.bimos/workspace/docking/<protein>/` (`results/bests/` holds winners) |
| `workflow` Apo | `~/.bimos/workspace/md/Apo-<protein>/` |
| `workflow` Holo | `~/.bimos/workspace/md/Holo-<PROT>-<LIG>/` |
| `qm-orca` / `qm-g16` | Next to the inputs, as `<name>-hirsh.itp` |
| `screen` | Your `-o` dir: `apo/`, `dock/`, `qm/<CAND>/`, `holo/<CAND>/`, `screen_report.csv`, `screen.json` |

`--output` must be a directory (or a new path); pointing it inside one of the inputs is rejected.

### 3.4 Hardware Check

Every pipeline grades the machine against the active configuration *before* it
starts anything:

```bash
bimos doctor           # tables: detected hardware, per-process verdict, thresholds
bimos doctor --json    # same data for dashboards and CI
```

| Grade | Meaning | Effect |
|-------|---------|--------|
| Green | Supported as configured | Runs silently |
| Yellow | Runs, but the current values are above what is recommended | Warning, then runs |
| Red | Very likely to fail | Aborts |

The command is read-only. Thresholds are heuristics, and are also printed in its
third table: free VRAM 8 GB minimum / 16 GB recommended, per-job RAM above 70%
of installed memory (100% is refused), workspace disk 10 GB free / 50 GB
recommended, and more requested threads than physical cores. Anything that
cannot be measured is reported as such and never blocks a run.

To override a red verdict on purpose, append `--force`:

```bash
bimos predict sequence.fasta -o ./boltz_out --force
```

Prefer fixing a yellow by lowering the value in `~/.bimos/config/`. Use
`--force` only when you know the run will fit.

---

## 4. Workflows

### 4.1 Ligand Databases

Set `BIMOS_DATABASE_URL` to your PostgreSQL instance before using these
commands; the packaged template does not include credentials.

Curated sets for virtual screening without preparing your own library:

- `candidates_1000`: mixed drugs + phytocompounds.
- `phytocompounds_300`: 300 regional phytocompounds.

```bash
bimos db list
bimos db query "acid" --dataset phytocompounds_300   # MW, LogP, DrugLikeness
bimos db export candidates_1000 ./my_ligands.sdf     # SDF for docking
```

**Filter by ligand properties.** Both `query` and `export` filter on each compound's computed characteristics: molecular weight, LogP, H-bond donors/acceptors, rotatable bonds, polar surface area (TPSA), Lipinski violations, and drug-likeness score. `--druglike` applies the classic Lipinski/Veber preset (MW ≤ 500, LogP ≤ 5, HBD ≤ 5, HBA ≤ 10, rotables ≤ 10); any explicit flag overrides it:

```bash
bimos db query "acid" --dataset candidates_1000 --druglike --max-mw 450
bimos db export candidates_1000 ./druglike.sdf --druglike
bimos db export phytocompounds_300 ./leads.sdf --max-logp 3 --min-drug-likeness 0.5 --max-lipinski 1
bimos db export candidates_1000 ./approved.sdf --min-phase 4 --natural-product
```
Extra filters: `--max-tpsa`, `--max-rotables`, `--max-hbd/hba`, `--min-phase` (e.g. 4 = approved), `--max-aromatic`, `--natural-product`. `query` reports the total match count (results are capped at 50 rows). Without `--dataset`, only MW/LogP bounds apply (the PostgreSQL schema has no other property columns) and the rest are reported as ignored.

Filtered exports plug straight into docking or the cascade:

```bash
bimos dock target_protein.pdb ./druglike.sdf
bimos screen -p protein.pdb --ligands ./druglike.sdf --ligand-dir ./LIG-DIN
```

### 4.2 Structure Prediction (Boltz-2, GPU required)

Folds a protein from a FASTA (or Boltz YAML) file. One container run per model; the best model is copied to `<name>_best.{cif,pdb}` with its confidence JSON.

```bash
bimos predict sequence.fasta -o ./boltz_out
bimos predict input.yaml -o ./boltz_out --models 3
```

Boltz needs an NVIDIA GPU — the pipeline aborts with a clear CDI hint if none is visible inside the container.

Boltz-2 is the default. Add `--model boltz1` only to reproduce an older run.

### 4.3 Molecular Docking (Vina)

Meeko (pinned in the image) prepares PDBQT files, Vina docks each ligand `--times` (default 10), and the best pose per ligand lands in `results/bests/`.

```bash
bimos dock target_protein.pdb my_ligands.sdf --times 10
bimos dock target_protein.pdb candidates_1000 --dataset --gui
```

**Blind vs targeted docking.** By default the grid covers the whole receptor (blind). Target a pocket explicitly, by reference pose, or by residues (priority in that order):

```bash
bimos dock target_protein.pdb my_ligands.sdf --center 12.5 3.1 -0.4 --size 20 20 20
bimos dock target_protein.pdb my_ligands.sdf --center-on ref_pose.sdf --padding 4
bimos dock target_protein.pdb my_ligands.sdf --pocket-residues "A:375,347,351" --size 22 22 22
```

The effective box is logged at job start and the rendered Vina config is archived per complex (`results/<protein>-<ligand>/*.conf`). An oversized box covering the whole receptor logs a *"blind de facto"* warning. For a persistent box, edit `~/.bimos/config/docking.yaml` (`grid.mode: manual` + `center_*`/`size_*`).

### 4.4 Molecular Dynamics (GROMACS)

Full pipeline per run: Prep → Minimization → NVT → NPT → Production → Analysis (RMSD/RMSF/Rg/HBond/SASA `.xvg` files). Stages resume automatically if re-run.

```bash
bimos workflow -p protein.pdb -o ./md_apo                                        # Apo
bimos workflow -p protein.pdb --ligand-gro JZ4.gro --ligand-itp JZ4.itp -o ./md_holo  # Holo
bimos workflow --protein-dir ./Proteins --ligand-dir ./LIG-DIN -o ./md_batch      # batch Holo
```

**Ligand naming (important).** The ligand *file stem* names the output (`Holo-3HTB-JZ4/`), while the *internal* residue/moleculetype name inside the files (typically `UNK`/`LIG`) drives the GROMACS topology. BIMOS infers both, normalizes the working copy when they differ (the `.itp` wins as force-field authority), and logs exactly what it did.

### 4.5 Quantum Mechanics (ORCA / Gaussian 16)

Refines ligand charges (Hirshfeld) and writes them back into the topology. The directory must contain matching `.gro` + `.itp` pairs per ligand.

```bash
bimos qm-orca ./ligands_dir -j 4 --charge 0
bimos qm-g16 ./ligands_dir -j 4 --charge 1
```

Host requirements are validated before the job starts: `ORCA_PATH` / `GAUSSIAN_PATH` in `~/.bimos/.env` plus `obabel` in `PATH`.

### 4.6 Full Screening Cascade (`bimos screen`)

One command for the whole drug-discovery loop — **1 APO + 1 docking + N × (QM + full HOLO)** per protein:

```
protein.pdb ──► APO ──► Docking (1000 ligands) ──► ranking by Vina energy
                                                        ├─► QM ──► HOLO ──► Holo-3HTB-JZ4/
                                                        ├─► QM ──► HOLO ──► Holo-3HTB-L2/
                                                        └─► ... (top-N) ──► screen_report.csv
```

```bash
bimos screen -p protein.pdb --ligands ligands.sdf --ligand-dir ./LIG-DIN -o ./screen_out
bimos screen --protein-eq protein_eq.pdb --ligands ligands.sdf --ligand-dir ./LIG-DIN
bimos screen -p protein.pdb --dataset candidates_1000 --ligand-dir ./LIG-DIN \
    --pocket-residues "A:375,347,351" --qm g16 --top-n 50 --min-score -7.0
```

How it works, step by step:

1. **APO** (skipped with `--protein-eq`) validates system stability first — if it fails, nothing else burns GPU.
2. **Docking** accepts the same targeted grid options as `bimos dock`.
3. **Selection**: hits rank by Vina energy; `--min-score` drops weak hits; hits without a `.gro`+`.itp` pair in `--ligand-dir` are skipped with a warning. The top-N viable hits (default 5) proceed.
4. **QM** refines each hit's charges (`qm/<CAND>/<CAND>-hirsh.itp`).
5. **HOLO** runs one full MD per hit (`holo/<CAND>/`).
6. **Report** (`screen_report.csv`): full ranking with `selected`, `holo_ok`, paths, and per-hit errors.

A failed hit is marked and skipped — the cascade aborts only if *every* hit fails. Progress persists in `screen.json` (per-hit flags), so re-running resumes without repeating finished QM/HOLO runs. Failed runs still cost nothing extra: validation (binaries, pairs, cutoff) happens before any container starts.

**Library convention.** `--ligand-dir` must hold `.gro` + `.itp` pairs sharing the SDF candidate stems (`JZ4.sdf` ⇔ `JZ4.gro`/`JZ4.itp`). No parametrization is ever generated — Meeko only prepares PDBQT for Vina.

---

## 5. The Desktop Dashboard (GUI)

```bash
bimos -g                                            # standalone dashboard
bimos dock protein.pdb candidates_1000 --dataset -g  # run + monitor live
```

- **Live Job Tracking**: status of active and historical jobs in real time.
- **Terminal Simulation**: click a job for a live console with exact GROMACS/Vina/QM output.
- **Theme Sync**: follows the host OS dark/light mode.

---

## 6. Configuration

`~/.bimos/.env` (created on first launch):

- `BIMOS_WORKSPACE`: where results and logs go.
- `ORCA_PATH` / `GAUSSIAN_PATH`: host QM binaries.
- `BIMOS_IMAGE`: container image for MD/docking/folding.
- `BIMOS_REMOTE_URL`: thin-client mode — point the UI at a remote engine; leave blank for local.

Per-pipeline tuning lives in `~/.bimos/config/*.yaml` (`md`, `boltz`, `docking`, `orca`, `gaussian`): default (packaged) → custom (your edits) → max (`bimos --max` uses all CPU threads). Invalid values are clamped; see `bimos setup` to inspect profiles.

---

## 7. Legal Disclaimer

> [!CAUTION]
> **BIMOS does not distribute or license third-party computational tools.**
>
> - **ORCA** and **Gaussian 16** are commercial software. You must obtain your own valid licenses from their respective vendors. BIMOS only provides automation scripts that call these tools if already installed.
> - **AutoDock Vina**, **GROMACS**, **Boltz**, **Meeko**, **RDKit**, and **PyTorch** are open-source but subject to their own licenses. They ship inside the container image built by `bimos setup`, not with BIMOS itself. The complete list lives in [NOTICE.md](./NOTICE.md); use is governed by [TERMS.md](./TERMS.md) and data handling by [PRIVACY.md](./PRIVACY.md).
> - BIMOS is provided **"as is"** without any warranty. The authors are not responsible for results, data loss, or legal issues arising from its use.
>
> See [README.md](./README.md) for full terms and citation requirements.

## 8. Troubleshooting

- **White Screen on Launch**: check `~/.bimos/.env`. If `BIMOS_REMOTE_URL` points somewhere unreachable, the UI stalls — comment it out for local mode.
- **Segment Fault (Linux)**: missing OpenGL libs for the desktop shell; software rendering is enforced automatically, but ensure a standard display server.
- **Docker Permission Denied**: add your user to the `docker` group (`sudo usermod -aG docker $USER`) or use Podman.
- **Boltz aborts (no GPU)**: predictions require NVIDIA + CDI passthrough; MD/docking run fine on CPU.
- **`screen` aborts "Sin candidato viable"**: nobody passed `--min-score`, or hits lack `.gro`+`.itp` pairs in `--ligand-dir` — the message lists exactly who was skipped and why.
- **QM "binary not found"**: set `ORCA_PATH`/`GAUSSIAN_PATH` in `~/.bimos/.env` and install OpenBabel (`obabel`).
- **Validation errors**: exit non-zero with the reason (bad grid combo, output inside inputs, missing pairs) — safe for scripts.
- **Stuck jobs**: `bimos jobs kill <JOB_ID>` terminates containers and frees resources; then re-run — MD stages and `screen` resume where they stopped.
- **A pipeline refuses to start**: it graded itself red. Run `bimos doctor` to see which check failed and why, lower the offending value in `~/.bimos/config/`, or pass `--force` to override deliberately.
- **Legacy `boltz.yaml` warning about `step_scale`**: a config file from a Boltz-1 install was left in `~/.bimos/config/`. Delete it to regenerate the Boltz-2 defaults, or set `model: boltz1` if you want those values kept.
