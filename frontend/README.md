# BIMOS Frontend

Welcome to the **Biomolecular Modeling Suite (BIMOS)** Frontend. This is a lightweight, minimalist, and responsive dashboard designed to interface with the robust BIMOS Python CLI/Backend.

## Overview

BIMOS is primarily a **CLI-first** engine, but this frontend exists to offer a premium graphical interface for monitoring and interacting with long-running scientific jobs (like ESMFold structure prediction, Vina molecular docking, and GROMACS molecular dynamics).

## Architecture

* **Framework:** React + TypeScript + Vite.
* **Styling:** Vanilla CSS (for maximum flexibility and a rich, glassmorphic aesthetic).
* **Communication:** Standard `fetch` calls to the FastAPI backend running on `http://127.0.0.1:8000`.

## Quick Start

1. **Start the Backend:**
   Ensure the BIMOS backend is running in GUI mode:
   ```bash
   cd ../backend
   python main.py gui
   ```
   *Note: This automatically starts the backend API on port 8000.*

2. **Run the Frontend (Development):**
   Open a new terminal and navigate to this folder:
   ```bash
   cd ../frontend
   bun install  # or npm install
   bun run dev  # or npm run dev
   ```

3. **Production Build:**
   ```bash
   bun run build
   ```

## Development Guide

### Folder Structure
* `src/main.tsx`: React entry point.
* `src/App.tsx`: Main dashboard component containing the UI layout.
* `src/index.css`: Global design tokens, color palettes, and micro-animations.

### Modifying the API connection
By default, the frontend expects the backend at `http://localhost:8000`. If you deploy the backend remotely or change the port via `.env`, update the `API_BASE` constant in `src/App.tsx`.

### Design System
The UI utilizes a dark-mode first, glassmorphism aesthetic. All tokens (colors, fonts, borders) are defined in `src/index.css` under `:root`. To maintain the premium feel, stick to these variables when adding new components.
