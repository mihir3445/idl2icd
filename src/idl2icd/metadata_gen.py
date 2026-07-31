"""Generates skeleton metadata YAML files from IDL source files.

For each IDL file, this produces a corresponding `.yaml` file with skeleton
entries for every `@topic`-annotated struct, including doc-comments as
descriptions, auto-detected fields, and placeholder sections for QoS profiles,
publishers, subscribers, and field-level metadata that a human can fill in.

Usage:
    idl2icd metadata generate --config idl2icd.yaml
"""
from __future__ import annotations

from pathlib import Path

import yaml

from idl2icd.model.ir import Field_, StructType
from idl2icd.parsing.idl_parser import parse_idl_file


def _field_to_meta(field: Field_) -> dict:
    """Convert a parsed IDL field into a skeleton metadata entry.
    The entry only includes keys that are valid per the metadata schema
    (MetaField model with extra="forbid"). Type hints are omitted since
    the type is already defined in the IDL — the metadata file only
    adds semantic annotations (units, ranges, descriptions).
    """
    entry: dict = {}
    _hint = field.type_ref.render()
    if field.is_key:
        _hint += " [@key]"
    # Use description as the primary field to carry the doc-comment
    # and include the type hint inline.
    if field.doc:
        entry["description"] = field.doc + f" (type: {_hint})"
    else:
        entry["description"] = _hint
    return entry


def _struct_to_topic_meta(struct: StructType) -> dict:
    """Convert a parsed @topic struct into a skeleton topic metadata entry."""
    entry: dict = {}
    if struct.doc:
        entry["description"] = struct.doc
    else:
        entry["description"] = "TODO: Add description for " + struct.fqn

    # Placeholder sections (commented out in the generated YAML via a marker)
    entry["criticality"] = "TODO (low | medium | high | safety)"
    entry["qos"] = {"profile": "TODO: reference a qos_profile or define overrides"}
    entry["publishers"] = [
        {"participant": "TODO: PublisherName", "instance_count": "TBD", "source": "TBD"},
    ]
    entry["subscribers"] = [
        {"participant": "TODO: SubscriberName"},
    ]

    fields: dict[str, dict] = {}
    for f in struct.fields:
        fields[f.name] = _field_to_meta(f)
    entry["fields"] = fields
    return entry


def _generate_yaml_for_idl(idl_path: Path, include_dirs: list[Path] | None = None) -> str | None:
    """Parse a single IDL file and return a YAML string with skeleton metadata,
    or None if the file has no @topic-annotated structs."""
    parsed = parse_idl_file(idl_path, include_dirs=include_dirs)
    if not parsed.topic_hints:
        return None

    # Collect all @topic structs from this file
    topic_entries: dict[str, dict] = {}
    for fqn in sorted(parsed.topic_hints):
        struct = parsed.types.get(fqn)
        if struct is not None and isinstance(struct, StructType):
            topic_entries[fqn] = _struct_to_topic_meta(struct)

    if not topic_entries:
        return None

    # Build the full document
    doc: dict = {
        "# yaml-language-server: $schema": "../schemas/metadata.schema.json",
        "qos_profiles": {
            "TODO_profile_name": {
                "reliability": "RELIABLE",
                "durability": "TRANSIENT_LOCAL",
                "history": {"kind": "KEEP_LAST", "depth": 1},
            },
        },
        "topics": topic_entries,
    }
    return yaml.dump(doc, default_flow_style=False, sort_keys=False, allow_unicode=True)


def generate_metadata_for_idl(
    idl_path: Path,
    output_dir: Path,
    include_dirs: list[Path] | None = None,
) -> Path | None:
    """Parse an IDL file and write a skeleton metadata YAML file next to it
    (in the output directory). Returns the output path, or None if no topics
    were found."""
    yaml_str = _generate_yaml_for_idl(idl_path, include_dirs=include_dirs)
    if yaml_str is None:
        return None

    out_path = output_dir / (idl_path.stem + ".yaml")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(yaml_str)
    return out_path