#!/usr/bin/env python3
"""
Integration test: runs real BIMOS pipelines on test PDBs with --max and ps-level MD.
Works cross-platform: installed binary, pip-installed module, or source tree.
"""

import os, sys, time, shutil, subprocess, signal, textwrap, threading
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TEST = ROOT / "test"
LOGS = TEST / "logs"

OVERALL = {"pass": 0, "fail": 0, "skip": 0}

# ── CLI detection (cross-platform) ─────────────────────────────────────────

BACKEND = ROOT / "backend"

def _detect_cli():
    """Return (cmd_list, env_patches) or raise SystemExit if not found.
    
    Resolution order:
      1. Source tree (backend/bimos/) — has scripts/ needed by containers
      2. python -m bimos (pip install with __main__.py)
      3. python -m bimos.cli.main (pip install without __main__.py)
      4. bimos binary on PATH (.deb, fallback — may lack scripts/)
    """
    # Priority 1: source tree (has scripts/ for container mounts)
    if (BACKEND / "bimos").exists():
        env = os.environ.copy()
        env["PYTHONPATH"] = str(BACKEND)
        try:
            r = subprocess.run(
                [sys.executable, "-m", "bimos.cli.main", "--help"],
                capture_output=True, text=True, timeout=15, env=env,
            )
            if r.returncode == 0:
                print("  [INFO] Using source tree (backend/bimos/)")
                return [sys.executable, "-m", "bimos.cli.main"], {"PYTHONPATH": str(BACKEND)}
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass

    # Priority 2: try python -m bimos (pip install with __main__.py)
    try:
        r = subprocess.run(
            [sys.executable, "-m", "bimos", "--help"],
            capture_output=True, text=True, timeout=15,
        )
        if r.returncode == 0:
            print("  [INFO] Using python -m bimos")
            return [sys.executable, "-m", "bimos"], {}
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    # Priority 3: python -m bimos.cli.main (pip install without __main__.py)
    try:
        r = subprocess.run(
            [sys.executable, "-m", "bimos.cli.main", "--help"],
            capture_output=True, text=True, timeout=15,
        )
        if r.returncode == 0:
            print("  [INFO] Using python -m bimos.cli.main (pip install)")
            return [sys.executable, "-m", "bimos.cli.main"], {}
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    # Priority 4: installed bimos binary (.deb fallback)
    bimos_bin = shutil.which("bimos")
    if bimos_bin:
        print(f"  [INFO] Using installed binary: {bimos_bin}")
        return [bimos_bin], {}

    print("  [FATAL] BIMOS CLI not found. Install it or run from the backend/ tree.")
    sys.exit(1)


CLI, ENV_PATCHES = _detect_cli()

ENV = os.environ.copy()
ENV.update(ENV_PATCHES)
ENV["BIMOS_USE_GPU"] = "false"

# ── Pre-flight helpers ─────────────────────────────────────────────────────

def _container_image() -> str:
    return os.environ.get("BIMOS_IMAGE", "localhost/bimos/global:latest")

def _container_runtime() -> str:
    for exe in ("podman", "docker"):
        if shutil.which(exe):
            return exe
    return ""

def _check_container_image() -> bool:
    runtime = _container_runtime()
    if not runtime:
        print("  [SKIP] No container runtime (podman/docker) found.")
        return False
    return subprocess.run(
        [runtime, "image", "exists", _container_image()],
        capture_output=True, text=True,
    ).returncode == 0

# ── Config injection ──────────────────────────────────────────────────────

BIMOS_BASE = Path(os.environ.get("BIMOS_BASE_PATH", Path.home() / ".bimos")).resolve()
MD_YAML = BIMOS_BASE / "config" / "md.yaml"
BOLTZ_YAML = BIMOS_BASE / "config" / "boltz.yaml"
MD_BACKUP = MD_YAML.with_suffix(".yaml.bak")
BOLTZ_BACKUP = BOLTZ_YAML.with_suffix(".yaml.bak2")

PS_CONFIG = """
simulation:
  sdm_steps_holo: 1000
  sdm_steps_apo: 1000
  nvt_npt_steps: 1000
  ion_concentration: "0.154004106"
  box_distance: "1.0"
  max_min_iterations: 5
prep:
  forcefield: oplsaa
  water_model: tip3p
  solvent_gro: spc216.gro
"""

def backup_md():
    if MD_YAML.exists():
        shutil.copy2(MD_YAML, MD_BACKUP)

def restore_md():
    if MD_BACKUP.exists():
        shutil.move(MD_BACKUP, MD_YAML)

def backup_boltz():
    if BOLTZ_YAML.exists():
        shutil.copy2(BOLTZ_YAML, BOLTZ_BACKUP)

def restore_boltz():
    if BOLTZ_BACKUP.exists():
        shutil.move(BOLTZ_BACKUP, BOLTZ_YAML)

def inject_configs():
    MD_YAML.parent.mkdir(parents=True, exist_ok=True)
    MD_YAML.write_text(textwrap.dedent(PS_CONFIG).lstrip())
    print("  [CONFIG] MD tuned to picosecond regime")

def create_fastas():
    (TEST / "PREDICT").mkdir(parents=True, exist_ok=True)
    ubi = TEST / "PREDICT" / "ubiquitin.fasta"
    ubi.write_text(">ubiquitin Human 76-residue ubiquitin fusion\n"
                   "MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG\n")
    lys = TEST / "PREDICT" / "lysozyme.fasta"
    lys.write_text(">lysozyme Hen egg white lysozyme (1AKI) 129 residues\n"
                   "KVFGRCELAAAMKRHGLDNYRGYSLGNWVCAAKFESNFNTQATNRNTDGSTDYGILQINSRWWCNDGRTPGSRNLCNIPCSALLSSDITASVNCAKKIVSDGNGMNAWVAWRNRCKGTDVQAWIRGCRL\n")
    print("  [DATA] FASTA files created in test/PREDICT/")

# ── Pipeline runner ───────────────────────────────────────────────────────

ERROR_MARKERS = ("Error:", "Error while", "Traceback", "ModuleNotFoundError", "exited with code")

def _check_error(log_text: str) -> str | None:
    for line in log_text.splitlines():
        for m in ERROR_MARKERS:
            if m in line:
                if "exit 0" in line:
                    continue
                return line.strip()
    return None

def _tail(path: Path, n: int = 15) -> str:
    try:
        lines = path.read_text().splitlines()
        return "\n".join(lines[-n:])
    except Exception:
        return "(unreadable)"

def _reader_thread(stream, log_file):
    with open(log_file, "a") as f:
        for line in iter(stream.readline, ""):
            f.write(line)
        stream.close()

def run_pipeline(label, cli_args, *, clean_output=False, timeout=120):
    cmd = CLI + ["--max"] + list(cli_args)
    LOGS.mkdir(parents=True, exist_ok=True)
    safe = (
        label.lower()
        .replace(" ", "_")
        .replace("(", "")
        .replace(")", "")
        .replace("+", "_")
        .replace(".", "_")
    )
    log_file = LOGS / f"{safe}.log"

    if clean_output:
        for i, arg in enumerate(cli_args):
            if arg in ("-o", "--output") and i + 1 < len(cli_args):
                out_dir = Path(cli_args[i + 1])
                if out_dir.exists():
                    shutil.rmtree(out_dir)
                    print(f"  [CLEAN] Removed old output: {out_dir}")

    print(f"\n{'=' * 70}")
    print(f"  >>> {label}")
    print(f"  CMD: {' '.join(str(a) for a in cmd)}")
    print(f"  TIMEOUT: {timeout}s")
    print(f"{'=' * 70}")

    start = time.monotonic()
    with open(log_file, "w") as f:
        f.write(f"CMD: {' '.join(str(a) for a in cmd)}\n")
        f.write(f"START: {datetime.now()}\n\n")

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=ENV,
        preexec_fn=lambda: signal.signal(signal.SIGPIPE, signal.SIG_DFL),
    )

    reader = threading.Thread(
        target=_reader_thread, args=(proc.stdout, log_file), daemon=True
    )
    reader.start()

    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        elapsed = timedelta(seconds=time.monotonic() - start)
        timed_out = True
    else:
        elapsed = timedelta(seconds=time.monotonic() - start)
        timed_out = False
    finally:
        reader.join(timeout=5)

    log_text = log_file.read_text()
    reason = _check_error(log_text)

    if timed_out:
        OVERALL["fail"] += 1
        print(f"\n  [FAIL] {label}  ({elapsed})")
        print(f"         Reason: TIMEOUT after {timeout}s")
        tail = _tail(log_file, 12)
        if tail:
            print(f"  {'─' * 50}")
            for t in tail.splitlines():
                print(f"  | {t}")
            print(f"  {'─' * 50}")
        print(f"         Full log: {log_file}")
        return False

    if reason is None:
        OVERALL["pass"] += 1
        print(f"\n  [PASS] {label}  ({elapsed})")
    else:
        OVERALL["fail"] += 1
        print(f"\n  [FAIL] {label}  ({elapsed})")
        print(f"         Reason: {reason}")
        tail = _tail(log_file, 12)
        if tail:
            print(f"  {'─' * 50}")
            for t in tail.splitlines():
                print(f"  | {t}")
            print(f"  {'─' * 50}")
        print(f"         Full log: {log_file}")

    return reason is None

# ── Summary ───────────────────────────────────────────────────────────────

def summary():
    total = OVERALL["pass"] + OVERALL["fail"] + OVERALL["skip"]
    print(f"\n{'=' * 70}")
    print(f"  TEST SUMMARY")
    print(f"  {'=' * 30}")
    print(f"  Passed:  {OVERALL['pass']}")
    print(f"  Failed:  {OVERALL['fail']}")
    print(f"  Skipped: {OVERALL['skip']}")
    print(f"  Total:   {total}")
    print(f"  Logs:    {LOGS}")
    print(f"{'=' * 70}")
    return OVERALL["fail"] == 0

# ── Pre-flight ────────────────────────────────────────────────────────────

def preflight() -> bool:
    ok = True
    img = _container_image()
    if _check_container_image():
        print(f"  [INFO] Container image '{img}' available")
    else:
        print(f"  [WARN] Container image '{img}' not found (run setup first)")
        ok = False

    runtime = _container_runtime()
    if runtime:
        print(f"  [INFO] Container runtime: {runtime}")
    else:
        print("  [WARN] No container runtime (podman/docker) found")
        ok = False

    return ok

# ── Main ──────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("  BIMOS Integration Test")
    print(f"  Started: {datetime.now()}")
    print(f"  CWD:     {ROOT}")
    print("=" * 70)

    if not preflight():
        print("\n  Pre-flight check failed. Aborting.")
        sys.exit(1)

    backup_md()
    backup_boltz()
    inject_configs()
    create_fastas()

    try:
        run_pipeline("Setup", ["setup", "--config-only"], timeout=60)

        run_pipeline(
            "APO MD (1AKI)",
            [
                "workflow",
                "--protein",
                str(TEST / "APO" / "1AKI.pdb"),
                "-o",
                str(TEST / "APO" / "output"),
            ],
            clean_output=True,
            timeout=300,
        )

        run_pipeline(
            "HOLO MD (3HTB + JZ4)",
            [
                "workflow",
                "--protein",
                str(TEST / "HOLO" / "3HTB.pdb"),
                "--ligand-gro",
                str(TEST / "HOLO" / "JZ4.gro"),
                "--ligand-itp",
                str(TEST / "HOLO" / "JZ4.itp"),
                "-o",
                str(TEST / "HOLO" / "output"),
            ],
            clean_output=True,
            timeout=300,
        )

        run_pipeline(
            "Docking (3HTB + JZ4 SDF)",
            [
                "dock",
                str(TEST / "DOCKING" / "3HTB.pdb"),
                str(TEST / "DOCKING" / "JZ4.sdf"),
                "-o",
                str(TEST / "DOCKING" / "output"),
            ],
            clean_output=True,
            timeout=120,
        )

        # run_pipeline(
        #     "Predict ESMFold (ubiquitin)",
        #     [
        #         "predict",
        #         str(TEST / "PREDICT" / "ubiquitin.fasta"),
        #         "-o",
        #         str(TEST / "PREDICT" / "esm_output"),
        #     ],
        #     clean_output=True,
        #     timeout=600,
        # )

        run_pipeline(
            "Predict Boltz (lysozyme)",
            [
                "predict-boltz",
                str(TEST / "PREDICT" / "lysozyme.yaml"),
                "-o",
                str(TEST / "PREDICT" / "boltz_output"),
            ],
            clean_output=True,
            timeout=600,
        )

        run_pipeline(
            "QM ORCA (JZ4)",
            [
                "qm-orca",
                str(TEST / "QM" / "orca"),
            ],
            timeout=120,
        )

        run_pipeline(
            "QM G16 (JZ4)",
            [
                "qm-g16",
                str(TEST / "QM" / "g16"),
            ],
            timeout=120,
        )

    except KeyboardInterrupt:
        print("\n\nInterrupted.")
    except BaseException as exc:
        print(f"\n\nFatal: {exc}")
        raise
    finally:
        restore_md()
        restore_boltz()

    all_ok = summary()
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
