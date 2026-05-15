"""
Base contract for computational pipelines.

Subclasses implement a single ``run`` entry point and declare their default
workspace subdirectory via ``workspace_subdir``.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable, Optional

from bimos.config.settings import settings

logger = logging.getLogger("bimos.pipeline")


class Pipeline(ABC):
    """Abstract base for docking, MD, prediction, and QM pipelines."""

    workspace_subdir: str = "jobs"

    def __init__(
        self,
        output_dir: str | Path | None = None,
        on_output: Callable[[str], None] | None = None,
    ) -> None:
        self.on_output = on_output
        self.output_dir = Path(output_dir) if output_dir else self._default_output_dir()
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _default_output_dir(self) -> Path:
        return settings.workspace_path / self.workspace_subdir

    def log(self, msg: str, level: int = logging.INFO) -> None:
        logger.log(level, msg)
        if self.on_output:
            self.on_output(msg)

    @abstractmethod
    def run(self, **kwargs: Any) -> dict[str, Any]:
        """Execute the pipeline and return a result summary."""
