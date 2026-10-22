"""Tests for skeleton metadata YAML generation and its round-trip back through
build_ir (generated metadata must be valid *and* resolvable)."""

from pathlib import Path

import pytest
import yaml

from idl2icd.metadata_gen import _generate_yaml_for_idl, generate_metadata_for_idl
from idl2icd.model.ir import ProjectMeta
from idl2icd.model.merge import build_ir


def _idl(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "x.idl"
    p.write_text(text)
    return p


TOPIC_IDL = """
/**
 * A battery temperature reading.
 */
@topic
struct BatteryStatus {
  @key unsigned long battery_id;
  float temperature_c;
};
"""


def test_generate_skeleton_for_topic_struct(tmp_path):
    yaml_str = _generate_yaml_for_idl(_idl(tmp_path, TOPIC_IDL))
    assert yaml_str is not None

    data = yaml.safe_load(yaml_str)
    assert data["qos_profiles"]["TODO_profile_name"]["reliability"] == "RELIABLE"
    assert data["qos_profiles"]["TODO_profile_name"]["durability"] == "TRANSIENT_LOCAL"

    topic = data["topics"]["BatteryStatus"]
    assert topic["description"] == "A battery temperature reading."
    assert topic["qos"]["profile"] == "TODO_profile_name"
    assert topic["publishers"][0]["participant"].startswith("TODO")
    assert "battery_id" in topic["fields"]
    assert "temperature_c" in topic["fields"]


def test_no_topic_structs_returns_none_without_all_structs(tmp_path):
    idl = _idl(tmp_path, "struct Plain { long x; };\n")
    assert _generate_yaml_for_idl(idl) is None
    assert _generate_yaml_for_idl(idl, all_structs=True) is not None


def test_all_structs_includes_non_topic_structs(tmp_path):
    yaml_str = _generate_yaml_for_idl(
        _idl(tmp_path, TOPIC_IDL + "struct Helper { long extra; };\n"),
        all_structs=True,
    )
    data = yaml.safe_load(yaml_str)
    assert "Helper" in data["topics"]


def test_write_metadata_file_and_refuse_clobber(tmp_path):
    idl = _idl(tmp_path, TOPIC_IDL)

    out = generate_metadata_for_idl(idl, tmp_path)
    assert out is not None and out.exists()
    assert out.name == "x.yaml"

    with pytest.raises(FileExistsError, match="use --overwrite"):
        generate_metadata_for_idl(idl, tmp_path)

    out2 = generate_metadata_for_idl(idl, tmp_path, overwrite=True)
    assert out2 == out


def test_generated_metadata_round_trips_through_build_ir(tmp_path):
    idl = _idl(tmp_path, TOPIC_IDL)
    generated = generate_metadata_for_idl(idl, tmp_path)
    assert generated is not None

    ir = build_ir([idl], [generated], ProjectMeta(name="t", version="1.0.0"))

    topic = ir.topics["BatteryStatus"]
    assert topic.description == "A battery temperature reading."
    assert topic.qos.reliability == "RELIABLE"  # resolved from TODO_profile_name
    assert topic.qos.durability == "TRANSIENT_LOCAL"
    assert topic.qos.history.kind == "KEEP_LAST"

    battery_id = ir.types["BatteryStatus"].fields[0]
    assert battery_id.meta.description  # auto-detected hint is carried as a description
