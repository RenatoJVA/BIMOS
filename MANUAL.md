# BIMOS User Manual
## Biomolecular Modeling Suite

BIMOS is a modern, high-performance toolkit designed to unify structural biology and quantum chemistry pipelines. It provides an intuitive CLI and a powerful Desktop Dashboard to orchestrate tasks across structure prediction, molecular dynamics (MD), molecular docking, and virtual screening.

---

## 1. Important Execution Guidelines

> [!IMPORTANT]
> **Always run BIMOS globally.** 
> Once installed or compiled, the executable is available system-wide as `bimos`. 
> You should **never** execute scripts directly from the `./backend` folder. Navigate to your project or workspace directory and use the `bimos` command.

---

## 2. Quick Start & Core Workflows

### 2.1 Virtual Screening & Built-in Databases
BIMOS includes curated local databases ready for massive virtual screening, eliminating the need to prepare your own ligand datasets manually.

Available Datasets:
- `candidates_1000`: Mixed curated subset of drugs and phytocompounds.
- `phytocompounds_300`: Exclusive collection of 300 regional phytocompounds.

**Search the Database:**
Query compounds by name, SMILES, or ChEMBL ID, and evaluate their properties (MW, LogP, DrugLikeness):
```bash
bimos db query "acid" --dataset phytocompounds_300
```

**Export a Dataset:**
Export the full dataset into an SDF file for external use:
```bash
bimos db export candidates_1000 ./my_screening_ligands.sdf
```

### 2.2 Molecular Docking (Vina)
Perform molecular docking using custom ligands or directly from our curated virtual screening databases. BIMOS will automatically handle 2D to 3D conformation generation and grid calculations.

**Standard Docking (Custom SDF):**
```bash
bimos dock target_protein.pdb my_ligands.sdf --times 10
```

**Direct Virtual Screening (Using built-in dataset):**
Launch a full virtual screening campaign bypassing manual SDF creation:
```bash
bimos dock target_protein.pdb candidates_1000 --dataset --gui
```

### 2.3 Structural Prediction (AI Folding)
Predict the 3D structure of a protein directly from its amino acid sequence using integrated AI models.
```bash
bimos predict --fasta sequence.fasta --name my_protein
```

### 2.4 Molecular Dynamics (GROMACS)
BIMOS automates the entire GROMACS simulation pipeline (Topology Prep, Solvation, Ionization, Minimization, NVT, NPT, and Production).
```bash
bimos workflow -p protein.pdb
```

### 2.5 Quantum Mechanics (QM)
Automate Hirshfeld charge generation and structure optimization pipelines. These workflows update your `.itp` files dynamically with calculated QM charges.
```bash
# ORCA Pipeline (Multiple threads)
bimos qm-orca ./ligands_dir -j 4 --charge 0

# Gaussian 16 Pipeline
bimos qm-g16 ./ligands_dir -j 4 --charge 1
```

---

## 3. The Desktop Dashboard (GUI)

BIMOS provides a beautiful, real-time Desktop UI to track and monitor all background and foreground processes. 

To launch the standalone dashboard:
```bash
bimos -g
```

To run a command and immediately open the dashboard to monitor it:
```bash
bimos dock protein.pdb candidates_1000 --dataset -g
```

### Dashboard Features:
- **Live Job Tracking**: Monitor the status of all active and historical jobs in real-time.
- **Terminal Simulation**: Click on any running job to access a live streaming console showing exact output from GROMACS, Vina, or AI folding models.
- **Theme Sync**: The dashboard automatically synchronizes with your host OS theme (Dark/Light mode).

---

## 4. Job Management & Background Execution

BIMOS is designed to run massively parallel tasks without freezing your terminal.

**Running in Background:**
Any long-running command can be sent to the background by appending `-b` or `--background`.
```bash
bimos dock protein.pdb phytocompounds_300 --dataset -b
```
The CLI will return immediately with a `Job ID`, allowing you to close the terminal or launch more jobs.

**Managing Jobs via CLI:**
You can list all jobs, view their status, or check logs directly from the terminal.
```bash
bimos jobs               # List all jobs and their statuses
bimos jobs -l <JOB_ID>   # View logs for a specific job
```

**Canceling a Job (Kill):**
If you need to stop a running job and release its resources (RAM, GPU), you can instantly terminate it and destroy all associated containers:
```bash
bimos jobs kill <JOB_ID>
```
*Note: Jobs can also be canceled seamlessly from the Desktop Dashboard by closing or deleting the job card.*

---

## 5. Configuration (.env)

When BIMOS is launched for the first time, it generates a `.env` configuration file in your home directory (`~/.bimos/.env`).

Key variables you can customize:
- `BIMOS_WORKSPACE`: Where calculation results and logs are stored.
- `ORCA_PATH` / `GAUSSIAN_PATH`: Absolute paths to host QM binaries.
- `BIMOS_IMAGE`: The container image name for containerized MD/Folding execution.
- `BIMOS_REMOTE_URL`: *(Thin Client Mode)* Set this to connect the local UI to a remote BIMOS engine API. Leave commented/blank for local execution.

---

## 5. Troubleshooting

- **White Screen on Launch**: If you launch the GUI (`bimos -g`) and see a white screen, check your `~/.bimos/.env` file. If `BIMOS_REMOTE_URL` is enabled but the remote server is unreachable, the UI will stall. Comment it out to run locally.
- **Segment Fault (Linux)**: Some Linux distributions lack compatible OpenGL libraries for the desktop interface. BIMOS attempts to enforce software rendering automatically, but ensure your display server supports standard rendering.
- **Docker Permission Denied**: BIMOS requires Docker/Podman to run simulations. Ensure your user belongs to the `docker` group (`sudo usermod -aG docker $USER`).
