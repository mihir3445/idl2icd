from pathlib import Path

from idl2icd.config import load_config
from idl2icd.model.ir import ProjectMeta
from idl2icd.model.merge import build_ir
from idl2icd.validation.engine import run_rules
import idl2icd.validation.rules.builtin  # noqa: F401

EXAMPLE_DIR = Path(__file__).parent.parent / "examples" / "robot-fleet"


def test_parses_example_idl_and_merges_metadata():
    cfg = load_config(EXAMPLE_DIR / "idl2icd.yaml")
    project = ProjectMeta(**cfg.project.model_dump())
    ir = build_ir(cfg.resolve_idl_paths(), cfg.resolve_metadata_paths(), project)

    assert "Robot::Telemetry::BatteryStatus" in ir.types
    assert "Robot::Telemetry::BatteryStatus" in ir.topics

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
