from pathlib import Path

import pytest

import idl2icd.validation.rules.builtin  # noqa: F401
from idl2icd.config import load_config
from idl2icd.model.ir import ProjectMeta
from idl2icd.model.merge import build_ir
from idl2icd.validation.engine import run_rules

EXAMPLE_DIR = Path(__file__).parent.parent / "examples" / "robot-fleet"


def test_parses_example_idl_and_merges_metadata():
    cfg = load_config(EXAMPLE_DIR / "idl2icd.yaml")
    project = ProjectMeta(**cfg.project.model_dump())
    ir = build_ir(
        cfg.resolve_idl_paths(),
        cfg.resolve_metadata_paths(),
        project,
        include_dirs=cfg.resolve_include_paths(),
    )

    assert "Robot::Telemetry::BatteryStatus" in ir.types
    assert "Robot::Telemetry::BatteryStatus" in ir.topics
    assert "Robot::Telemetry::SharedId" in ir.types
    assert "Robot::Telemetry::ChannelState" in ir.types

    battery = ir.topics["Robot::Telemetry::BatteryStatus"]
    assert battery.criticality == "high"
    assert battery.qos.reliability == "RELIABLE"
    assert battery.qos.durability == "TRANSIENT_LOCAL"
    assert len(battery.publishers) == 1
    assert len(battery.subscribers) == 2

    battery_type = ir.types["Robot::Telemetry::BatteryStatus"]
    soc_field = next(f for f in battery_type.fields if f.name == "state_of_charge_pct")
    assert soc_field.meta.unit == "percent"
    robot_id_field = next(f for f in battery_type.fields if f.name == "robot_id")
    assert robot_id_field.is_key is True


def test_qos_compatibility_rule_flags_bad_pairing(tmp_path):
    idl = tmp_path / "bad.idl"
    idl.write_text("""
    @topic
    struct Unsafe {
      @key unsigned long id;
      float value;
    };
    """)
    meta = tmp_path / "meta.yaml"
    meta.write_text("""
    topics:
      Unsafe:
        criticality: safety
        qos:
          overrides:
            reliability: BEST_EFFORT
    """)
    project = ProjectMeta(name="t", version="0.0.1")
    ir = build_ir([idl], [meta], project)
    diags = run_rules(ir)
    assert any(d.rule == "qos-compatibility" and d.severity == "error" for d in diags)


def test_dangling_topic_ref_is_reported(tmp_path):
    idl = tmp_path / "empty.idl"
    idl.write_text("module M { struct Foo { long x; }; };")
    meta = tmp_path / "meta.yaml"
    meta.write_text("topics:\n  M::DoesNotExist:\n    description: 'oops'\n")
    project = ProjectMeta(name="t", version="0.0.1")
    ir = build_ir([idl], [meta], project)
    assert any(d.rule == "dangling-topic-ref" for d in ir.diagnostics)


def test_preprocessor_guards_are_ignored_for_idl_parsing(tmp_path):
    idl = tmp_path / "guarded.idl"
    idl.write_text("""
    #ifndef XXX
    #define XXX
    module M {
      struct Foo {
        long x;
      };
    };
    #endif // XXX
    """)

    project = ProjectMeta(name="t", version="0.0.1")
    ir = build_ir([idl], [], project)

    assert "M::Foo" in ir.types


def test_nested_include_paths_are_resolved_from_base_dir(tmp_path):
    base = tmp_path / "base"
    include_root = base / "idl"
    nested_dir = include_root / "nested"
    nested_dir.mkdir(parents=True)

    shared = include_root / "common.idl"
    shared.write_text("module Shared { struct Common { long value; }; };\n")

    top = nested_dir / "top.idl"
    top.write_text("#include \"../common.idl\"\nmodule M { struct Foo { Shared::Common value; }; };\n")

    project = ProjectMeta(name="t", version="0.0.1")
    ir = build_ir([top], [], project, include_dirs=[include_root])

    assert "Shared::Common" in ir.types
    assert "M::Foo" in ir.types


def test_struct_inheritance_is_accepted(tmp_path):
    idl = tmp_path / "inheritance.idl"
    idl.write_text("""
    struct Base {
      long x;
    };

    struct Child : Base {
      long y;
    }
    """)

    project = ProjectMeta(name="t", version="0.0.1")
    ir = build_ir([idl], [], project)

    assert "Base" in ir.types
    assert "Child" in ir.types


def test_enum_member_initializers_are_accepted(tmp_path):
    idl = tmp_path / "enum-init.idl"
    idl.write_text("""
    enum Foo {
      UNKNOWN = 0,
      ACTIVE = 1,
    };
    """)

    project = ProjectMeta(name="t", version="0.0.1")
    ir = build_ir([idl], [], project)

    enum = ir.types["Foo"]
    assert enum.values == ["UNKNOWN", "ACTIVE"]


def test_typedef_enum_with_initializers_is_accepted(tmp_path):
    idl = tmp_path / "typedef-enum.idl"
    idl.write_text("""
    typedef enum {
      UNKNOWN = 0,
      ACTIVE = 1,
    } UtmCoordinate3d;
    """)

    project = ProjectMeta(name="t", version="0.0.1")
    ir = build_ir([idl], [], project)

    assert "UtmCoordinate3d" in ir.types
    assert ir.types["UtmCoordinate3d"].values == ["UNKNOWN", "ACTIVE"]


def test_union_switch_on_named_enum_is_accepted(tmp_path):
    idl = tmp_path / "union-switch.idl"
    idl.write_text("""
    enum CoordType {
      UTM,
      MRGS,
    };

    union Cood switch(CoordType)
    {
      case UTM:
        UtmCoordinate3d utm_coordinate;

      case MRGS:
        MGRSCoordinate3d mgrs_coordinate;
    };
    """)

    project = ProjectMeta(name="t", version="0.0.1")
    ir = build_ir([idl], [], project)

    assert "CoordType" in ir.types
    assert "Cood" in ir.types
    union = ir.types["Cood"]
    assert [case.labels for case in union.cases] == [["UTM"], ["MRGS"]]


def test_invalid_metadata_yaml_is_reported(tmp_path):
    idl = tmp_path / "bad.idl"
    idl.write_text("""
    @topic
    struct Unsafe {
      @key unsigned long id;
      float value;
    };
    """)
    meta = tmp_path / "meta.yaml"
    meta.write_text("topics: [oops")
    project = ProjectMeta(name="t", version="0.0.1")

    with pytest.raises(ValueError, match="Failed to parse metadata YAML"):
        build_ir([idl], [meta], project)
