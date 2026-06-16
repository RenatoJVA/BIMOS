from pathlib import Path

import pytest

from bimos.shared.templates import render_template


def test_render_simple_template(tmp_path: Path) -> None:
    tpl = tmp_path / "test.template"
    tpl.write_text("Hello, $name!")
    result = render_template(tpl, name="World")
    assert result == "Hello, World!"


def test_render_multiple_values(tmp_path: Path) -> None:
    tpl = tmp_path / "multi.template"
    tpl.write_text("$a $b $c")
    result = render_template(tpl, a="x", b="y", c="z")
    assert result == "x y z"


def test_render_with_numbers(tmp_path: Path) -> None:
    tpl = tmp_path / "num.template"
    tpl.write_text("Value: $value")
    result = render_template(tpl, value=42)
    assert result == "Value: 42"


def test_render_missing_variable_unchanged(tmp_path: Path) -> None:
    tpl = tmp_path / "missing.template"
    tpl.write_text("Hello, $name! Today is $day.")
    result = render_template(tpl, name="Alice")
    assert "Alice" in result
    assert "$day" in result


def test_render_empty_template(tmp_path: Path) -> None:
    tpl = tmp_path / "empty.template"
    tpl.write_text("")
    result = render_template(tpl)
    assert result == ""
