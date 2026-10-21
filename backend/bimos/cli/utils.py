import csv
import io
import json
import os
import sys
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import click

_output_format: str = "text"


def set_output_format(fmt: str) -> None:
    global _output_format
    _output_format = fmt


def get_output_format() -> str:
    return _output_format


def output_result(result: dict[str, Any] | list[dict[str, Any]]) -> None:
    """Print *result* using the output format configured via ``set_output_format``.

    Formats:
        text — print *label* and a few key/value lines (caller must handle).
        json — dump the whole dict (or list) as JSON.
        csv  — dump the flattened dict as CSV header + row (one row per item for lists).
    """
    if _output_format == "json":
        click.echo(json.dumps(result, indent=2, default=str))
    elif _output_format == "csv":
        def _flatten(d: dict, prefix: str = "") -> dict:
            flat: dict = {}
            for k, v in d.items():
                key = f"{prefix}_{k}" if prefix else k
                if isinstance(v, dict):
                    flat.update(_flatten(v, key))
                elif isinstance(v, list):
                    flat[key] = "; ".join(str(x) for x in v)
                else:
                    flat[key] = v
            return flat

        rows = [ _flatten(item) for item in result ] if isinstance(result, list) else [_flatten(result)]
        if not rows:
            return
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(list(rows[0].keys()))
        for row in rows:
            w.writerow(list(row.values()))
        click.echo(buf.getvalue().strip())


def expand_path(path: str | None) -> str | None:
    """Expand ``~`` and return *path* unchanged otherwise (None-safe)."""
    return os.path.expanduser(path) if path else path


def force_option(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Add the shared ``--force`` flag that bypasses the hardware guardrail.

    Used by every command that launches a pipeline, so the flag shows up in
    each ``--help`` instead of only in the global options.
    """
    return click.option(
        "--force",
        is_flag=True,
        help="Run even when the hardware check reports red (not viable). See 'bimos doctor'.",
    )(fn)


def validate_output(output: str | None, inputs: list[str | None]) -> str | None:
    """Validate an ``--output`` directory option.

    Expands ``~``, rejects existing non-directories, and rejects outputs
    nested inside one of the input paths (which would contaminate inputs).
    Returns the expanded path (or None) for the pipeline.
    """
    if not output:
        return None
    expanded = Path(os.path.expanduser(output))
    if expanded.exists() and not expanded.is_dir():
        raise click.ClickException(f"Output '{output}' exists and is not a directory.")
    resolved = expanded.resolve()
    for raw in inputs:
        if not raw:
            continue
        anchor = Path(os.path.expanduser(raw)).resolve()
        base = anchor if anchor.is_dir() else anchor.parent
        if resolved == anchor or base in resolved.parents:
            raise click.ClickException(
                f"Output '{output}' must not be inside input '{raw}'."
            )
    return str(expanded)


def run_tracked(
    kind: str,
    meta: dict[str, Any],
    output: str | None,
    background: bool,
    gui: bool,
    gui_message: str,
    run_fn: Callable[[Callable[[str], None]], dict[str, Any] | list[dict[str, Any]]],
    summarize: Callable[[dict[str, Any] | list[dict[str, Any]]], None],
) -> None:
    """Run a pipeline as a tracked job with shared CLI lifecycle.

    Creates the job, streams logs via *run_fn(emit)*, and handles the
    foreground/background/GUI branches identically for every command.
    """
    from bimos.infrastructure.job_store import store

    job = store.create(kind=kind, meta=meta, output_dir=output or "")
    click.echo(f"Job ID: {job.id}")

    def _run() -> None:
        store.start(job.id)

        def emit(line: str) -> None:
            store.log(job.id, line)
            if not background and not gui:
                click.echo(line)

        try:
            result = run_fn(emit)
            store.complete(job.id, exit_code=0)
            if not background and not gui:
                if get_output_format() != "text":
                    output_result(result)
                else:
                    summarize(result)
        except Exception as exc:
            store.fail(job.id, str(exc))
            click.echo(f"Error: {exc}", err=True)

    if gui:
        threading.Thread(target=_run, daemon=True).start()
        from bimos.api.server import start_server

        click.echo(gui_message)
        start_server(desktop=True)
    elif background:
        click.echo("Running in background. Use 'bimos jobs' to check status.")
        daemonize(_run)
    else:
        _run()


def daemonize(target: Callable[[], None]) -> None:
    """Detach from the terminal by running *target* in the background.

    On POSIX (Linux/macOS): classic double fork + setsid
    (behavior identical to the current inline code).

    On Windows: run *target* in a daemon thread (no fork on Windows).
    """
    if os.name == "nt":
        t = threading.Thread(target=target, daemon=True)
        t.start()
    else:
        pid = os.fork()
        if pid > 0:
            sys.exit(0)
        os.setsid()
        if os.fork() > 0:
            sys.exit(0)
        with open(os.devnull) as f:
            os.dup2(f.fileno(), sys.stdin.fileno())
        with open(os.devnull, "a+") as f:
            os.dup2(f.fileno(), sys.stdout.fileno())
            os.dup2(f.fileno(), sys.stderr.fileno())
        target()
