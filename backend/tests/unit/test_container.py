from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from bimos.infrastructure import container as container_module


def test_run_raw_command(mock_subprocess) -> None:
    rc = container_module.run(
        command=["echo", "hello"],
        image="",
    )
    assert rc == 0


def test_run_with_image(mock_subprocess) -> None:
    rc = container_module.run(
        command=["vina", "--help"],
        image="localhost/bimos/test:latest",
    )
    assert rc == 0


def test_run_with_volumes(mock_subprocess) -> None:
    rc = container_module.run(
        command=["gmx", "--version"],
        image="localhost/bimos/test:latest",
        volumes={"/host/data": "/container/data"},
    )
    assert rc == 0


def test_run_with_on_output_callback(mock_subprocess) -> None:
    lines = []

    def capture(line: str) -> None:
        lines.append(line)

    rc = container_module.run(
        command=["echo", "test"],
        image="",
        on_output=capture,
    )
    assert rc == 0


def test_run_timeout_returns_minus_one(tmp_path: Path) -> None:
    timeout_expired = __import__("subprocess").TimeoutExpired(cmd="test", timeout=1)
    with patch("subprocess.Popen") as mock_popen:
        proc_mock = MagicMock()
        proc_mock.wait.side_effect = [timeout_expired, None]
        proc_mock.stdout = ["line1\n"]
        proc_mock.pid = 12345
        mock_popen.return_value = proc_mock

        with patch("bimos.infrastructure.container._detect_runtime", return_value="podman"):
            rc = container_module.run(
                command=["sleep", "999"],
                image="test:latest",
            )
            assert rc == -1


@patch("bimos.infrastructure.container._detect_runtime", return_value="podman")
def test_image_exists_true(mock_detect) -> None:
    mock_result = MagicMock()
    mock_result.returncode = 0
    with patch("subprocess.run", return_value=mock_result):
        assert container_module.image_exists("localhost/bimos/test:latest") is True


@patch("bimos.infrastructure.container._detect_runtime", return_value="podman")
def test_image_exists_false(mock_detect) -> None:
    mock_result = MagicMock()
    mock_result.returncode = 1
    with patch("subprocess.run", return_value=mock_result):
        assert container_module.image_exists("nonexistent:latest") is False


@patch("bimos.infrastructure.container._detect_runtime", return_value="podman")
def test_build_image(mock_detect, mock_subprocess) -> None:
    rc = container_module.build_image(
        dockerfile="Dockerfile.test",
        tag="test:latest",
        context=".",
    )
    assert rc == 0


@patch("bimos.infrastructure.container._detect_runtime", return_value="podman")
def test_run_with_env_vars(mock_detect, mock_subprocess) -> None:
    rc = container_module.run(
        command=["python3", "script.py"],
        image="test:latest",
        env={"MY_VAR": "my_value"},
    )
    assert rc == 0


@patch("bimos.infrastructure.container._detect_runtime", return_value="podman")
def test_run_with_stdin(mock_detect) -> None:
    with patch("subprocess.Popen") as mock_popen:
        proc_mock = MagicMock()
        proc_mock.stdout = ["output\n"]
        proc_mock.wait.return_value = 0
        proc_mock.pid = 12345
        mock_popen.return_value = proc_mock

        rc = container_module.run(
            command=["gmx", "genion"],
            image="test:latest",
            stdin_text="SOL\n",
        )
        assert rc == 0


@patch("bimos.infrastructure.container._detect_runtime", return_value="podman")
def test_run_file_not_found(mock_detect) -> None:
    with patch("subprocess.Popen", side_effect=FileNotFoundError()):
        rc = container_module.run(
            command=["nonexistent"],
            image="test:latest",
        )
        assert rc == -2


@patch("bimos.infrastructure.container._detect_runtime", return_value="podman")
def test_detect_runtime(mock_detect) -> None:
    runtime = container_module._detect_runtime()
    assert runtime == "podman"


@patch("bimos.infrastructure.container._detect_runtime", return_value="podman")
def test_get_proc_env_no_ssh(mock_detect) -> None:
    env = container_module._get_proc_env()
    assert isinstance(env, dict)


@patch("bimos.infrastructure.container.settings")
def test_get_proc_env_with_ssh(mock_settings) -> None:
    mock_settings.ssh_host = "192.168.1.100"
    mock_settings.ssh_user = "bimos"
    env = container_module._get_proc_env()
    assert "DOCKER_HOST" in env
    assert "ssh://bimos@192.168.1.100" in env["DOCKER_HOST"]

def test_run_raw_command_does_not_require_container_runtime() -> None:
    """A raw command (image="") must not call podman/docker detection."""
    with patch(
        "bimos.infrastructure.container._detect_runtime",
        side_effect=AssertionError("runtime detection must be skipped"),
    ):
        with patch("subprocess.Popen") as mock_popen:
            proc_mock = MagicMock()
            proc_mock.stdout = []
            proc_mock.wait.return_value = 0
            proc_mock.pid = 12345
            mock_popen.return_value = proc_mock

            rc = container_module.run(command=["echo", "hello"])

    assert rc == 0


def test_container_library_path_per_architecture() -> None:
    x86 = container_module._container_library_path("x86_64")
    arm = container_module._container_library_path("aarch64")

    assert "/lib/x86_64-linux-gnu" in x86
    assert "/lib/aarch64-linux-gnu" in arm
    assert "/usr/local/cuda/lib64" in x86
    assert "/usr/local/cuda/lib64" in arm


@patch("bimos.infrastructure.container._detect_runtime", return_value="podman")
def test_read_only_mount_uses_ro_flag(mock_detect) -> None:
    with patch("subprocess.Popen") as mock_popen:
        proc_mock = MagicMock()
        proc_mock.stdout = []
        proc_mock.wait.return_value = 0
        proc_mock.pid = 12345
        mock_popen.return_value = proc_mock

        rc = container_module.run(
            command=["python3", "/scripts/tool.py"],
            image="test:latest",
            volumes={"/host/work": "/work", "/host/scripts": "/scripts"},
            read_only={"/scripts"},
        )

    assert rc == 0
    cmd = mock_popen.call_args.args[0]
    mounts = [cmd[i + 1] for i, arg in enumerate(cmd) if arg == "-v"]
    assert any(mount.endswith("/scripts:ro,Z") for mount in mounts)
    assert any(mount.endswith("/work:Z") for mount in mounts)


@patch("bimos.infrastructure.container._detect_runtime", return_value="podman")
def test_run_raises_explicit_timeout_error(mock_detect) -> None:
    with patch("bimos.infrastructure.container._wait_for", return_value=container_module.TIMED_OUT_RC):
        with patch("subprocess.Popen") as mock_popen:
            proc_mock = MagicMock()
            proc_mock.stdout = []
            proc_mock.pid = 12345
            mock_popen.return_value = proc_mock

            with pytest.raises(container_module.ContainerTimeoutError, match="timed out"):
                container_module.run(command=["sleep", "999"], image="test:latest", raise_on_error=True)


@patch("bimos.infrastructure.container._detect_runtime", return_value="podman")
def test_run_raises_explicit_cancel_error(mock_detect) -> None:
    with patch("bimos.infrastructure.container._wait_for", return_value=container_module.CANCELED_RC):
        with patch("subprocess.Popen") as mock_popen:
            proc_mock = MagicMock()
            proc_mock.stdout = []
            proc_mock.pid = 12345
            mock_popen.return_value = proc_mock

            with pytest.raises(container_module.ContainerCanceledError, match="canceled"):
                container_module.run(command=["sleep", "999"], image="test:latest", raise_on_error=True)


@patch("bimos.infrastructure.container._detect_runtime", return_value="podman")
def test_run_raises_explicit_runtime_error(mock_detect) -> None:
    with patch("subprocess.Popen", side_effect=FileNotFoundError()):
        with pytest.raises(container_module.ContainerRuntimeNotFoundError, match="not found"):
            container_module.run(command=["gmx"], image="test:latest", raise_on_error=True)
