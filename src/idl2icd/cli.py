from __future__ import annotations

from pathlib import Path

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.markup import escape
from rich.table import Table

import idl2icd.validation.rules.builtin  # noqa: F401  (registers built-in rules)
from idl2icd.config import load_config
from idl2icd.metadata_gen import generate_metadata_for_idl
from idl2icd.model.ir import ProjectMeta
from idl2icd.model.merge import build_ir
from idl2icd.plugins.loader import build_plugin_manager, list_available_plugins
from idl2icd.render.site.renderer import render_site
from idl2icd.snapshot import diff_ir, load_snapshot, save_snapshot
from idl2icd.validation.engine import SEVERITY_RANK, run_rules, worst_severity

app = typer.Typer(help="idl2icd: generate an Interface Control Document from OMG IDL + metadata.")
snapshot_app = typer.Typer(help="Manage frozen IR snapshots used for change reports.")
plugins_app = typer.Typer(help="Inspect available idl2icd plugins.")
metadata_app = typer.Typer(help="Generate skeleton metadata YAML files from IDL.")
app.add_typer(snapshot_app, name="snapshot")
app.add_typer(plugins_app, name="plugins")
app.add_typer(metadata_app, name="metadata")
console = Console()


def _pdf_unavailable_message(exc: Exception) -> str:
    """WeasyPrint can fail two different ways: the package isn't installed
    at all (ImportError), or it's installed but can't dlopen its native
    Pango/GObject/Cairo libraries at import/render time (OSError) — the
    latter is common on macOS even after `brew install pango`, because
    Homebrew's lib directory isn't on the dynamic linker's default search
    path. Give a targeted hint for each case instead of a raw traceback.
    """
    import platform

    if isinstance(exc, ImportError):
        return (
            "PDF export requires the optional 'pdf' extra:\n"
            "  pip install 'idl2icd[pdf]'"
        )

    # OSError from a failed dlopen of libgobject/libpango/libcairo etc.
    if platform.system() == "Darwin":
        return (
            f"weasyprint is installed but couldn't load its native libraries ({exc}).\n"
            "This is a known macOS issue: Homebrew's lib path isn't on the dynamic\n"
            "linker's default search path. Fix:\n"
            "  brew install pango gdk-pixbuf libffi\n"
            "  # Apple Silicon:\n"
            "  export DYLD_FALLBACK_LIBRARY_PATH=\"/opt/homebrew/lib:$DYLD_FALLBACK_LIBRARY_PATH\"\n"
            "  # Intel Mac:\n"
            "  export DYLD_FALLBACK_LIBRARY_PATH=\"/usr/local/lib:$DYLD_FALLBACK_LIBRARY_PATH\"\n"
            "Add the export line to your ~/.zshrc, open a new terminal, then retry."
        )
    return (
        f"weasyprint is installed but couldn't load its native libraries ({exc}).\n"
        "Debian/Ubuntu: sudo apt-get install libpango-1.0-0 libpangoft2-1.0-0 libgdk-pixbuf2.0-0\n"
        "Windows: install the GTK3 runtime — see "
        "https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#windows"
    )


def _build_ir_and_diagnostics(config_path: str):
    try:
        cfg = load_config(config_path)
    except FileNotFoundError:
        console.print(f"[red]Config file not found: {config_path}[/red]")
        raise typer.Exit(code=1)
    except ValidationError as exc:
        console.print(f"[red]Configuration validation failed:\n{exc}[/red]")
        raise typer.Exit(code=1)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)

    project = ProjectMeta(**cfg.project.model_dump())
    idl_paths = cfg.resolve_idl_paths()
    metadata_paths = cfg.resolve_metadata_paths()
    include_dirs = cfg.resolve_include_paths()
    if not idl_paths:
        console.print(f"[red]No IDL files matched sources.idl patterns: {cfg.sources.idl}[/red]")
        raise typer.Exit(code=1)

    try:
        ir = build_ir(idl_paths, metadata_paths, project, include_dirs=include_dirs)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)

    pm = build_plugin_manager(enabled=cfg.plugins.enabled or None)
    for result in pm.hook.on_ir_built(ir=ir):
        if result is not None:
            ir = result

    diagnostics = run_rules(ir, severities=cfg.validation.rules)
    return cfg, ir, diagnostics


def _print_diagnostics(diagnostics):
    if not diagnostics:
        console.print("[green]No validation issues found.[/green]")
        return
    table = Table(title="Validation Diagnostics")
    table.add_column("Severity")
    table.add_column("Rule")
    table.add_column("Message")
    for d in diagnostics:
        color = {"error": "red", "warn": "yellow", "info": "blue"}[d.severity]
        table.add_row(f"[{color}]{d.severity.upper()}[/{color}]", d.rule, d.message)
    console.print(table)


def _exit_if_validation_failed(worst: str | None, threshold: str, message: str):
    if worst and SEVERITY_RANK[worst] >= SEVERITY_RANK[threshold]:
        console.print(f"[red]{message}[/red]")
        raise typer.Exit(code=1)


@app.command()
def validate(config: str = typer.Option("idl2icd.yaml", "--config", "-c")):
    """Parse + merge + run validation only (fast, CI-friendly)."""
    cfg, _, diagnostics = _build_ir_and_diagnostics(config)
    _print_diagnostics(diagnostics)
    worst = worst_severity(diagnostics)
    _exit_if_validation_failed(
        worst,
        cfg.validation.fail_on,
        f"Validation failed: worst severity '{worst}' >= fail_on threshold '{cfg.validation.fail_on}'",
    )
    console.print("[green]Validation passed.[/green]")


@app.command()
def build(
    config: str = typer.Option("idl2icd.yaml", "--config", "-c"),
    format: str = typer.Option("site", "--format", help="site | pdf | docx | all"),
):
    """Full pipeline: parse -> validate -> render site, PDF, and/or docx."""
    cfg, ir, diagnostics = _build_ir_and_diagnostics(config)
    _print_diagnostics(diagnostics)
    base_dir = Path(cfg._base_dir)

    out_dir = base_dir / cfg.output.site_dir
    if format in ("site", "all"):
        render_site(
            ir,
            diagnostics,
            out_dir,
            direction=cfg.diagrams.direction,
            show_topic_qos=cfg.diagrams.show_topic_qos,
            show_topic_rate=cfg.diagrams.show_topic_rate,
        )
        console.print(f"[green]Site written to {out_dir}[/green]")

    if format in ("pdf", "all"):
        from idl2icd.render.pdf.renderer import render_pdf
        pdf_path = base_dir / cfg.output.pdf_path
        try:
            render_pdf(
                ir,
                diagnostics,
                pdf_path,
                direction=cfg.diagrams.direction,
                show_topic_qos=cfg.diagrams.show_topic_qos,
                show_topic_rate=cfg.diagrams.show_topic_rate,
            )
            console.print(f"[green]PDF written to {pdf_path}[/green]")
        except (ImportError, OSError) as exc:
            console.print(f"[yellow]{escape(_pdf_unavailable_message(exc))}[/yellow]")

    if format in ("docx", "all"):
        from idl2icd.render.docx.renderer import render_docx
        docx_path = base_dir / cfg.output.docx_path
        try:
            render_docx(
                ir,
                diagnostics,
                docx_path,
                direction=cfg.diagrams.direction,
                show_topic_qos=cfg.diagrams.show_topic_qos,
                show_topic_rate=cfg.diagrams.show_topic_rate,
            )
            console.print(f"[green]Word document written to {docx_path}[/green]")
        except ImportError:
            msg = "Word export requires the optional 'docx' extra: pip install 'idl2icd[docx]'"
            console.print(f"[yellow]{escape(msg)}[/yellow]")

    worst = worst_severity(diagnostics)
    _exit_if_validation_failed(
        worst,
        cfg.validation.fail_on,
        f"Build produced output, but validation failed (worst='{worst}').",
    )


@app.command()
def diff(
    config: str = typer.Option("idl2icd.yaml", "--config", "-c"),
    against: str = typer.Option(..., "--against", help="Path to a previously saved snapshot JSON file"),
    output_format: str = typer.Option("text", "--output-format", help="text | markdown"),
):
    """Show a semantic change report between the current build and a saved snapshot."""
    _, ir, _ = _build_ir_and_diagnostics(config)
    old_ir = load_snapshot(against)
    report = diff_ir(old_ir, ir)

    if output_format == "markdown":
        typer.echo(report.to_markdown())
    else:
        if not report.changes:
            console.print("[green]No changes detected.[/green]")
        for c in report.changes:
            color = {"breaking": "red", "additive": "green", "informational": "blue"}[c.change_class]
            console.print(f"[{color}]{c.change_class.upper():14}[/{color}] {c.entity}: {c.detail}")

    if report.breaking():
        console.print(f"\n[red]{len(report.breaking())} breaking change(s) detected.[/red]")


@snapshot_app.command("save")
def snapshot_save(
    config: str = typer.Option("idl2icd.yaml", "--config", "-c"),
    tag: str = typer.Option(None, "--tag", help="Filename tag; defaults to the project version"),
):
    """Freeze the current IR to a JSON snapshot for future `idl2icd diff` comparisons."""
    cfg, ir, _ = _build_ir_and_diagnostics(config)
    tag = tag or ir.project.version
    snap_dir = Path(cfg._base_dir) / cfg.output.snapshot_dir
    path = snap_dir / f"{tag}.json"
    save_snapshot(ir, path)
    console.print(f"[green]Snapshot saved to {path}[/green]")


@plugins_app.command("list")
def plugins_list():
    """List discoverable idl2icd plugins (the 'core' plugin always loads)."""
    for name in list_available_plugins():
        console.print(f"- {name}")


@metadata_app.command("generate")
def metadata_generate(
    config: str = typer.Option("idl2icd.yaml", "--config", "-c"),
    output_dir: str = typer.Option("metadata", "--output-dir", "-o", help="Directory to write generated YAML files to"),
    all_structs: bool = typer.Option(False, "--all-structs", "-a", help="Generate entries for ALL structs, not just @topic ones"),
):
    """Generate skeleton metadata YAML files from IDL source files.

    Parses each IDL file and produces a corresponding .yaml file with skeleton
    entries for every @topic-annotated struct, including doc-comments as
    descriptions, auto-detected fields, and placeholder sections for QoS
    profiles, publishers, subscribers, and field-level metadata.

    Use --all-structs / -a to generate entries for every struct in the IDL
    (even those without @topic), so you can decide which ones to promote to
    topics in the metadata YAML.
    """
    try:
        cfg = load_config(config)
    except FileNotFoundError:
        console.print(f"[red]Config file not found: {config}[/red]")
        raise typer.Exit(code=1)
    except (ValidationError, ValueError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1)

    idl_paths = cfg.resolve_idl_paths()
    include_dirs = cfg.resolve_include_paths()
    if not idl_paths:
        console.print(f"[red]No IDL files matched sources.idl patterns: {cfg.sources.idl}[/red]")
        raise typer.Exit(code=1)

    base_dir = Path(cfg._base_dir)
    out_dir = base_dir / output_dir
    generated = 0
    skipped = 0

    for idl_path in idl_paths:
        try:
            result = generate_metadata_for_idl(
                idl_path, out_dir, include_dirs=include_dirs, all_structs=all_structs,
            )
            if result is not None:
                console.print(f"  [green]✔[/green] {result}")
                generated += 1
            else:
                skipped += 1
        except ValueError as exc:
            console.print(f"  [red]✖[/red] {idl_path}: {exc}")

    if generated:
        console.print(f"\n[green]Generated {generated} metadata file(s) in {out_dir}[/green]")
    if skipped:
        console.print(f"[yellow]Skipped {skipped} IDL file(s) with no {'@topic' if not all_structs else 'struct'} definitions[/yellow]")
    if not generated and not skipped:
        console.print("[yellow]No IDL files found to process.[/yellow]")


@app.command()
def doctor():
    """Environment sanity check."""
    import lark, pydantic, jinja2, typer as _t, pluggy  # noqa
    console.print("[green]lark, pydantic, jinja2, typer, pluggy all importable. Environment OK.[/green]")
    try:
        import weasyprint  # noqa
        console.print("[green]weasyprint available: PDF export enabled.[/green]")
    except (ImportError, OSError) as exc:
        console.print(f"[yellow]{escape(_pdf_unavailable_message(exc))}[/yellow]")

    try:
        import docx  # noqa
        console.print("[green]python-docx available: Word export enabled.[/green]")
    except ImportError:
        msg = "python-docx not installed: Word export disabled (pip install 'idl2icd[docx]')."
        console.print(f"[yellow]{escape(msg)}[/yellow]")


if __name__ == "__main__":
    app()
