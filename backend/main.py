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
    # If the application is launched as a desktop shortcut with BIMOS_GUI, start the GUI.
    # Otherwise, let click handle the arguments (showing help on no args).
    if len(sys.argv) == 2 and sys.argv[1] == "BIMOS_GUI":
        sys.argv = [sys.argv[0], "-g"]

    cli()


if __name__ == "__main__":
    main()
