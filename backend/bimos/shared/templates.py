"""Load and render text templates from the package tree."""

from pathlib import Path
from string import Template


def render_template(template_path: Path, **values: str | int | float) -> str:
    """Render a template file using safe ``$placeholder`` substitution."""
    text = template_path.read_text(encoding="utf-8")
    return Template(text).safe_substitute(
        {key: str(val) for key, val in values.items()}
    )
