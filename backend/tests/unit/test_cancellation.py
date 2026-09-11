import time
from pathlib import Path
from subprocess import TimeoutExpired
from threading import Thread
from unittest.mock import MagicMock, patch

from bimos.infrastructure import cancellation
from bimos.infrastructure.container import _CANCELED_RC, _wait_for
from bimos.infrastructure.job_store import FileJobStore, JobStatus


def test_event_lifecycle() -> None:
    job_id = "cancel-test-1"
    ev = cancellation.register(job_id)
    assert cancellation.event_for(job_id) is ev
    assert not cancellation.is_canceled(job_id)

    cancellation.request(job_id)
    assert ev.is_set()
    assert cancellation.is_canceled(job_id)

    cancellation.unregister(job_id)
    assert cancellation.event_for(job_id) is None
    assert not cancellation.is_canceled(job_id)


def test_request_unregistered_is_noop() -> None:
    cancellation.request("never-registered")  # should not raise


def test_current_is_canceled_reflects_context_var() -> None:
    job_id = "cancel-test-2"
    ev = cancellation.register(job_id)
    cancellation.current_cancel_event.set(ev)
    assert not cancellation.current_is_canceled()

    cancellation.request(job_id)
    assert cancellation.current_is_canceled()

    cancellation.current_cancel_event.set(None)
    cancellation.unregister(job_id)


def test_wait_for_returns_canceled_rc(tmp_path: Path) -> None:
    job_id = "cancel-test-3"
    cancellation.register(job_id)

    proc_mock = MagicMock()
    proc_mock.wait.side_effect = TimeoutExpired("sleep 999", 999)
    cancellation.request(job_id)

    rc = _wait_for(proc_mock, timeout=600, job_id=job_id)
    assert rc == _CANCELED_RC
    proc_mock.kill.assert_called_once()

    cancellation.unregister(job_id)


def test_wait_for_cancel_honored_after_event(tmp_path: Path) -> None:
    job_id = "cancel-test-4"
    ev = cancellation.register(job_id)

    proc_mock = MagicMock()
    proc_mock.wait.side_effect = TimeoutExpired("sleep 999", 999)

    def _trigger_after_delay():
        time.sleep(0.05)
        ev.set()

    Thread(target=_trigger_after_delay, daemon=True).start()

    rc = _wait_for(proc_mock, timeout=600, job_id=job_id)
    assert rc == _CANCELED_RC
    proc_mock.kill.assert_called_once()

    cancellation.unregister(job_id)


def test_wait_for_returns_exit_code(tmp_path: Path) -> None:
    proc_mock = MagicMock()
    proc_mock.wait.return_value = 0
    rc = _wait_for(proc_mock, timeout=600, job_id="")
    assert rc == 0


def test_dispatch_job_cancel_before_start(tmp_path: Path) -> None:
    from bimos.api import utils as api_utils

    store = FileJobStore()
    store.jobs_dir = tmp_path / ".jobs"
    store.jobs_dir.mkdir(parents=True, exist_ok=True)

    job = store.create(kind="dock", output_dir=str(tmp_path))
    store.cancel(job.id)

    called = []

    with patch.object(api_utils, "store", store):
        api_utils.dispatch_job(lambda **kw: called.append(True), job.id)
        time.sleep(0.2)

    assert called == []
    assert store.get(job.id).status == JobStatus.CANCELED


def test_dispatch_job_does_not_overwrite_canceled(tmp_path: Path) -> None:
    from bimos.api import utils as api_utils

    store = FileJobStore()
    store.jobs_dir = tmp_path / ".jobs"
    store.jobs_dir.mkdir(parents=True, exist_ok=True)

    job = store.create(kind="dock", output_dir=str(tmp_path))

    def _slow_fn(**kwargs) -> dict:  # type: ignore[no-untyped-def]
        time.sleep(0.15)
        return {"status": "completed"}

    with patch.object(api_utils, "store", store):
        api_utils.dispatch_job(_slow_fn, job.id)
        time.sleep(0.05)
        store.cancel(job.id)
        time.sleep(0.3)

    # The worker finished after cancel; it must NOT flip CANCELED -> COMPLETED.
    assert store.get(job.id).status == JobStatus.CANCELED


def test_cancel_clears_registered_event(tmp_path: Path) -> None:
    store = FileJobStore()
    store.jobs_dir = tmp_path / ".jobs"
    store.jobs_dir.mkdir(parents=True, exist_ok=True)

    job = store.create(kind="dock")
    cancellation.register(job.id)
    store.cancel(job.id)
    assert cancellation.is_canceled(job.id)

    store.delete(job.id)
    assert not cancellation.is_canceled(job.id)
