from __future__ import annotations

from idl2icd.model.ir import IRModel


def _safe_id(name: str) -> str:
    return "n_" + "".join(c if c.isalnum() else "_" for c in name)


def generate_pubsub_graph(
    ir: IRModel,
    direction: str = "LR",
    show_topic_qos: bool = False,
    show_topic_rate: bool = False,
) -> str:
    lines = [f"flowchart {direction}"]
    lines.append("    classDef participant fill:#f8fafc,stroke:#0f172a,stroke-width:1px")
    lines.append("    classDef topic fill:#eff6ff,stroke:#1d4ed8,stroke-width:1px")
    lines.append("    classDef critical fill:#dc2626,stroke:#991b1b,stroke-width:1px,color:#fff")
    lines.append("    classDef safety fill:#b91c1c,stroke:#7f1d1d,stroke-width:1px,color:#fff")

    participants = set()
    for topic in ir.topics.values():
        for ep in topic.publishers:
            participants.add(ep.participant)
        for ep in topic.subscribers:
            participants.add(ep.participant)

    if participants:
        lines.append("    subgraph Participants")
        for p in sorted(participants):
            pid = _safe_id(p)
            lines.append(f"        {pid}[{p}]")
            lines.append(f"        class {pid} participant")
        lines.append("    end")

    for topic in ir.topics.values():
        tid = _safe_id(topic.fqn)
        short_name = topic.fqn.split("::")[-1]
        label = short_name.replace('"', '\\"')
        segments = []
        if show_topic_qos:
            qos_values = []
            if topic.qos.reliability:
                qos_values.append(topic.qos.reliability.replace("_", " ").title())
            if topic.qos.durability:
                qos_values.append(topic.qos.durability.replace("_", " ").title())
            if qos_values:
                segments.append("QOS: " + ", ".join(qos_values))
        if show_topic_rate and topic.rate:
            nominal = f"{topic.rate.nominal_hz:g}Hz" if topic.rate.nominal_hz is not None else "?Hz"
            rate_str = nominal
            if topic.rate.max_hz is not None:
                rate_str = f"{nominal} (max {topic.rate.max_hz:g}Hz)"
            segments.append("Rate: " + rate_str)
        if segments:
            label += "<br>[" + " | ".join(segments) + "]"

        lines.append(f'    {tid}(("{label}"))')
        lines.append(f"    class {tid} topic")
        if topic.criticality == "high":
            lines.append(f"    class {tid} critical")
        elif topic.criticality == "safety":
            lines.append(f"    class {tid} safety")

        for ep in topic.publishers:
            lines.append(f"    {_safe_id(ep.participant)} -->|pub| {tid}")
        for ep in topic.subscribers:
            lines.append(f"    {tid} -->|sub| {_safe_id(ep.participant)}")

    return "\n".join(lines)


def _struct_class_lines(struct) -> list[str]:
    """Generate Mermaid classDiagram lines for a single struct (no header)."""
    short = struct.fqn.split("::")[-1]
    lines = [f"    class {short} {{"]
    for f in struct.fields:
        key_marker = "+" if f.is_key else " "
        lines.append(f"        {key_marker}{f.type_ref.render()} {f.name}")
    lines.append("    }")
    return lines


def generate_type_diagram_for_struct(struct) -> str:
    """Generate a complete Mermaid classDiagram for a single struct type.

    This is the lightweight helper callers should use when they only need a
    diagram for one type — no IRModel construction or re-validation required.
    """
    return "\n".join(["classDiagram", *_struct_class_lines(struct)])


def generate_type_diagram(ir: IRModel) -> str:
    """Generate a Mermaid classDiagram for all struct types in the IR."""
    lines = ["classDiagram"]
    for t in ir.types.values():
        if t.kind != "struct":
            continue
        lines.extend(_struct_class_lines(t))
    return "\n".join(lines)
