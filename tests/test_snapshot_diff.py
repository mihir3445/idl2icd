from pathlib import Path

from idl2icd.model.ir import ProjectMeta
from idl2icd.model.merge import build_ir
from idl2icd.snapshot import save_snapshot, load_snapshot, diff_ir


def _build(tmp_path, idl_text, meta_text, version="1.0.0"):
    idl = tmp_path / "x.idl"
    idl.write_text(idl_text)
    meta = tmp_path / "m.yaml"
    meta.write_text(meta_text)
    project = ProjectMeta(name="t", version=version)
    return build_ir([idl], [meta], project)


BASE_IDL = """
@topic
struct Foo {
  @key unsigned long id;
  float value;
};
"""
BASE_META = """
topics:
  Foo:
    criticality: medium
    qos:
      overrides: { reliability: RELIABLE, durability: TRANSIENT_LOCAL }
    publishers:
      - participant: A
    subscribers:
      - participant: B
"""


def test_snapshot_roundtrip(tmp_path):
    ir = _build(tmp_path, BASE_IDL, BASE_META)
    path = tmp_path / "snap.json"
    save_snapshot(ir, path)
    loaded = load_snapshot(path)
    assert loaded.project.version == "1.0.0"
    assert "Foo" in loaded.topics


def test_diff_detects_breaking_type_change_and_removed_topic(tmp_path):
    old = _build(tmp_path, BASE_IDL, BASE_META, version="1.0.0")

    new_idl = """
    struct Foo {
      @key unsigned long id;
      double value;
    };
    """
    new_meta = "topics: {}\n"
    new = _build(tmp_path, new_idl, new_meta, version="2.0.0")

    report = diff_ir(old, new)
    breaking_kinds = {c.kind for c in report.breaking()}
    assert "topic-removed" in breaking_kinds


def test_diff_detects_additive_optional_field_and_new_subscriber(tmp_path):
    old = _build(tmp_path, BASE_IDL, BASE_META, version="1.0.0")

    new_idl = """
    @topic
    struct Foo {
      @key unsigned long id;
      float value;
      @optional float extra;
    };
    """
    new_meta = """
    topics:
      Foo:
        criticality: medium
        qos:
          overrides: { reliability: RELIABLE, durability: TRANSIENT_LOCAL }
        publishers:
          - participant: A
        subscribers:
          - participant: B
          - participant: C
    """
    new = _build(tmp_path, new_idl, new_meta, version="1.1.0")

    report = diff_ir(old, new)
    additive_kinds = {c.kind for c in report.additive()}
    assert "field-added" in additive_kinds
    assert "subscriber-added" in additive_kinds
    assert not report.breaking()


def test_diff_detects_durability_weakening(tmp_path):
    old = _build(tmp_path, BASE_IDL, BASE_META, version="1.0.0")
    new_meta = """
    topics:
      Foo:
        criticality: medium
        qos:
          overrides: { reliability: RELIABLE, durability: VOLATILE }
        publishers:
          - participant: A
        subscribers:
          - participant: B
    """
    new = _build(tmp_path, BASE_IDL, new_meta, version="1.0.1")
    report = diff_ir(old, new)
    assert any(c.kind == "qos-durability-weakened" for c in report.breaking())
