import csv
import io
import json
import os
import sys
import threading
from typing import Any, Callable

import click


_output_format: str = "text"


def set_output_format(fmt: str) -> None:
    global _output_format
    _output_format = fmt


def get_output_format() -> str:
    return _output_format


def output_result(result: dict[str, Any]) -> None:
    """Print *result* using the output format configured via ``set_output_format``.

    Formats:
        text — print *label* and a few key/value lines (caller must handle).
        json — dump the whole dict as JSON.
        csv  — dump the flattened dict as CSV header + row.
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

        row = _flatten(result)
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(list(row.keys()))
        w.writerow(list(row.values()))
        click.echo(buf.getvalue().strip())


def daemonize(target: Callable[[], None]) -> None:
    """Desvincula del terminal ejecutando *target* en background.

    En POSIX (Linux/macOS): doble fork clásico + setsid
    (comportamiento idéntico al código actual inline).

    En Windows: ejecuta *target* en un hilo daemon (no hay fork en Windows).
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
        with open(os.devnull, "r") as f:
            os.dup2(f.fileno(), sys.stdin.fileno())
        with open(os.devnull, "a+") as f:
            os.dup2(f.fileno(), sys.stdout.fileno())
            os.dup2(f.fileno(), sys.stderr.fileno())
        target()
