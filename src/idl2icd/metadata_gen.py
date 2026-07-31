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

    # Placeholder sections. criticality is omitted by default (it's optional
    # in the schema and has a Literal constraint); the user can add it when
    # they know the actual value.
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


def _generate_yaml_for_idl(
    idl_path: Path,
    include_dirs: list[Path] | None = None,
    all_structs: bool = False,
) -> str | None:
    """Parse a single IDL file and return a YAML string with skeleton metadata.

    If *all_structs* is True, every struct in the file gets a metadata entry
    (even without @topic). Otherwise, only @topic-annotated structs are included.
    Returns None if no structs qualify.
    """
    parsed = parse_idl_file(idl_path, include_dirs=include_dirs)

    # Determine which FQNs to generate entries for.
    if all_structs:
        candidates = sorted(
            fqn for fqn, t in parsed.types.items() if isinstance(t, StructType)
        )
    else:
        candidates = sorted(parsed.topic_hints)

    if not candidates:
        return None

    # Collect struct metadata entries
    topic_entries: dict[str, dict] = {}
    for fqn in candidates:
        struct = parsed.types.get(fqn)
        if struct is not None and isinstance(struct, StructType):
            topic_entries[fqn] = _struct_to_topic_meta(struct)

    if not topic_entries:
        return None

    qos_profiles: dict = {
        "TODO_profile_name": {
            "reliability": "RELIABLE",
            "durability": "TRANSIENT_LOCAL",
            "history": {"kind": "KEEP_LAST", "depth": 1},
        },
    }

    doc: dict = {
        "qos_profiles": qos_profiles,
        "topics": topic_entries,
    }
    return yaml.dump(doc, default_flow_style=False, sort_keys=False, allow_unicode=True)


def generate_metadata_for_idl(
    idl_path: Path,
    output_dir: Path,
    include_dirs: list[Path] | None = None,
    all_structs: bool = False,
) -> Path | None:
    """Parse an IDL file and write a skeleton metadata YAML file next to it
    (in the output directory). Returns the output path, or None if no structs
    qualify for metadata generation."""
    yaml_str = _generate_yaml_for_idl(idl_path, include_dirs=include_dirs, all_structs=all_structs)
    if yaml_str is None:
        return None

    out_path = output_dir / (idl_path.stem + ".yaml")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(yaml_str)
    return out_path
