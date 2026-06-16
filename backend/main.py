"""
BIMOS entry point.
"""

import sys


def main() -> None:
    if len(sys.argv) == 2 and sys.argv[1] == "BIMOS_GUI":
        sys.argv = [sys.argv[0], "-g"]
    from bimos.cli.main import cli
    cli()
    import gc
    gc.collect()


if __name__ == "__main__":
    main()
