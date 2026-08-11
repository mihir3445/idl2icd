# idl2icd

[![CI](https://github.com/mihir3445/idl2icd/actions/workflows/ci.yml/badge.svg)](https://github.com/mihir3445/idl2icd/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)
[![Live Demo](https://img.shields.io/badge/live%20demo-view%20site-brightgreen)](https://mihir3445.github.io/idl2icd/)

**The IDL is the single source of truth. Everything else — the website, the
PDF, the Word doc, and change reports — is generated from it.**

idl2icd turns OMG IDL plus a little YAML metadata into a polished Interface
Control Document for DDS systems. You can use it to validate your model,
build a static website, export PDF/Word files, and compare versions over time.

**[→ View the live example ICD site](https://mihir3445.github.io/idl2icd/)** — generated from [examples/robot-fleet](examples/robot-fleet), rebuilt automatically on tagged releases.

If you want the full background and roadmap, see [ARCHITECTURE.md](ARCHITECTURE.md), [ROADMAP.md](ROADMAP.md), and [CONTRIBUTING.md](CONTRIBUTING.md).

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
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[pdf,docx]"
```

Then check that everything is available:

```bash
idl2icd doctor
```

Build the example project:

```bash
cd examples/robot-fleet
idl2icd validate
idl2icd build --format all --open
```

That will generate a site, a PDF, and a Word document in the example folder.

## What the CLI can do

Here is the short version of what `idl2icd --help` exposes:

- `idl2icd validate` — parse your IDL, merge metadata, and check for problems.
- `idl2icd build` — generate the ICD website and optionally export PDF and Word output.
- `idl2icd diff` — compare the current build against an earlier snapshot and show what changed.
- `idl2icd doctor` — check that the required Python packages and PDF export support are available.
- `idl2icd snapshot save` — save a frozen snapshot of the current model for later comparisons.
- `idl2icd plugins list` — list the available plugins.
- `idl2icd metadata generate` — create starter metadata YAML files from your IDL.

A few useful examples:

```bash
# Generate skeleton metadata YAML from your IDL
idl2icd metadata generate
idl2icd metadata generate --all-structs

# Save a snapshot and compare it later
idl2icd snapshot save --tag v0.1.0
idl2icd diff --against .idl2icd/snapshots/v0.1.0.json --output-format markdown
```

## Development

If you want to work on the project itself:

```bash
pip install -e ".[dev]"
python3 -m pytest -q
```

## Status

The current project is already useful for real documentation workflows: parsing IDL,
merging metadata, validating topics and QoS, rendering HTML, exporting PDF/Word,
and comparing snapshots over time.
