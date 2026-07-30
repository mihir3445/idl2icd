from __future__ import annotations

from idl2icd.model.ir import IRModel


def _safe_id(name: str) -> str:
    return "n_" + "".join(c if c.isalnum() else "_" for c in name)


def generate_pubsub_graph(ir: IRModel, direction: str = "LR") -> str:
    lines = [f"flowchart {direction}"]
    participants = set()
    for topic in ir.topics.values():
        for ep in topic.publishers:
            participants.add(ep.participant)
        for ep in topic.subscribers:
            participants.add(ep.participant)

    if participants:
        lines.append("    subgraph Participants")
        for p in sorted(participants):
            lines.append(f"        {_safe_id(p)}[{p}]")
        lines.append("    end")

    for topic in ir.topics.values():
        tid = _safe_id(topic.fqn)
        short_name = topic.fqn.split("::")[-1]
        lines.append(f"    {tid}(({short_name}))")
        for ep in topic.publishers:
            lines.append(f"    {_safe_id(ep.participant)} -->|pub| {tid}")
        for ep in topic.subscribers:
            lines.append(f"    {tid} -->|sub| {_safe_id(ep.participant)}")
        if topic.criticality in ("high", "safety"):
            lines.append(f"    style {tid} fill:#d1495b,color:#fff")

    return "\n".join(lines)


def generate_type_diagram(ir: IRModel) -> str:
    lines = ["classDiagram"]
    for t in ir.types.values():
        if t.kind != "struct":
            continue
        short = t.fqn.split("::")[-1]
        lines.append(f"    class {short} {{")
        for f in t.fields:
            key_marker = "+" if f.is_key else " "
            lines.append(f"        {key_marker}{f.type_ref.render()} {f.name}")
        lines.append("    }")
    return "\n".join(lines)
