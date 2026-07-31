# Roadmap

## Implemented (v0.4)
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
- **Word/.docx export** via `python-docx`, schema-validated and visually
  verified via LibreOffice → PDF → page images.
- **Plugin system** via `pluggy`: hookspecs for validation rules, diagram
  generators, renderers, and IR-enrichment (`on_ir_built`); `idl2icd plugins
  list` shows discovered plugins.
- **Snapshot + change-report engine**: `idl2icd snapshot save` / `idl2icd
  diff --against <snapshot>` — semantic diff (breaking / additive /
  informational) keyed by FQN.
- **`idl2icd schema`**: generates JSON Schema from the Pydantic metadata and
  project-config models, for editor autocompletion. Verified by actually
  validating the real example YAML files against the generated schema (and
  confirming an unknown-key document is correctly rejected), not just
  checking the schema parses. `examples/robot-fleet/.vscode/settings.json`
  wires this up for VS Code's YAML extension out of the box.
- CLI: `validate`, `build --format site|pdf|docx|all`, `diff`,
  `snapshot save`, `plugins list`, `schema`, `doctor`.
- **`LICENSE`** (Apache-2.0, matching what `pyproject.toml` already declared
  — this was missing before and is a real gap for a public GitHub repo).
- **`CONTRIBUTING.md`** — dev setup, where each extension point lives, and
  the testing philosophy the existing suite follows.
- **Lint-clean codebase**: `ruff check .` passes with zero issues (was 83
  real issues — unused variables, unsorted imports, a legacy `typing.Union`
  — now fixed); CI's lint step is blocking, not `|| true` anymore.
- 11 passing pytest tests: parse+merge, validation rules, snapshot/diff,
  the docx renderer's actual content, and the generated JSON Schemas
  actually validating (and rejecting) real data.
- GitHub Actions: CI (matrix test + example build, lint-blocking), a
  PR-time docs-drift workflow posting the change report as a sticky PR
  comment, and a release workflow that builds site + PDF + docx, generates
  schemas, freezes/commits a snapshot, deploys to Pages, and attaches PDF +
  docx to the GitHub Release.

## Attempted and genuinely blocked in this environment (not a design gap)
- **Mermaid → image embedding for PDF/docx** via `mermaid-cli` (`mmdc`):
  I tried installing it in this sandbox. It failed because Puppeteer's
  bundled Chromium download is blocked by this environment's network
  allowlist (`storage.googleapis.com` isn't reachable here) — not because
  the approach is wrong. A normal GitHub Actions runner has unrestricted
  internet and should install and run `mmdc` without issue. This still
  needs to be wired into `render/pdf/renderer.py` and
  `render/docx/renderer.py` (call `mmdc` as a subprocess, embed the
  resulting SVG/PNG, fall back to the current text-source behavior if
  `mmdc` isn't on PATH) and then verified for real in CI, not assumed.

## Designed, not yet implemented (see ARCHITECTURE.md for full spec)
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
- **Example third-party plugins** (e.g. a Confluence exporter, a live DDS
  domain-introspection enricher) to prove out the plugin API end-to-end
  from outside the core package — the API is currently only exercised by
  the in-tree `CorePlugin`.

## Suggested next session
1. Wire `mmdc` into the PDF/docx paths (see "genuinely blocked" above) —
   this needs to run in an environment with real internet access to verify.
2. Build a real per-subscriber RxO compatibility check + rendered QoS
   matrix page (site, PDF, and docx), replacing the current heuristic.
3. Write one real example plugin package (e.g. a Confluence or Markdown
   exporter) living outside `src/dds_icd/`, registered via an entry point,
   to validate the plugin API isn't just internally self-consistent.
