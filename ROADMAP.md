# Roadmap

## Implemented (v0.3)

- Lark-based OMG IDL subset parser: modules, structs, unions, enums, sequences,
  bounded strings, arrays, `@key`/`@optional`/`@topic` annotations, `/** */`
  and `///` doc-comment association.
- Pydantic metadata schema + YAML merge (topics, QoS profiles, publishers,
  subscribers, field-level units/ranges/descriptions).
- Validation rule engine with built-in rules: `missing-units`,
  `missing-owner`, `undocumented-topic`, `qos-compatibility` (simplified).
- Mermaid pub/sub flowchart + type classDiagram generation.
- Static HTML site renderer (Jinja2 + a default theme) with a landing page,
  per-topic pages, and inline validation diagnostics.
- **PDF export** via WeasyPrint, reusing the same IR and a print-mode Jinja2
  template (cover page, topic index, per-topic sections, page numbers).
- **Word/.docx export** via `python-docx` (cover page, topic index table,
  validation results, per-topic sections with QoS/publisher/subscriber/field
  tables). Schema-validated with the OOXML XSD checker (including patching a
  pre-existing gap in python-docx's own blank-document template). Verified
  visually via LibreOffice → PDF → page images, not just "didn't crash."
  Both PDF and docx currently show Mermaid diagrams as a text-source
  fallback rather than a rendered image (see below).
- **Plugin system** via `pluggy`: hookspecs for validation rules, diagram
  generators, renderers, and IR-enrichment (`on_ir_built`); a `CorePlugin`
  routes idl2icd's own built-ins through the same mechanism third-party
  plugins use. `idl2icd plugins list` shows discovered plugins.
- **Snapshot + change-report engine**: `idl2icd snapshot save` freezes the
  IR to versioned JSON; `idl2icd diff --against <snapshot>` produces a
  semantic diff (breaking / additive / informational) keyed by FQN, with
  text or Markdown output. Detects: topic/type removal, field
  add/remove/type-change, `@key` changes, durability/reliability weakening,
  publisher/subscriber changes, criticality/description edits.
- CLI: `validate`, `build --format site|pdf|docx|all`, `diff`,
  `snapshot save`, `plugins list`, `doctor` (reports PDF *and* docx
  availability, with platform-aware fix hints for macOS WeasyPrint issues).
- 8 passing pytest tests covering parse+merge, validation rules, the
  snapshot/diff engine, and the docx renderer's actual document content.
- GitHub Actions: CI (matrix test + example build), a PR-time docs-drift
  workflow that posts the change report as a sticky PR comment, and a
  release workflow that builds site + PDF, freezes/commits a snapshot,
  deploys to GitHub Pages, and attaches the PDF to the GitHub Release.

## Designed, not yet implemented (see ARCHITECTURE.md for full spec)

- **Mermaid → image pre-rendering** for PDF and docx via `mermaid-cli`/`mmdc`,
  so both get real embedded diagrams instead of a source-code fallback block.
- **SARIF export** of validation diagnostics for GitHub code-scanning
  annotations.
- **Sequence-diagram generation** for request/reply topic pairs.
- **Full per-endpoint QoS compatibility (RxO)**: the `qos-compatibility`
  rule is still a simplified single-topic heuristic (criticality vs.
  reliability), not yet a per-subscriber requested-vs-offered comparison
  or a rendered pairwise compatibility matrix.
- **Full OMG IDL 4.2 grammar** via an ANTLR4 migration (typedefs surfaced
  into the IR, `#include`/`#ifdef` preprocessing, fixed-point types,
  bitmask/bitset, forward declarations).
- **`idl2icd init`** scaffolding command and **`idl2icd serve`** live-reload
  dev server.
- **JSON Schema generation** from the Pydantic metadata models for editor
  autocompletion.
- **Example third-party plugins** (e.g. a Confluence exporter, a live DDS
  domain-introspection enricher) to prove out the plugin API end-to-end
  from outside the core package.
- **CI docx build step**: `release.yml`/`ci.yml` currently only exercise
  `--format site` / `all` for PDF; add a docx build+validate step alongside.

## Suggested next session

1. Wire `mmdc` (Node) into the PDF *and* docx paths to replace the
   Mermaid-source fallback with real rendered images in both.
2. Build a real per-subscriber RxO compatibility check + rendered QoS
   matrix page (site, PDF, and docx), replacing the current heuristic.
3. Write one real example plugin package (e.g. a Confluence or Markdown
   exporter) living outside `src/idl2icd/`, registered via an entry point,
   to validate the plugin API isn't just internally self-consistent.
