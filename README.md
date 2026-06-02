<div align="center">

  # BIMOS

  **Biomolecular Modeling Suite**

  [![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
  [![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/)
  [![Platform](https://img.shields.io/badge/platform-linux%20%7C%20macOS%20%7C%20Windows-lightgrey)]()

  A modern, high-performance toolkit unifying structural biology and quantum chemistry pipelines — from structure prediction and molecular dynamics to virtual screening and QM charge refinement.

  [Installation](#installation) •
  [Quick Start](#quick-start) •
  [Documentation](#documentation) •
  [Citation](#citation)

</div>

---

## Features

- **Protein Structure Prediction** — Predict 3D structures from amino acid sequences using ESMFold and Boltz-1.
- **Molecular Docking** — High-throughput virtual screening with AutoDock Vina using built-in curated ligand databases.
- **Molecular Dynamics** — Automated GROMACS simulation pipeline (solvation, ionization, minimization, NVT, NPT, production).
- **Quantum Mechanics** — Automated Hirshfeld charge refinement via ORCA or Gaussian 16 pipelines with `.itp` integration.
- **Desktop Dashboard** — Real-time GUI for monitoring jobs, streaming logs, and managing workflows.
- **Background Jobs** — Run massively parallel simulations without blocking the terminal.

## Installation

### Pre-built Installers

| Platform | Format | Download |
|----------|--------|----------|
| Linux    | `.deb` | [Releases](https://github.com/RenatoJVA/BIMOS/releases) |
| Windows  | `.exe` | [Releases](https://github.com/RenatoJVA/BIMOS/releases) |
| macOS    | `.dmg` | [Releases](https://github.com/RenatoJVA/BIMOS/releases) |

### From Source

```bash
# Clone the repository
git clone https://github.com/RenatoJVA/BIMOS.git
cd BIMOS

# Install the backend
cd backend
pip install -e .

# (Optional) Build the frontend
cd ../frontend
bun install && bun run build
```

### Requirements

- **Podman** (recommended) or **Docker** — required for running all computational pipelines. BIMOS auto-detects which one is available at runtime.
- **Python 3.12+** — for source installation.
- **ORCA** or **Gaussian 16** (optional) — only needed for QM workflows. *These are commercial/third-party tools and are NOT bundled with BIMOS.*

## Quick Start

```bash
# Launch the Desktop Dashboard
bimos -g

# Predict a protein structure
bimos predict --fasta sequence.fasta --name my_protein

# Run molecular docking with a built-in dataset
bimos dock receptor.pdb candidates_1000 --dataset

# Run a full GROMACS MD pipeline
bimos workflow -p protein.pdb

# Quantum mechanics (requires external ORCA/Gaussian)
bimos qm-orca ./ligands -j 4 --charge 0
```

## Documentation

See [MANUAL.md](./MANUAL.md) for a comprehensive user guide covering all workflows, job management, and configuration.

```bash
# Or view the manual from the CLI
bimos -M
```

## Project Structure

```
BIMOS/
├── backend/          # Python CLI + FastAPI server + computational pipelines
│   └── bimos/        # Core package (cli, api, docking, md, prediction, qm, ...)
├── frontend/         # React + TypeScript desktop dashboard
├── installer/        # Cross-platform packaging (NSIS, DMG, DEB)
├── builder.py        # Master build script (Nuitka + installer)
└── MANUAL.md         # Full user manual
```

## Legal Notice & Disclaimer

### Third-Party Software

BIMOS orchestrates several third-party computational tools. Open-source tools are bundled in the Docker image (built via `bimos setup`). Commercial tools are **not** bundled — you must obtain your own licenses.

| Tool | Category | License | Bundled? |
|------|----------|---------|----------|
| Docker / Podman | Container runtime | Apache 2.0 | No (install separately — Podman recommended) |
| AutoDock Vina | Molecular docking | Apache 2.0 | Yes (via Docker) |
| GROMACS | Molecular dynamics | GPLv2 | Yes (via Docker) |
| ESMFold | Structure prediction | MIT | Yes (via Docker) |
| Boltz-1 | Structure prediction | MIT | Yes (via Docker) |
| RDKit / Meeko | Cheminformatics | BSD | Yes (via Docker) |
| **ORCA** | Quantum chemistry | **Commercial** | **No** |
| **Gaussian 16** | Quantum chemistry | **Commercial** | **No** |

> [!WARNING]
> **BIMOS does not provide, distribute, or grant licenses for ORCA or Gaussian.** Users must purchase or obtain their own valid licenses from the respective vendors. BIMOS simply provides automation scripts that call these tools if they are already installed on your system.
>
> The Docker image built by `bimos setup` contains only open-source tools (AutoDock Vina, GROMACS, ESMFold, Boltz-1, RDKit) under their respective licenses.

### Limitation of Liability

BIMOS is provided **"as is"**, without warranty of any kind, express or implied. The authors and contributors are **not responsible** for:

- Any results, interpretations, or conclusions derived from using this software.
- Compliance with third-party software licenses.
- Any damages, data loss, or legal issues arising from the use of BIMOS.

### Open Source Commitment

BIMOS itself is **100% open source** under the GPLv3 license. All computational pipelines are built on open-source tools wherever possible. The use of proprietary software (ORCA, Gaussian) is entirely optional and at the user's discretion.

## Citation

If you use BIMOS in your research, teaching, or commercial work, you **must cite** the following:

```bibtex
@software{bimos2025,
  author    = {Renato J. V. A. and Ponze Bellido, L. J. and Quispe Ppacco, D. J. and Carbajal, P. and Del Carpio, F. and Gómez Valdez, B.},
  title     = {BIMOS: Biomolecular Modeling Suite},
  year      = {2025},
  url       = {https://github.com/RenatoJVA/BIMOS},
  note      = {Version 0.1.0}
}
```

**Repository:** [https://github.com/RenatoJVA/BIMOS](https://github.com/RenatoJVA/BIMOS)

Please also cite the individual tools used in your workflow (GROMACS, AutoDock Vina, ESMFold, Boltz-1, ORCA, Gaussian, etc.) according to their respective guidelines.

## Team

- **Renato J. V. A.** — Author & Lead Developer
- L. J. Ponze Bellido — Coauthor
- D. J. Quispe Ppacco — Coauthor
- P. Carbajal — Coauthor
- F. Del Carpio — Coauthor
- B. Gómez Valdez (Director, CIIM) — Coauthor

## Acknowledgments

This project was funded by the **Universidad Católica de Santa María** through a competitive research grant.

## License

BIMOS is free software distributed under the **GNU General Public License v3.0**. See [LICENSE](./LICENSE) for details.

---

<div align="center">
  <sub>Built with ❤️ for the computational chemistry and structural biology community.</sub>
</div>
