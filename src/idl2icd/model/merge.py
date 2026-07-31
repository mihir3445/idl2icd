from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from idl2icd.model.ir import (
    Diagnostic,
    Endpoint,
    IRModel,
    ProjectMeta,
    QoSDeadline,
    QoSHistory,
    QoSLiveliness,
    RateSpec,
    ResolvedQoS,
    StructType,
    Topic,
)
from idl2icd.model.metadata_schema import MetadataFile
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

    qos_profiles: dict[str, dict] = {}
    topic_meta: dict[str, dict] = {}
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

        for name, prof in mf.qos_profiles.items():
            qos_profiles[name] = prof.model_dump(exclude_none=True)
        for fqn, t in mf.topics.items():
            topic_meta[fqn] = t.model_dump(exclude_none=True)
            merged.topic_hints.add(fqn)  # metadata can promote a struct to topic status

    ir = IRModel(project=project, types=merged.types)

    for fqn in sorted(merged.topic_hints):
        data_type = merged.types.get(fqn)
        if data_type is None or not isinstance(data_type, StructType):
            diagnostics.append(Diagnostic(
                rule="dangling-topic-ref", severity="error",
                message=f"Metadata references topic '{fqn}' but no matching struct was found in parsed IDL.",
            ))
            continue

        tmeta = topic_meta.get(fqn, {})
        qos_dict = _resolve_qos(tmeta.get("qos"), qos_profiles)

        topic = Topic(
            fqn=fqn,
            data_type_fqn=fqn,
            description=tmeta.get("description") or data_type.doc,
            criticality=tmeta.get("criticality"),
            rate=RateSpec(**tmeta["rate"]) if tmeta.get("rate") else None,
            qos=qos_dict,
            publishers=[Endpoint(**p) for p in tmeta.get("publishers", [])],
            subscribers=[Endpoint(**s) for s in tmeta.get("subscribers", [])],
        )
        ir.topics[fqn] = topic

        # apply per-field metadata onto the struct's fields (in place)
        field_meta = tmeta.get("fields", {})
        for f in data_type.fields:
            fm = field_meta.get(f.name)
            if fm:
                f.meta = f.meta.model_copy(update=fm)

    ir.diagnostics = diagnostics
    return ir


def _resolve_qos(qos_meta: dict | None, qos_profiles: dict[str, dict]) -> ResolvedQoS:
    base: dict = {}
    if qos_meta:
        profile_name = qos_meta.get("profile")
        if profile_name and profile_name in qos_profiles:
            base.update(qos_profiles[profile_name])
        overrides = qos_meta.get("overrides") or {}
        base.update({k: v for k, v in overrides.items() if v is not None})

    kwargs = {}
    for key in ("reliability", "durability"):
        if key in base:
            kwargs[key] = base[key]

    for key, cls in (
        ("history", QoSHistory),
        ("deadline", QoSDeadline),
        ("liveliness", QoSLiveliness),
    ):
        if base.get(key):
            kwargs[key] = cls(**base[key])
    return ResolvedQoS(**kwargs)
