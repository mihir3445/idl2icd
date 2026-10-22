"""Validation rule engine behaviors: unit detection recursion into containers,
severity override control, and the built-in rule registration."""

from pathlib import Path

from idl2icd.model.ir import ProjectMeta
from idl2icd.model.merge import build_ir
from idl2icd.validation.engine import run_rules


def _run(tmp_path: Path, idl_text: str, meta_text: str | None = None):
    idl = tmp_path / "x.idl"
    idl.write_text(idl_text)
    meta = tmp_path / "m.yaml"
    if meta_text is not None:
        meta.write_text(meta_text)
    return build_ir(
        [idl],
        [meta] if meta_text is not None else [],
        ProjectMeta(name="t", version="1.0.0"),
    )


def test_missing_units_flags_top_level_numeric_field(tmp_path):
    ir = _run(tmp_path, "struct S { float speed; };")
    messages = [d.message for d in run_rules(ir) if d.rule == "missing-units"]
    assert any("S.speed" in m for m in messages)


def test_missing_units_recurses_into_sequences_and_arrays(tmp_path):
    ir = _run(tmp_path, "struct S { sequence<double> samples; float matrix[4][4]; };")
    messages = [d.message for d in run_rules(ir) if d.rule == "missing-units"]
    assert any("S.samples" in m for m in messages)
    assert any("S.matrix" in m for m in messages)


def test_missing_units_ignores_non_numeric_sequences(tmp_path):
    ir = _run(tmp_path, "struct S { sequence<string<16>, 8> names; };")
    assert not any(d.rule == "missing-units" for d in run_rules(ir))


def test_documented_unit_suppresses_missing_units(tmp_path):
    ir = _run(
        tmp_path,
        "struct S { sequence<double> samples; };",
        "topics:\n  S:\n    fields:\n      samples:\n        unit: Hz\n",
    )
    assert not any(d.rule == "missing-units" for d in run_rules(ir))


def test_rule_can_be_disabled_per_config(tmp_path):
    ir = _run(tmp_path, "struct S { float speed; };")
    diags = run_rules(ir, severities={"missing-units": "off"})
    assert not any(d.rule == "missing-units" for d in diags)


def test_rule_severity_can_be_overridden(tmp_path):
    ir = _run(tmp_path, "struct S { float speed; };")
    diags = run_rules(ir, severities={"missing-units": "info"})
    units = [d for d in diags if d.rule == "missing-units"]
    assert units and all(d.severity == "info" for d in units)


def test_builtin_rules_registered_without_explicit_import(tmp_path):
    # Regression: `run_rules` must work with zero side-effect imports, because
    # importing the validation package registers the built-in rules.
    ir = _run(
        tmp_path,
        "@topic\nstruct S { float speed; };\n",
        "topics:\n  S:\n    criticality: safety\n",
    )
    rule_ids = {d.rule for d in run_rules(ir)}
    assert {"missing-units", "missing-owner", "undocumented-topic", "qos-compatibility"} <= rule_ids
