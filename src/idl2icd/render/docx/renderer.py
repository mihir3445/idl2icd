"""Renders the IR to a Word (.docx) document via python-docx.

Unlike the PDF renderer, this doesn't reuse the site's HTML/CSS — python-docx
has no HTML/templating layer, so the document is built imperatively
(heading-by-heading, table-by-table). Mermaid diagrams aren't rendered here
either (same limitation as PDF): the Mermaid source is included as a
monospace text block with a note, until SVG/PNG pre-rendering via mmdc is
wired in (see ROADMAP.md).
"""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.shared import Pt, Cm, RGBColor
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

from idl2icd.model.ir import IRModel, Diagnostic
from idl2icd.diagrams.pubsub_graph import generate_pubsub_graph

_CRIT_COLOR = {
    "safety": RGBColor(0xD1, 0x49, 0x5B),
    "high": RGBColor(0xD1, 0x49, 0x5B),
    "medium": RGBColor(0xE2, 0xA5, 0x3A),
    "low": RGBColor(0x3A, 0xA7, 0x6D),
}
_HEADER_SHADE = "F0F2F5"


def _shade_cell(cell, hex_color: str):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tc_pr.append(shd)


def _set_col_widths(table, widths_cm: list[float]):
    table.autofit = False
    for row in table.rows:
        for cell, w in zip(row.cells, widths_cm):
            cell.width = Cm(w)


def _add_kv_table(doc, rows: list[tuple[str, str]], widths=(4.0, 10.0)):
    table = doc.add_table(rows=0, cols=2)
    table.style = "Table Grid"
    for label, value in rows:
        row = table.add_row()
        row.cells[0].text = label
        row.cells[0].paragraphs[0].runs[0].bold = True
        row.cells[1].text = str(value)
        _shade_cell(row.cells[0], _HEADER_SHADE)
    _set_col_widths(table, list(widths))
    return table


def _add_grid_table(doc, headers: list[str], rows: list[list[str]], widths: list[float]):
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = h
        cell.paragraphs[0].runs[0].bold = True
        _shade_cell(cell, _HEADER_SHADE)
    for r in rows:
        row = table.add_row()
        for i, val in enumerate(r):
            row.cells[i].text = str(val) if val is not None else ""
    if rows == []:
        row = table.add_row()
        row.cells[0].text = "(none declared)"
    _set_col_widths(table, widths)
    return table


def _fix_zoom_setting(doc: Document) -> None:
    """python-docx's blank template emits <w:zoom> without the required
    w:percent attribute, which fails strict OOXML schema validation (though
    Word/LibreOffice both open it fine). Patch it so the output is
    unambiguously schema-valid, not just "happens to render"."""
    settings = doc.settings.element
    zoom = settings.find(qn("w:zoom"))
    if zoom is None:
        zoom = OxmlElement("w:zoom")
        settings.insert(0, zoom)
    zoom.set(qn("w:percent"), "100")


def render_docx(ir: IRModel, diagnostics: list[Diagnostic], out_path: Path, direction: str = "LR") -> None:
    doc = Document()
    _fix_zoom_setting(doc)

    # --- base style tweaks ---
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(10)

    # --- cover page ---
    title = doc.add_heading(ir.project.name, level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub.add_run(f"{ir.project.organization or ''}\nVersion {ir.project.version}").italic = True
    doc.add_page_break()

    # --- topic index ---
    doc.add_heading("Topic Index", level=1)
    all_topics = sorted(ir.topics.values(), key=lambda t: t.fqn)
    index_rows = [
        [t.fqn, t.criticality or "-", t.qos.reliability, t.qos.durability,
         str(len(t.publishers)), str(len(t.subscribers))]
        for t in all_topics
    ]
    _add_grid_table(
        doc,
        headers=["Topic", "Criticality", "Reliability", "Durability", "Pubs", "Subs"],
        rows=index_rows,
        widths=[6.0, 2.5, 2.5, 2.5, 1.5, 1.5],
    )

    # --- validation diagnostics ---
    if diagnostics:
        doc.add_heading("Validation Results", level=1)
        for d in diagnostics:
            p = doc.add_paragraph(style="List Bullet")
            run = p.add_run(f"[{d.severity.upper()}] {d.rule}: ")
            run.bold = True
            if d.severity == "error":
                run.font.color.rgb = RGBColor(0xD1, 0x49, 0x5B)
            elif d.severity == "warn":
                run.font.color.rgb = RGBColor(0xB8, 0x86, 0x0B)
            p.add_run(d.message)

    # --- pub/sub topology (Mermaid source fallback, same limitation as PDF) ---
    doc.add_heading("Publish/Subscribe Topology", level=1)
    note = doc.add_paragraph()
    note.add_run(
        "Diagram omitted in this Word export (Mermaid pre-rendering to an image "
        "is not yet wired in this build — see the website output for the "
        "interactive version). Mermaid source below:"
    ).italic = True
    mermaid_src = generate_pubsub_graph(ir, direction=direction)
    mono = doc.add_paragraph()
    mono_run = mono.add_run(mermaid_src)
    mono_run.font.name = "Consolas"
    mono_run.font.size = Pt(8)

    # --- per-topic sections ---
    for topic in all_topics:
        doc.add_page_break()
        h = doc.add_heading(topic.fqn, level=1)
        if topic.criticality:
            badge = doc.add_paragraph()
            run = badge.add_run(f"  {topic.criticality.upper()}  ")
            run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            run.bold = True
            # crude "badge" via character shading isn't supported per-run in
            # python-docx without lower-level XML; color the text instead.
            run.font.color.rgb = _CRIT_COLOR.get(topic.criticality, RGBColor(0x66, 0x66, 0x66))

        doc.add_paragraph(topic.description or "No description provided.")

        doc.add_heading("QoS", level=2)
        qos_rows = [
            ("Reliability", topic.qos.reliability),
            ("Durability", topic.qos.durability),
            ("History", f"{topic.qos.history.kind} (depth {topic.qos.history.depth})"),
        ]
        if topic.qos.deadline:
            qos_rows.append(("Deadline", f"{topic.qos.deadline.period_ms} ms"))
        if topic.rate:
            qos_rows.append(("Rate", f"nominal {topic.rate.nominal_hz} Hz / max {topic.rate.max_hz} Hz"))
        _add_kv_table(doc, qos_rows)

        doc.add_heading("Publishers", level=2)
        _add_grid_table(
            doc, headers=["Participant", "Instance count", "Source"],
            rows=[[p.participant, p.instance_count or "", p.source or ""] for p in topic.publishers],
            widths=[5.0, 4.0, 5.0],
        )

        doc.add_heading("Subscribers", level=2)
        _add_grid_table(
            doc, headers=["Participant", "Notes"],
            rows=[[s.participant, s.notes or ""] for s in topic.subscribers],
            widths=[5.0, 9.0],
        )

        data_type = ir.types.get(topic.data_type_fqn)
        doc.add_heading(f"Data Type: {topic.data_type_fqn}", level=2)
        if data_type and data_type.kind == "struct":
            field_rows = [
                [f.name, f.type_ref.render(), "yes" if f.is_key else "",
                 f.meta.unit or "", f.meta.description or f.doc or ""]
                for f in data_type.fields
            ]
        else:
            field_rows = []
        _add_grid_table(
            doc, headers=["Field", "Type", "Key", "Unit", "Description"],
            rows=field_rows,
            widths=[3.0, 3.0, 1.2, 2.0, 6.8],
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out_path))
