"""
BIMOS entry point.
"""

import sys


def _is_frozen() -> bool:
    """True when running from a Nuitka/PyInstaller standalone binary."""
    # Nuitka injects ``__compiled__`` into every compiled module; PyInstaller
    # (and some Nuitka modes) set ``sys.frozen``.
    return "__compiled__" in globals() or bool(getattr(sys, "frozen", False))


def main() -> None:
    if len(sys.argv) == 2 and sys.argv[1] == "BIMOS_GUI":
        sys.argv = [sys.argv[0], "-g"]
    elif _is_frozen() and sys.platform == "darwin":
        # Finder may pass a legacy ``-psn_...`` argument. Anything else means
        # the user really wants the CLI.
        args = [arg for arg in sys.argv[1:] if not arg.startswith("-psn_")]
        if not args:
            sys.argv = [sys.argv[0], "-g"]
    from bimos.cli.main import cli
    cli()
    import gc
    gc.collect()



if __name__ == "__main__":
    main()
