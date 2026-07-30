from __future__ import annotations

from idl2icd.model.ir import IRModel, Diagnostic
from idl2icd.validation.engine import register_rule


@register_rule("missing-units", default_severity="warn")
def check_missing_units(ir: IRModel):
    numeric_primitives = {
        "float", "double", "short", "long", "unsigned", "int8", "uint8",
        "int16", "uint16", "int32", "uint32", "int64", "uint64", "octet",
    }
    for t in ir.types.values():
        if t.kind != "struct":
            continue
        for f in t.fields:
            if f.type_ref.name in numeric_primitives and not f.meta.unit:
                yield Diagnostic(
                    rule="missing-units", severity="warn",
                    message=f"Field '{t.fqn}.{f.name}' is numeric but has no documented unit.",
                    location=f.source_span,
                )


@register_rule("missing-owner", default_severity="warn")
def check_missing_owner(ir: IRModel):
    for topic in ir.topics.values():
        if not topic.publishers:
            yield Diagnostic(
                rule="missing-owner", severity="warn",
                message=f"Topic '{topic.fqn}' has no declared publisher.",
            )


@register_rule("undocumented-topic", default_severity="info")
def check_undocumented_topic(ir: IRModel):
    for topic in ir.topics.values():
        if not topic.description:
            yield Diagnostic(
                rule="undocumented-topic", severity="info",
                message=f"Topic '{topic.fqn}' has no description.",
            )


@register_rule("qos-compatibility", default_severity="error")
def check_qos_compatibility(ir: IRModel):
    """Simplified RxO check: a subscriber that requests RELIABLE cannot be
    paired with a topic offered as BEST_EFFORT; TRANSIENT_LOCAL subscribers
    need at least TRANSIENT_LOCAL durability offered. Since v0.1 doesn't yet
    model per-subscriber requested QoS overrides, this checks the topic's
    own resolved QoS is internally sane and flags BEST_EFFORT + high
    criticality as a likely mismatch worth a human's attention.
    """
    for topic in ir.topics.values():
        if topic.criticality in ("high", "safety") and topic.qos.reliability == "BEST_EFFORT":
            yield Diagnostic(
                rule="qos-compatibility", severity="error",
                message=(
                    f"Topic '{topic.fqn}' is marked criticality='{topic.criticality}' "
                    f"but uses BEST_EFFORT reliability."
                ),
            )
