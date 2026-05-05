import sys
from pathlib import Path
import rich_click as click
from bimos.config.settings import settings

def _print(msg: str) -> None:
    click.echo(msg)

@click.command("setup")
@click.option("--force", is_flag=True, help="Force rebuild even if image exists.")
def setup(force: bool) -> None:
    """Build the bimos/global:latest container image."""
    from bimos.infrastructure.container import build_image, image_exists

    tag = settings.bimos_image
    # Note: path relative to this file will change since it's now in bimos/cli/commands/setup.py
    # We need to go up three levels: bimos/cli/commands -> bimos/cli -> bimos -> root -> dockers
    dockerfile = Path(__file__).parent.parent.parent.parent / "dockers" / "Dockerfile.bimos"

    if not dockerfile.exists():
        click.echo(f"Error: Dockerfile not found at {dockerfile}", err=True)
        sys.exit(1)

    if not force and image_exists(tag):
        click.echo(f"Image {tag} already exists. Use --force to rebuild.")
        return

    context = str(dockerfile.parent.parent)
    click.echo(f"Building {tag}  (this may take 20-40 minutes on first run)...")
    rc = build_image(
        dockerfile=str(dockerfile),
        tag=tag,
        context=context,
        on_output=_print,
    )
    if rc != 0:
        click.echo(f"Build failed with exit code {rc}.", err=True)
        sys.exit(rc)
    click.echo(f"Image {tag} built successfully.")
