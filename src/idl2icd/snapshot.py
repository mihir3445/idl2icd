"""Freezes an IRModel to a versioned JSON snapshot, and produces a semantic
diff between two snapshots keyed by fully-qualified name (FQN) — never a
raw file diff, so renames/reordering/comment-only edits don't create noise.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from idl2icd.model.ir import IRModel, StructType, Topic

ChangeClass = Literal["breaking", "additive", "informational"]


@dataclass
class Change:
    entity: str            # FQN of the topic/type/field affected
    kind: str               # short machine tag, e.g. "field-type-changed"
    change_class: ChangeClass
    detail: str


@dataclass
class ChangeReport:
    version_from: str
    version_to: str
    changes: list[Change] = field(default_factory=list)

    def breaking(self) -> list[Change]:
        return [c for c in self.changes if c.change_class == "breaking"]

    def additive(self) -> list[Change]:
        return [c for c in self.changes if c.change_class == "additive"]

    def informational(self) -> list[Change]:
        return [c for c in self.changes if c.change_class == "informational"]

    def to_markdown(self) -> str:
        lines = [f"## {self.version_from} → {self.version_to}", ""]
        if self.breaking():
            lines.append("### ⚠ Breaking changes")
            for c in self.breaking():
                lines.append(f"- `{c.entity}`: {c.detail}")
            lines.append("")
        if self.additive():
            lines.append("### ✅ Additive changes")
            for c in self.additive():
                lines.append(f"- `{c.entity}`: {c.detail}")
            lines.append("")
        if self.informational():
            lines.append("### ℹ️ Informational")
            for c in self.informational():
                lines.append(f"- `{c.entity}`: {c.detail}")
            lines.append("")
        if not self.changes:
            lines.append("_No changes detected._")
        return "\n".join(lines)


def save_snapshot(ir: IRModel, path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(ir.model_dump_json(indent=2))


def load_snapshot(path: str | Path) -> IRModel:
    return IRModel.model_validate_json(Path(path).read_text())


def _add(changes: list[Change], entity: str, kind: str, change_class: ChangeClass, detail: str) -> None:
    changes.append(Change(entity=entity, kind=kind, change_class=change_class, detail=detail))


def diff_ir(old: IRModel, new: IRModel) -> ChangeReport:
    report = ChangeReport(version_from=old.project.version, version_to=new.project.version)
    old_t, new_t = old.topics, new.topics
    old_ty, new_ty = old.types, new.types

    for fqn in sorted(set(old_t) - set(new_t)):
        subs = ", ".join(s.participant for s in old_t[fqn].subscribers) or "none"
        _add(report.changes, fqn, "topic-removed", "breaking", f"topic removed (had subscribers: {subs})")
    for fqn in sorted(set(new_t) - set(old_t)):
        _add(report.changes, fqn, "topic-added", "additive", "new topic")
    for fqn in sorted(set(old_t) & set(new_t)):
        report.changes.extend(_diff_topic(fqn, old_t[fqn], new_t[fqn]))

    for fqn in sorted(set(old_ty) - set(new_ty)):
        _add(report.changes, fqn, "type-removed", "breaking", "type removed")
    for fqn in sorted(set(new_ty) - set(old_ty)):
        _add(report.changes, fqn, "type-added", "additive", "type added")
    for fqn in sorted(set(old_ty) & set(new_ty)):
        ot, nt = old_ty[fqn], new_ty[fqn]
        if ot.kind != nt.kind:
            _add(report.changes, fqn, "type-kind-changed", "breaking", f"type kind changed: {ot.kind} → {nt.kind}")
        elif ot.kind == nt.kind == "struct":
            report.changes.extend(_diff_struct_fields(fqn, ot, nt))

    return report


def _diff_topic(fqn: str, old: Topic, new: Topic) -> list[Change]:
    changes: list[Change] = []

    def add(kind: str, change_class: ChangeClass, detail: str) -> None:
        _add(changes, fqn, kind, change_class, detail)

    if old.data_type_fqn != new.data_type_fqn:
        add("topic-data-type-changed", "breaking", f"topic data type changed: {old.data_type_fqn} → {new.data_type_fqn}")

    durability_rank = {"VOLATILE": 0, "TRANSIENT_LOCAL": 1, "TRANSIENT": 2, "PERSISTENT": 3}
    if durability_rank[new.qos.durability] < durability_rank[old.qos.durability]:
        add("qos-durability-weakened", "breaking", f"durability weakened: {old.qos.durability} → {new.qos.durability}")
    if old.qos.reliability == "RELIABLE" and new.qos.reliability == "BEST_EFFORT":
        add("qos-reliability-weakened", "breaking", "reliability weakened: RELIABLE → BEST_EFFORT")

    old_subs = {s.participant for s in old.subscribers}
    new_subs = {s.participant for s in new.subscribers}
    for added in sorted(new_subs - old_subs):
        add("subscriber-added", "additive", f"new subscriber '{added}'")
    for removed in sorted(old_subs - new_subs):
        add("subscriber-removed", "informational", f"subscriber '{removed}' removed")

    old_pubs = {p.participant for p in old.publishers}
    new_pubs = {p.participant for p in new.publishers}
    for removed in sorted(old_pubs - new_pubs):
        kind = "publisher-removed-no-owner" if not new_pubs else "publisher-removed"
        cls = "breaking" if not new_pubs else "informational"
        detail = f"publisher '{removed}' removed" + (" and no publisher remains" if not new_pubs else "")
        add(kind, cls, detail)

    if old.criticality != new.criticality:
        add("criticality-changed", "informational", f"criticality changed: {old.criticality} → {new.criticality}")
    if old.description != new.description:
        add("description-changed", "informational", "description updated")

    return changes


def _diff_struct_fields(fqn: str, old: StructType, new: StructType) -> list[Change]:
    changes: list[Change] = []

    def add(entity: str, kind: str, change_class: ChangeClass, detail: str) -> None:
        _add(changes, entity, kind, change_class, detail)

    old_fields = {f.name: f for f in old.fields}
    new_fields = {f.name: f for f in new.fields}

    for name in sorted(set(old_fields) - set(new_fields)):
        add(f"{fqn}.{name}", "field-removed", "breaking", "field removed")
    for name in sorted(set(new_fields) - set(old_fields)):
        cls = "additive" if new_fields[name].optional else "breaking"
        note = "new optional field" if new_fields[name].optional else "new REQUIRED field (breaking for existing readers)"
        add(f"{fqn}.{name}", "field-added", cls, note)
    for name in sorted(set(old_fields) & set(new_fields)):
        of, nf = old_fields[name], new_fields[name]
        if of.type_ref.render() != nf.type_ref.render():
            add(f"{fqn}.{name}", "field-type-changed", "breaking",
                f"type changed `{of.type_ref.render()}` → `{nf.type_ref.render()}`")
        if of.is_key != nf.is_key:
            add(f"{fqn}.{name}", "key-status-changed", "breaking", f"@key changed: {of.is_key} → {nf.is_key}")
        if of.meta.unit != nf.meta.unit:
            add(f"{fqn}.{name}", "unit-changed", "informational",
                f"unit changed: {of.meta.unit} → {nf.meta.unit}")
    return changes
