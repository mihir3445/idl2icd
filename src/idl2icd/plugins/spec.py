"""Hook specifications for idl2icd plugins.

A plugin is any importable object implementing one or more of these hooks,
registered either via a Python entry point (group `idl2icd.plugins`) or,
for local/dev use, passed directly to `PluginManager.register()`.

All hooks are optional — implement only the ones you need.
"""
from __future__ import annotations

import pluggy

hookspec = pluggy.HookspecMarker("idl2icd")
hookimpl = pluggy.HookimplMarker("idl2icd")


class DDSICDHookSpec:
    @hookspec
    def register_validation_rules(self):
        """Return an iterable of (rule_id, default_severity, rule_fn) tuples.
        rule_fn: Callable[[IRModel], Iterator[Diagnostic]]
        """

    @hookspec
    def register_diagram_generators(self):
        """Return an iterable of (name, Callable[[IRModel], str]) tuples,
        each producing Mermaid source (or another embeddable format)."""

    @hookspec
    def register_renderers(self):
        """Return an iterable of (format_name, Callable[[IRModel, RenderContext], None])
        tuples — each renderer is responsible for writing its own output."""

    @hookspec
    def on_ir_built(self, ir):
        """Called after IDL parsing + metadata merge, before validation.
        May return a modified IRModel (e.g. to enrich topics with live data
        from a running DDS domain), or None to leave it unchanged."""

    @hookspec
    def on_before_render(self, ir, ctx):
        """Called once before rendering begins. `ctx` is a RenderContext
        dict-like object plugins may use to stash shared state."""

    @hookspec
    def on_after_build(self, artifacts):
        """Called once after all output artifacts have been written.
        `artifacts` is a dict of {name: Path}."""
