from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from idl2icd.model.ir import (
    Diagnostic,
    IRModel,
    ProjectMeta,
    ResolvedQoS,
    StructType,
    Topic,
)
from idl2icd.model.metadata_schema import (
    MetadataFile,
    MetaField,
    MetaQoS,
    MetaQoSOverride,
    MetaTopic,
)
from idl2icd.parsing.idl_parser import ParsedFile, parse_idl_file


def build_ir(
    idl_paths: list[Path],
    metadata_paths: list[Path],
    project: ProjectMeta,
    include_dirs: list[Path] | None = None,
) -> IRModel:
    diagnostics: list[Diagnostic] = []

    merged = ParsedFile()
    for p in idl_paths:
        parsed = parse_idl_file(p, include_dirs=include_dirs)
        merged.types.update(parsed.types)
        merged.topic_hints.update(parsed.topic_hints)

    qos_profiles: dict[str, MetaQoSOverride] = {}
    topic_meta: dict[str, MetaTopic] = {}
    for mp in metadata_paths:
        raw_text = Path(mp).read_text()
        try:
            raw = yaml.safe_load(raw_text) or {}
        except yaml.YAMLError as exc:
            raise ValueError(f"Failed to parse metadata YAML '{mp}': {exc}") from exc

        try:
            mf = MetadataFile.model_validate(raw)
        except ValidationError as exc:
            raise ValueError(f"Invalid metadata file '{mp}': {exc}") from exc

        qos_profiles |= mf.qos_profiles
        topic_meta |= mf.topics
        # Metadata can promote a plain struct to topic status.
        merged.topic_hints.update(mf.topics)

    ir = IRModel(project=project, types=merged.types)

    for fqn in sorted(merged.topic_hints):
        data_type = merged.types.get(fqn)
        if data_type is None or not isinstance(data_type, StructType):
            diagnostics.append(
                Diagnostic(
                    rule="dangling-topic-ref",
                    severity="error",
                    message=(
                        f"Metadata references topic '{fqn}' but no matching "
                        f"struct was found in parsed IDL."
                    ),
                )
            )
            continue

        tmeta = topic_meta.get(fqn)
        topic = Topic(
            fqn=fqn,
            data_type_fqn=fqn,
            description=tmeta.description if tmeta and tmeta.description else data_type.doc,
            criticality=tmeta.criticality if tmeta else None,
            rate=tmeta.rate if tmeta else None,
            qos=_resolve_qos(tmeta.qos if tmeta else None, qos_profiles),
            publishers=list(tmeta.publishers) if tmeta else [],
            subscribers=list(tmeta.subscribers) if tmeta else [],
        )
        ir.topics[fqn] = topic

        # Apply per-field metadata onto the struct's fields (in place), so the
        # merged IR is what renderers, rules, and snapshots see.
        field_meta: dict[str, MetaField] = tmeta.fields if tmeta else {}
        for f in data_type.fields:
            fm = field_meta.get(f.name)
            if fm:
                f.meta = f.meta.model_copy(update=fm.model_dump(exclude_none=True))

    ir.diagnostics = diagnostics
    return ir


def _apply_qos_override(base: ResolvedQoS, override: MetaQoSOverride) -> ResolvedQoS:
    """Overlay the non-None fields of a profile/overrides block onto a QoS value."""
    updates: dict[str, object] = {}
    for fname in ("reliability", "durability", "history", "deadline", "liveliness"):
        value = getattr(override, fname)
        if value is not None:
            updates[fname] = value
    return base.model_copy(update=updates)


def _resolve_qos(
    qos_meta: MetaQoS | None,
    qos_profiles: dict[str, MetaQoSOverride],
) -> ResolvedQoS:
    """Resolve a topic's QoS settings.

    A named *profile* (if referenced and known) is applied first, then any
    inline *overrides* block is layered on top of it. Unknown profile names
    are silently ignored, matching the pre-existing behavior.
    """
    resolved = ResolvedQoS()
    if qos_meta and qos_meta.profile:
        profile = qos_profiles.get(qos_meta.profile)
        if profile is not None:
            resolved = _apply_qos_override(resolved, profile)
    if qos_meta and qos_meta.overrides:
        resolved = _apply_qos_override(resolved, qos_meta.overrides)
    return resolved
