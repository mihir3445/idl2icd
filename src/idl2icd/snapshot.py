"""Freezes an IRModel to a versioned JSON snapshot, and produces a semantic
diff between two snapshots keyed by fully-qualified name (FQN) — never a
raw file diff, so renames/reordering/comment-only edits don't create noise.
"""
from __future__ import annotations

import json
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


def diff_ir(old: IRModel, new: IRModel) -> ChangeReport:
    report = ChangeReport(version_from=old.project.version, version_to=new.project.version)

    old_topics, new_topics = old.topics, new.topics
    for fqn in sorted(set(old_topics) - set(new_topics)):
        subs = ", ".join(s.participant for s in old_topics[fqn].subscribers) or "none"
        report.changes.append(Change(
            entity=fqn, kind="topic-removed", change_class="breaking",
            detail=f"topic removed (had subscribers: {subs})",
        ))
    for fqn in sorted(set(new_topics) - set(old_topics)):
        report.changes.append(Change(
            entity=fqn, kind="topic-added", change_class="additive",
            detail="new topic",
        ))
    for fqn in sorted(set(old_topics) & set(new_topics)):
        report.changes.extend(_diff_topic(fqn, old_topics[fqn], new_topics[fqn]))

    old_types, new_types = old.types, new.types
    for fqn in sorted(set(old_types) - set(new_types)):
        report.changes.append(Change(
            entity=fqn, kind="type-removed", change_class="breaking",
            detail="type removed",
        ))
    for fqn in sorted(set(old_types) & set(new_types)):
        ot, nt = old_types[fqn], new_types[fqn]
        if ot.kind == "struct" and nt.kind == "struct":
            report.changes.extend(_diff_struct_fields(fqn, ot, nt))

    return report


def _diff_topic(fqn: str, old: Topic, new: Topic) -> list[Change]:
    changes: list[Change] = []

    _DURABILITY_RANK = {"VOLATILE": 0, "TRANSIENT_LOCAL": 1, "TRANSIENT": 2, "PERSISTENT": 3}
    if _DURABILITY_RANK[new.qos.durability] < _DURABILITY_RANK[old.qos.durability]:
        changes.append(Change(
            entity=fqn, kind="qos-durability-weakened", change_class="breaking",
            detail=f"durability weakened: {old.qos.durability} → {new.qos.durability}",
        ))
    if old.qos.reliability == "RELIABLE" and new.qos.reliability == "BEST_EFFORT":
        changes.append(Change(
            entity=fqn, kind="qos-reliability-weakened", change_class="breaking",
            detail="reliability weakened: RELIABLE → BEST_EFFORT",
        ))

    old_subs = {s.participant for s in old.subscribers}
    new_subs = {s.participant for s in new.subscribers}
    for added in sorted(new_subs - old_subs):
        changes.append(Change(fqn, "subscriber-added", "additive", f"new subscriber '{added}'"))
    for removed in sorted(old_subs - new_subs):
        changes.append(Change(fqn, "subscriber-removed", "informational", f"subscriber '{removed}' removed"))

    old_pubs = {p.participant for p in old.publishers}
    new_pubs = {p.participant for p in new.publishers}
    for removed in sorted(old_pubs - new_pubs):
        if not new_pubs:
            changes.append(Change(fqn, "publisher-removed-no-owner", "breaking",
                                   f"publisher '{removed}' removed and no publisher remains"))
        else:
            changes.append(Change(fqn, "publisher-removed", "informational",
                                   f"publisher '{removed}' removed"))

    if old.criticality != new.criticality:
        changes.append(Change(fqn, "criticality-changed", "informational",
                               f"criticality changed: {old.criticality} → {new.criticality}"))
    if old.description != new.description:
        changes.append(Change(fqn, "description-changed", "informational", "description updated"))

    return changes


def _diff_struct_fields(fqn: str, old: StructType, new: StructType) -> list[Change]:
    changes: list[Change] = []
    old_fields = {f.name: f for f in old.fields}
    new_fields = {f.name: f for f in new.fields}

    for name in sorted(set(old_fields) - set(new_fields)):
        changes.append(Change(f"{fqn}.{name}", "field-removed", "breaking", "field removed"))
    for name in sorted(set(new_fields) - set(old_fields)):
        f = new_fields[name]
        cls = "additive" if f.optional else "breaking"
        note = "new optional field" if f.optional else "new REQUIRED field (breaking for existing readers)"
        changes.append(Change(f"{fqn}.{name}", "field-added", cls, note))
    for name in sorted(set(old_fields) & set(new_fields)):
        of, nf = old_fields[name], new_fields[name]
        if of.type_ref.render() != nf.type_ref.render():
            changes.append(Change(
                f"{fqn}.{name}", "field-type-changed", "breaking",
                f"type changed `{of.type_ref.render()}` → `{nf.type_ref.render()}`",
            ))
        if of.is_key != nf.is_key:
            changes.append(Change(
                f"{fqn}.{name}", "key-status-changed", "breaking",
                f"@key changed: {of.is_key} → {nf.is_key}",
            ))
        if of.meta.unit != nf.meta.unit:
            changes.append(Change(
                f"{fqn}.{name}", "unit-changed", "informational",
                f"unit changed: {of.meta.unit} → {nf.meta.unit}",
            ))
    return changes
