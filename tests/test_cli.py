"""CLI-level tests: user-facing format validation and regression coverage for
the public command surface (no plugin subcommands remain, values are
case-insensitive, and both the --format and --output-format spellings work)."""

from pathlib import Path

from typer.testing import CliRunner

from idl2icd.cli import app

runner = CliRunner()


def _project(tmp_path: Path, fail_on: str = "error") -> Path:
    (tmp_path / "x.idl").write_text("@topic\nstruct Foo {\n  long value;\n};\n")
    cfg = tmp_path / "idl2icd.yaml"
    cfg.write_text(
        "project:\n"
        "  name: t\n"
        "  version: 1.0.0\n"
        "sources:\n"
        "  idl: ['x.idl']\n"
        f"validation:\n  fail_on: {fail_on}\n"
    )
    return cfg


def test_build_rejects_unknown_format_before_reading_config():
    result = runner.invoke(
        app,
        ["build", "--config", "/nonexistent/idl2icd.yaml", "--format", "docx2"],
    )
    assert result.exit_code == 1
    assert "Unknown --format 'docx2'" in result.output
    assert "all" in result.output and "site" in result.output and "pdf" in result.output


def test_diff_rejects_unknown_output_format_before_reading_config():
    result = runner.invoke(
        app,
        [
            "diff",
            "--config",
            "/nonexistent/idl2icd.yaml",
            "--against",
            "/nonexistent/snap.json",
            "--output-format",
            "html",
        ],
    )
    assert result.exit_code == 1
    assert "Unknown --output-format 'html'" in result.output
    assert "markdown" in result.output and "text" in result.output


def test_build_accepts_uppercase_format(tmp_path):
    cfg = _project(tmp_path)
    result = runner.invoke(app, ["build", "--config", str(cfg), "--format", "SITE"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "dist" / "site" / "index.html").exists()


def test_build_accepts_output_format_alias(tmp_path):
    cfg = _project(tmp_path)
    result = runner.invoke(app, ["build", "--config", str(cfg), "--output-format", "site"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "dist" / "site" / "index.html").exists()


def test_snapshot_save_and_diff_end_to_end(tmp_path):
    cfg = _project(tmp_path)
    save = runner.invoke(app, ["snapshot", "save", "--config", str(cfg)])
    assert save.exit_code == 0, save.output

    snap = tmp_path / ".idl2icd" / "snapshots" / "1.0.0.json"
    assert snap.exists()

    diff = runner.invoke(
        app,
        ["diff", "--config", str(cfg), "--against", str(snap), "--output-format", "markdown"],
    )
    assert diff.exit_code == 0, diff.output
    assert "## 1.0.0 → 1.0.0" in diff.output
    assert "No changes" in diff.output


def test_help_lists_commands_and_not_plugins():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "plugins" not in result.output
    for cmd in ("validate", "build", "diff", "snapshot", "metadata", "doctor"):
        assert cmd in result.output
