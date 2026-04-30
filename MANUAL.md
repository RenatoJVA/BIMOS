# BIMOS User Manual
## Biomolecular Modeling Suite

BIMOS is a high-performance suite for biomolecular modeling, including structure prediction, molecular docking, and MD simulations.

---

## 1. Installation

### 🐧 Linux (Debian/Ubuntu)
BIMOS is distributed as a `.deb` package for easy installation.

1. **Download** the latest `.deb` from the releases page.
2. **Install** using `dpkg` or `apt`:
   ```bash
   sudo apt update
   sudo apt install ./bimos_1.0.0_amd64.deb
   ```
3. **Dependencies**: BIMOS requires Docker for containerized workflows (GROMACS, ESMFold).
   ```bash
   sudo apt install docker.io
   sudo usermod -aG docker $USER
   ```

### 🪟 Windows
For Windows, BIMOS provides a standalone installer.

1. **Download** `BIMOS_Setup.exe`.
2. **Run the installer** and follow the prompts.
3. **WSL2 Recommendation**: For maximum performance, it is recommended to have WSL2 and Docker Desktop installed.
4. **Environment**: The installer will automatically add `bimos-cli` to your PATH.

### 🍎 macOS
BIMOS supports macOS via a portable binary or Homebrew.

1. **Direct Download**: Download `bimos-macos.zip`, extract, and move `bimos` to `/usr/local/bin`.
2. **Permissions**: You may need to allow the app in "System Settings > Privacy & Security" since it's a CLI tool.
3. **Docker**: Install [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop/) to run simulations.

---

## 2. Quick Start

### Structural Prediction (ESMFold)
Predict the 3D structure of a protein from its sequence:
```bash
bimos-cli predict --fasta protein.fasta --name my_protein
```

### Molecular Docking
Dock a ligand into a protein structure:
```bash
bimos-cli dock protein.pdb ligands.sdf --times 10
```

### Molecular Dynamics (GROMACS)
Run a full MD pipeline (Prep -> Min -> NVT -> NPT -> Production):
```bash
bimos-cli simulate protein.pdb
```

---

## 3. The Dashboard (GUI)

BIMOS includes a real-time monitoring dashboard. To launch it along with any command, use the `--gui` flag:

```bash
bimos-cli dock protein.pdb ligands.sdf --gui
```

### Dashboard Features:
- **Live Job Tracking**: Monitor the status of all active and past jobs.
- **Terminal Simulation**: Click on any job in the dashboard to open a **live console** and see the exact output of the simulation/docking process.
- **Visual Feedback**: Real-time progress badges and error reporting.

---

## 4. Configuration

BIMOS uses a `.env` file or environment variables for configuration.
- `WORKSPACE_PATH`: Where results are stored (Default: `~/bimos_workspace`)
- `ORCA_PATH`: Path to the ORCA binary (required for QM calculations).
- `DOCKER_IMAGE`: The container image used for simulations.

---

## 5. Troubleshooting

- **Docker Permission Denied**: Ensure your user is in the `docker` group.
- **Segment Fault (Nuitka)**: If running the compiled binary, ensure your system has compatible graphics drivers for the GUI (Vulkan/OpenGL).
- **Backend Connection Error**: Ensure the BIMOS engine is running. The dashboard connects to `localhost:8000`.
