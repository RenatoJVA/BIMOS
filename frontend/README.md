# BIMOS Frontend

**Biomolecular Modeling Suite — Desktop Dashboard**

A lightweight, responsive desktop interface for monitoring and managing BIMOS computational jobs.

## Overview

BIMOS is primarily a **CLI-first** engine. This frontend provides a premium graphical dashboard for tracking long-running scientific jobs (ESMFold structure prediction, Vina docking, GROMACS MD, QM pipelines).

## Tech Stack

- **React 18** + **TypeScript**
- **Vite** for build tooling
- **Vanilla CSS** — glassmorphic dark/light theme
- **Fetch API** → FastAPI backend at `http://127.0.0.1:8000`

## Development

```bash
cd frontend
bun install     # or npm install
bun run dev     # or npm run dev
bun run build   # production build
```

The built assets are copied to `backend/bimos/ui/` by the build script (`builder.py`).

## Citation

If you use the BIMOS desktop interface in your research, please cite:

```bibtex
@software{bimos2025,
  author    = {Renato J. V. A. and Ponze Bellido, L. J. and Quispe Ppacco, D. J. and Carbajal, P. and Del Carpio, F. and Gómez Valdez, B.},
  title     = {BIMOS: Biomolecular Modeling Suite},
  year      = {2025},
  url       = {https://github.com/RenatoJVA/BIMOS},
  note      = {Version 0.1.0}
}
```

---

## Author

**Renato J. V. A.** — Lead Developer

## Team

- L. J. Ponze Bellido — Coauthor
- D. J. Quispe Ppacco — Coauthor
- P. Carbajal — Coauthor
- F. Del Carpio — Coauthor
- B. Gómez Valdez (Director, CIIM) — Coauthor

---

*Part of the [BIMOS](https://github.com/RenatoJVA/BIMOS) project — Biomolecular Modeling Suite.*
