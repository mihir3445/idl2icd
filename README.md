# idl2icd

[![CI](https://github.com/mihir3445/idl2icd/actions/workflows/ci.yml/badge.svg)](https://github.com/mihir3445/idl2icd/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)
[![Live Demo](https://img.shields.io/badge/live%20demo-view%20site-brightgreen)](https://mihir3445.github.io/idl2icd/)

**[→ View the live example ICD site](https://mihir3445.github.io/idl2icd/)** — generated entirely from `examples/robot-fleet`, rebuilt automatically on every tagged release.

**The IDL is the single source of truth. Everything else — the website, the
PDF, the Word doc, the change log — is generated from it.**

Generate a modern website, PDF, and Word document Interface Control Document
for a DDS system straight from OMG IDL + a small metadata layer (publishers,
subscribers, QoS, timing, units).

See [`Architecture`](ARCHITECTURE.md) for the full design, `ROADMAP.md` for what's implemented
vs. still designed-only, and `CONTRIBUTING.md` to get set up for development.
See `examples/robot-fleet` for a runnable example.

## Platform notes

**PDF export on macOS:** WeasyPrint depends on native Pango/Cairo/GObject
libraries. `pip install` succeeds and `import weasyprint` can even work, but
*rendering* a PDF can still fail with something like:

```text
OSError: cannot load library 'libgobject-2.0-0': dlopen(...)
```

This happens because Homebrew's lib directory isn't on macOS's default
dynamic-linker search path. Fix:

```bash
brew install pango gdk-pixbuf libffi

# Apple Silicon:
export DYLD_FALLBACK_LIBRARY_PATH="/opt/homebrew/lib:$DYLD_FALLBACK_LIBRARY_PATH"
# Intel Mac:
export DYLD_FALLBACK_LIBRARY_PATH="/usr/local/lib:$DYLD_FALLBACK_LIBRARY_PATH"
```

Add the `export` line to `~/.zshrc`, open a new terminal, then `idl2icd doctor`
should report `weasyprint available: PDF export enabled.`

`idl2icd doctor` and `idl2icd build --format pdf`/`all` both catch this and
print the fix above automatically rather than a raw traceback.

**PDF export on Debian/Ubuntu:**

```bash
sudo apt-get install libpango-1.0-0 libpangoft2-1.0-0 libgdk-pixbuf2.0-0
```

**PDF export on Windows:** requires the GTK3 runtime — see WeasyPrint's
[Windows install notes](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#windows).

## Quickstart

```bash
python3 -m venv .venv             # create the virtual environment
source .venv/bin/activate         # activate the environment
pip install -e ".[pdf,docx]"      # drop extras you don't need
```

```bash
idl2icd doctor                    # check project is working fine
```

For development, install the dev extras and run the test suite:

```bash
pip install -e ".[dev]"
python3 -m pytest -q
```

Shall show you following to confirm things are working without error.

```text
lark, pydantic, jinja2, typer, pluggy all importable. Environment OK.
weasyprint available: PDF export enabled.
python-docx available: Word export enabled.
```

Build the example project

```bash
cd examples/robot-fleet
idl2icd validate
idl2icd build --format all        # writes dist/site/, dist/icd.pdf, dist/icd.docx
open dist/site/index.html         # Linux: xdg-open

# Freeze a snapshot, make a change, then see a semantic change report:
idl2icd snapshot save --tag v0.1.0
# ...edit idl/telemetry.idl or metadata/telemetry.yaml...
idl2icd diff --against .idl2icd/snapshots/v0.1.0.json --output-format markdown
```

## Status

v0.3 — functional, tested: IDL parsing (Lark-based grammar covering modules,
structs, unions, enums, sequences, bounded strings, `@key`/`@optional`/`@topic`
annotations, doc-comments), metadata merge, a validation rule engine, Mermaid
pub/sub + type diagrams, a static HTML site renderer, **PDF export**
(WeasyPrint), **Word/.docx export** (python-docx), a **plugin system**
(`pluggy` hookspecs), and a **snapshot + semantic change-report engine**
(`idl2icd diff`). See `ROADMAP.md` for exactly what's implemented vs. still
designed-only (full ANTLR-grade grammar, SARIF output, per-subscriber RxO
QoS matrix, Mermaid→image embedding in PDF/docx, `init`/`serve` commands).
