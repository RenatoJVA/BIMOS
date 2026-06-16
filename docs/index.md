# BIMOS

**Biomolecular Modeling Suite** — A modern, high-performance toolkit for structural biology and computational chemistry.

## Overview

BIMOS integrates molecular docking, protein structure prediction, molecular dynamics simulations, and quantum chemistry calculations into a single, unified command-line tool and Python package.

## Key Features

- **Protein Structure Prediction** — ESMFold and Boltz-1
- **Molecular Docking** — AutoDock Vina with virtual screening datasets
- **Molecular Dynamics** — GROMACS-based MD simulations (Apo and Holo)
- **Quantum Chemistry** — ORCA and Gaussian Hirshfeld charge pipelines
- **Desktop GUI** — Cross-platform native interface (pywebview + React)
- **REST API** — FastAPI-based HTTP interface
- **Container-native** — All compute tools run inside containers

## Quick Start

```bash
pip install bimos

# Predict a protein structure
bimos predict sequence.fasta

# Run molecular docking
bimos dock receptor.pdb ligands.sdf

# Start the desktop GUI
bimos --gui
```
