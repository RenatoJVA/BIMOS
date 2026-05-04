"""
BIMOS entry point.

Usage:
  python main.py [CLI COMMAND]    — Default CLI mode
  python main.py BIMOS_GUI        — Start API server + open browser
  bimos [CLI COMMAND]             — After installation via uv/pip
"""

import sys
from bimos.cli.main import cli


def main() -> None:
    # Special keyword or no arguments to directly launch GUI mode
    if len(sys.argv) == 1:
        sys.argv = [sys.argv[0], "gui"]
    elif len(sys.argv) == 2 and sys.argv[1] == "BIMOS_GUI":
        sys.argv = [sys.argv[0], "gui"]

    cli()


if __name__ == "__main__":
    main()
