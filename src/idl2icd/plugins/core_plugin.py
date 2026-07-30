"""The built-in "core" plugin. Registered automatically and always active;
it exposes idl2icd's own rules/diagrams through the same hook mechanism
third-party plugins use, so there's exactly one extensibility path, not a
special-cased built-in one plus a plugin one.
"""
from __future__ import annotations

from idl2icd.plugins.spec import hookimpl
from idl2icd.validation.rules import builtin as builtin_rules
from idl2icd.validation.engine import _RULES, _DEFAULT_SEVERITY  # already-registered rules
from idl2icd.diagrams.pubsub_graph import generate_pubsub_graph, generate_type_diagram


class CorePlugin:
    @hookimpl
    def register_validation_rules(self):
        return [(rid, _DEFAULT_SEVERITY[rid], fn) for rid, fn in _RULES.items()]

    @hookimpl
    def register_diagram_generators(self):
        return [
            ("pubsub_graph", generate_pubsub_graph),
            ("type_diagram", generate_type_diagram),
        ]
