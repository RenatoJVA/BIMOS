"""
Container runner for BIMOS.

Uses subprocess to call Podman or Docker, streaming output line by line.
Works with rootless Podman (no daemon socket required).
"""

import subprocess
import logging
import os
from pathlib import Path
from typing import Callable, Optional

from bimos.config.settings import settings

logger = logging.getLogger("bimos.container")


def _detect_runtime() -> str:
    return settings.container_runtime()


def _get_proc_env() -> dict[str, str]:
    """Get process environment with SSH remote host if configured."""
    proc_env = os.environ.copy()
    if settings.ssh_host:
        user = f"{settings.ssh_user}@" if settings.ssh_user else ""
        uri = f"ssh://{user}{settings.ssh_host}"
        proc_env["DOCKER_HOST"] = uri
        proc_env["CONTAINER_HOST"] = uri
        # Ensure SSH doesn't hang on prompts
        proc_env["SSH_AUTH_SOCK"] = os.environ.get("SSH_AUTH_SOCK", "")
    return proc_env


def run(
    command: list[str],
    image: str = "",
    volumes: Optional[dict[str, str]] = None,
    workdir: str = "/workspace",
    on_output: Optional[Callable[[str], None]] = None,
    env: Optional[dict[str, str]] = None,
    stdin_text: Optional[str] = None,
    timeout: int = 7200,
) -> int:
    """
    Run a command inside a container (or a raw subprocess if image is empty).
    Streams stdout+stderr line by line to on_output if provided.

    Args:
        command: Command list to run (inside container, or raw if image is empty).
        image: Container image name. If empty, runs the command directly.
        volumes: Host-to-container path mappings { host_path: container_path }.
        workdir: Working directory inside the container.
        on_output: Callback called with each output line.
        env: Additional environment variables.
        timeout: Max execution time in seconds.

    Returns:
        Exit code.
    """
    runtime = _detect_runtime()

    if image:
        full_cmd = [runtime, "run", "-i" ,"--rm", "--workdir", workdir]
        
        # Thread limiting (default 1/3 available)
        t = settings.get_threads()
        full_cmd += ["-e", f"OMP_NUM_THREADS={t}", "-e", f"MKL_NUM_THREADS={t}"]

        if settings.use_gpu:
            ld_path = "/lib/x86_64-linux-gnu:/usr/local/nvidia/lib64:/usr/local/cuda/lib64"
            full_cmd += ["-e", f"LD_LIBRARY_PATH={ld_path}"]
            if runtime == "docker":
                full_cmd += ["--gpus", "all"]
            elif runtime == "podman":
                full_cmd += ["--device", "nvidia.com/gpu=all"]

        # Rootless Podman and performance flags
        full_cmd += ["--shm-size=10g"]
        if runtime == "podman":
            full_cmd += ["--userns=keep-id"]

        if volumes:
            for host_path, container_path in volumes.items():
                full_cmd += ["-v", f"{Path(host_path).resolve()}:{container_path}:Z"]

        if env:
            for k, v in env.items():
                full_cmd += ["-e", f"{k}={v}"]

        from bimos.infrastructure.job_store import current_job_id
        job_id = current_job_id.get()
        if job_id:
            full_cmd += ["--label", f"bimos_job_id={job_id}"]

        full_cmd.append(image)
        full_cmd.extend(command)
    else:
        full_cmd = command

    logger.debug("Executing: %s", " ".join(str(c) for c in full_cmd))

    if on_output:
        on_output(f"[CMD] {' '.join(str(c) for c in full_cmd)}")

    # Setup environment for remote execution if configured
    proc_env = _get_proc_env()

    try:
        process = subprocess.Popen(
            full_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE if stdin_text is not None else None,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=proc_env,
        )

        if stdin_text is not None and process.stdin:
            process.stdin.write(stdin_text)
            process.stdin.close()

        if process.stdout:
            for line in process.stdout:
                stripped = line.rstrip()
                if stripped:
                    logger.debug(stripped)
                    if on_output:
                        on_output(stripped)

        rc = process.wait(timeout=timeout)
        from bimos.infrastructure.job_store import current_job_id, store, JobStatus
        job_id = current_job_id.get()
        if job_id:
            job = store.get(job_id)
            if not job or job.status == JobStatus.CANCELED:
                raise RuntimeError(f"Job {job_id} was canceled by user.")
        return rc

    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        msg = f"[BIMOS] Container timed out after {timeout}s"
        logger.error(msg)
        if on_output:
            on_output(msg)
        return -1

    except FileNotFoundError:
        msg = f"[BIMOS] Runtime '{runtime}' not found. Install Podman or Docker."
        logger.error(msg)
        if on_output:
            on_output(msg)
        return -2


def image_exists(image: str) -> bool:
    """Check if a container image is available locally (or on remote host)."""
    runtime = _detect_runtime()
    proc_env = _get_proc_env()
    result = subprocess.run(
        [runtime, "image", "inspect", image],
        capture_output=True,
        env=proc_env,
    )
    return result.returncode == 0


def build_image(dockerfile: str, tag: str, context: str = ".", on_output: Optional[Callable[[str], None]] = None) -> int:
    """Build a container image from a Dockerfile."""
    runtime = _detect_runtime()
    cmd = [runtime, "build", "-t", tag, "-f", dockerfile, context]

    if on_output:
        on_output(f"Building image {tag} with {runtime}...")

    return run(command=cmd, on_output=on_output)
