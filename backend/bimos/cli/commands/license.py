import rich_click as click
from pathlib import Path

_LICENSE_FILE = Path.home() / ".bimos" / "license.lic"


@click.group("key", invoke_without_command=True)
@click.argument("license_key", required=False, default=None)
def key(license_key: str | None) -> None:
    """Manage your BIMOS license.

    Without arguments: show the current license status and machine fingerprint.

    With a key argument: activate a license key directly.

    You can also drop a bimos*.lic file into ~/.bimos/ and run "bimos key"
    to auto-detect and activate it.

    Examples:

        bimos key              # show status

        bimos key <key>        # activate a license key
    """
    from bimos.shared.license import (
        machine_fingerprint,
        validate_key,
        _read_obfuscated,
        _store_obfuscated,
    )

    if license_key is not None:
        valid, msg = validate_key(license_key)
        if not valid:
            click.echo(f"ERROR: {msg}")
            return
        _store_obfuscated(license_key)
        click.echo("License activated successfully.")
        click.echo(msg)
        return

    # Auto-detect: rename bimos*.lic -> license.lic
    bimos_dir = Path.home() / ".bimos"
    for f in bimos_dir.glob("bimos*.lic"):
        if f.name != "license.lic":
            dst = bimos_dir / "license.lic"
            if dst.exists():
                dst.unlink()
            f.rename(dst)
            click.echo(f"Detected: {f.name} -> license.lic")

    fp = machine_fingerprint()
    stored = _read_obfuscated()

    click.echo("=== BIMOS License ===")

    if stored:
        valid, msg = validate_key(stored)
        if valid:
            parts = stored.split("|")
            lic_type = parts[1]
            click.echo(f"Status:    ACTIVE")
            if lic_type == "PERMANENT":
                click.echo(f"Type:      PERMANENT")
            else:
                click.echo(f"Expires:   {lic_type}")
        else:
            click.echo(f"Status:    INVALID ({msg})")
    else:
        click.echo(f"Status:    UNLICENSED")

    click.echo(f"Machine:   {fp}")

    if not stored or not valid:
        click.echo("")
        click.echo("To activate:")
        click.echo("  Option 1: Drop the .lic file into ~/.bimos/ and run 'bimos key'")
        click.echo("  Option 2: bimos key <license_key>")
