from __future__ import annotations

from typing import Callable, Iterator

from idl2icd.model.ir import Diagnostic, IRModel

_RULES: dict[str, Callable[[IRModel], Iterator[Diagnostic]]] = {}
_DEFAULT_SEVERITY: dict[str, str] = {}


def register_rule(id: str, default_severity: str = "warn"):
    def deco(fn):
        _RULES[id] = fn
        _DEFAULT_SEVERITY[id] = default_severity
        return fn
    return deco


def run_rules(ir: IRModel, severities: dict[str, str] | None = None) -> list[Diagnostic]:
    severities = severities or {}
    out: list[Diagnostic] = list(ir.diagnostics)  # carry over merge-time diagnostics
    for rule_id, fn in _RULES.items():
        sev = severities.get(rule_id, _DEFAULT_SEVERITY[rule_id])
        if sev == "off":
            continue
        for diag in fn(ir):
            out.append(diag.model_copy(update={"severity": sev}))
    return out


SEVERITY_RANK = {"info": 0, "warn": 1, "error": 2}


def worst_severity(diagnostics: list[Diagnostic]) -> str | None:
    if not diagnostics:
        return None
    return max(diagnostics, key=lambda d: SEVERITY_RANK[d.severity]).severity
