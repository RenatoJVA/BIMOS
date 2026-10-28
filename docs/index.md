# BIMOS

**Biomolecular Modeling Suite** — A modern, high-performance toolkit for structural biology and computational chemistry.

## Overview

BIMOS integrates molecular docking, protein structure prediction, molecular dynamics simulations, and quantum chemistry calculations into a single, unified command-line tool and Python package.

## Key Features

- **Protein Structure Prediction** — Boltz (GPU)
- **Molecular Docking** — AutoDock Vina with virtual screening datasets
- **Molecular Dynamics** — GROMACS-based MD simulations (Apo and Holo)
- **Quantum Chemistry** — ORCA and Gaussian Hirshfeld charge pipelines
- **Desktop GUI** — Cross-platform native interface (pywebview + React)
- **REST API** — FastAPI-based HTTP interface
- **Containerized compute** — Boltz, Vina and GROMACS run in a Podman/Docker image; ORCA/G16 run on the licensed host

## Quick Start

See [Installation](installation.md) and [Deployment](deployment.md) for
installers, the platform support matrix (Linux is recommended for the full
stack), GPU requirements and remote access.

```bash
pip install bimos

# Predict a protein structure
bimos predict sequence.fasta

# Run molecular docking
bimos dock receptor.pdb ligands.sdf

# Start the desktop GUI
bimos -g
```
