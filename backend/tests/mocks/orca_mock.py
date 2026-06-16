import tempfile
from pathlib import Path
from typing import Optional


class OrcaMock:
    def __init__(self):
        self.inputs_written: list[Path] = []
        self.output_text: str = ""
        self.return_code: int = 0

    def run_orca(
        self,
        inp_path: Path,
        out_path: Optional[Path] = None,
        cwd: Optional[Path] = None,
    ) -> int:
        self.inputs_written.append(inp_path)
        if out_path is None:
            out_path = inp_path.with_suffix(".out")
        if cwd:
            out_path = cwd / out_path.name
        out_path.write_text(
            self.output_text
            or self._default_output(inp_path.stem)
        )
        return self.return_code

    def run_gaussian(
        self,
        gjf_path: Path,
        log_path: Optional[Path] = None,
        cwd: Optional[Path] = None,
    ) -> int:
        self.inputs_written.append(gjf_path)
        if log_path is None:
            log_path = gjf_path.with_suffix(".log")
        if cwd:
            log_path = cwd / log_path.name
        log_path.write_text(
            self.output_text
            or self._default_gaussian_output(gjf_path.stem)
        )
        return self.return_code

    def _default_output(self, name: str) -> str:
        return f"""
ORCA TERMINATED NORMALLY
HIRSHFELD ANALYSIS
  1 C   0.1234
  2 C   0.0567
  3 H  -0.0123
  4 H  -0.0456
  5 O  -0.1234
TOTAL CHARGE: 0.0000
        """.strip()

    def _default_gaussian_output(self, name: str) -> str:
        return f"""
Normal termination of Gaussian
Hirshfeld charges, spin densities
  1    C    0.1234
  2    C    0.0567
  3    H   -0.0123
  4    H   -0.0456
  5    O   -0.1234
 Tot   0.0000
        """.strip()

    def set_output(self, text: str) -> None:
        self.output_text = text

    def set_return_code(self, code: int) -> None:
        self.return_code = code

    def reset(self) -> None:
        self.inputs_written.clear()
        self.output_text = ""
        self.return_code = 0
