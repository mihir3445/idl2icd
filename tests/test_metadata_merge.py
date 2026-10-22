"""Unit + integration tests for the metadata -> IR merge: QoS resolution order
(profile first, then overrides), field-level metadata, and topic promotion."""

from pathlib import Path

import pytest

from idl2icd.model.ir import ProjectMeta
from idl2icd.model.merge import _resolve_qos, build_ir
from idl2icd.model.metadata_schema import MetaQoS, MetaQoSOverride


def _build(tmp_path: Path, idl_text: str, meta_text: str):
    idl = tmp_path / "x.idl"
    idl.write_text(idl_text)
    meta = tmp_path / "m.yaml"
    meta.write_text(meta_text)
    return build_ir([idl], [meta], ProjectMeta(name="t", version="1.0.0"))


IDL = """
@topic
struct Foo {
  long value;
};
"""


# --- direct unit tests of the QoS resolution order ---


def test_qos_defaults_when_no_metadata():
    qos = _resolve_qos(None, {})
    assert qos.reliability == "BEST_EFFORT"
    assert qos.durability == "VOLATILE"
    assert qos.history.kind == "KEEP_LAST"


def test_qos_profile_is_applied():
    profiles = {"telemetry": MetaQoSOverride(reliability="RELIABLE", durability="TRANSIENT_LOCAL")}
    qos = _resolve_qos(MetaQoS(profile="telemetry"), profiles)
    assert qos.reliability == "RELIABLE"
    assert qos.durability == "TRANSIENT_LOCAL"


def test_qos_overrides_win_over_profile():
    profiles = {"telemetry": MetaQoSOverride(reliability="RELIABLE", durability="TRANSIENT_LOCAL")}
    qos = _resolve_qos(
        MetaQoS(
            profile="telemetry",
            overrides=MetaQoSOverride(durability="PERSISTENT"),
        ),
        profiles,
    )
    assert qos.reliability == "RELIABLE"  # from the profile
    assert qos.durability == "PERSISTENT"  # overridden


def test_qos_unknown_profile_is_ignored():
    qos = _resolve_qos(MetaQoS(profile="does-not-exist"), {})
    assert qos.reliability == "BEST_EFFORT"
    assert qos.durability == "VOLATILE"


def test_qos_history_deadline_passthrough():
    profiles = {
        "d": MetaQoSOverride(
            history={"kind": "KEEP_ALL", "depth": 50},
            deadline={"period_ms": 100.0},
        ),
    }
    qos = _resolve_qos(MetaQoS(profile="d"), profiles)
    assert qos.history.kind == "KEEP_ALL"
    assert qos.history.depth == 50
    assert qos.deadline is not None and qos.deadline.period_ms == 100.0


# --- integration tests through build_ir ---


def test_field_metadata_merges_onto_struct_fields(tmp_path):
    ir = _build(
        tmp_path,
        IDL,
        """
    topics:
      Foo:
        fields:
          value:
            unit: percent
            precision: 2
    """,
    )

    field = ir.types["Foo"].fields[0]
    assert field.meta.unit == "percent"
    assert field.meta.precision == 2
    assert field.meta.range is None  # untouched None field stays None


def test_metadata_promotes_plain_struct_to_topic(tmp_path):
    idl = "struct Foo { long value; };\n"
    ir = _build(
        tmp_path,
        idl,
        """
    topics:
      Foo:
        description: Promoted by metadata.
        publishers:
          - participant: SensorNode
    """,
    )

    assert "Foo" in ir.topics
    assert ir.topics["Foo"].description == "Promoted by metadata."
    assert ir.topics["Foo"].publishers[0].participant == "SensorNode"


def test_later_metadata_file_wins_for_same_topic(tmp_path):
    idl = tmp_path / "x.idl"
    idl.write_text(IDL)
    meta1 = tmp_path / "m1.yaml"
    meta1.write_text("topics:\n  Foo:\n    description: first\n")
    meta2 = tmp_path / "m2.yaml"
    meta2.write_text("topics:\n  Foo:\n    description: second\n")

    ir = build_ir([idl], [meta1, meta2], ProjectMeta(name="t", version="1.0.0"))
    assert ir.topics["Foo"].description == "second"


def test_topic_without_strict_qos_overrides_falls_back_to_defaults(tmp_path):
    ir = _build(
        tmp_path,
        IDL,
        """
    topics:
      Foo:
        description: just a description
    """,
    )

    topic = ir.topics["Foo"]
    assert topic.qos.reliability == "BEST_EFFORT"
    assert topic.rate is None
    assert topic.criticality is None


def test_invalid_qos_literal_is_rejected_by_schema(tmp_path):
    idl = tmp_path / "x.idl"
    idl.write_text(IDL)
    meta = tmp_path / "m.yaml"
    meta.write_text("topics:\n  Foo:\n    qos:\n      overrides:\n        reliability: SOMETIMES\n")

    with pytest.raises(ValueError, match="Invalid metadata file"):
        build_ir([idl], [meta], ProjectMeta(name="t", version="1.0.0"))
