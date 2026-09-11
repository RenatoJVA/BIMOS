"""
Per-job cancellation signaling.

A ``threading.Event`` is registered per job id so any part of the job's
execution (container.run, QM subprocesses, dispatch worker) can observe that
the user requested cancellation and abort promptly. The active event is
exposed through a ``ContextVar`` (parallel to ``current_job_id``) which is set
in the job's worker thread.
"""

import threading
from contextvars import ContextVar

_cancel_lock = threading.Lock()
_cancel_events: dict[str, threading.Event] = {}

current_cancel_event: ContextVar[threading.Event | None] = ContextVar(
    "current_cancel_event", default=None
)


def register(job_id: str) -> threading.Event:
    """Create (or reuse) a cancellation event for *job_id*."""
    with _cancel_lock:
        return _cancel_events.setdefault(job_id, threading.Event())


def event_for(job_id: str) -> threading.Event | None:
    """Return the event registered for *job_id*, if any."""
    with _cancel_lock:
        return _cancel_events.get(job_id)


def request(job_id: str) -> None:
    """Signal cancellation for *job_id* (no-op if not registered)."""
    ev = event_for(job_id)
    if ev is not None:
        ev.set()


def is_canceled(job_id: str) -> bool:
    """Return True when a cancellation was requested for *job_id*."""
    ev = event_for(job_id)
    return ev is not None and ev.is_set()


def current_is_canceled() -> bool:
    """Return True when the current worker thread's job was canceled."""
    ev = current_cancel_event.get()
    return ev is not None and ev.is_set()


def unregister(job_id: str) -> None:
    """Remove the event for *job_id* (job deleted)."""
    with _cancel_lock:
        _cancel_events.pop(job_id, None)
