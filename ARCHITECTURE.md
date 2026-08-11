# idl2icd architecture

Status: lightweight overview for contributors.

## Goal

idl2icd turns OMG IDL plus YAML metadata into an interface control document. The project is intentionally small: parse once, build one internal model, then render or validate from that model.

## High-level flow

```text
IDL files + metadata YAML
        -> parse and merge into one IR
        -> run validation rules
        -> render site / PDF / docx
        -> optionally save snapshots and diff them
```

## Main pieces

- cli.py
  - Typer entry points for validate, build, diff, snapshot save, plugins list, metadata generate, and doctor.
- config.py
  - Loads and validates the project config from idl2icd.yaml.
- parsing/
  - Lark grammar and parser entrypoint for IDL.
  - A small doc-comment pass helps attach comments to declarations.
- model/
  - IR models and the merge logic that combines IDL structure with metadata.
- validation/
  - Rule engine plus built-in validation rules.
- render/
  - Site renderer, PDF renderer, and Word renderer.
- plugins/
  - Pluggy-based extension hooks and plugin discovery.
- snapshot.py
  - Saves IR snapshots and compares them for semantic change reports.
- metadata_gen.py
  - Generates starter metadata YAML from IDL.

## Core design choice

The IR is the single source of truth.

- Renderers read from the IR.
- Validation reads from the IR.
- Snapshot diffing reads from the IR.
- The tool does not re-derive output from raw IDL files at each stage.

That keeps the output consistent and makes it easier to add new renderers or checks later.

## Current CLI shape

The commands in the current implementation are:

```text
idl2icd validate
idl2icd build
idl2icd diff
idl2icd snapshot save
idl2icd plugins list
idl2icd metadata generate
idl2icd doctor
```

## Notes for contributors

- Keep changes focused around the IR and the CLI surface.
- Validation and rendering should stay driven by the same IR model.
- New features should fit the existing flow instead of introducing separate parsing paths.
