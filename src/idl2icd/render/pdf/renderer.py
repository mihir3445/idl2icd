from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from idl2icd.diagrams.pubsub_graph import generate_pubsub_graph
from idl2icd.model.ir import Diagnostic, IRModel
from idl2icd.render.helpers import format_type_ref

THEME_DIR = Path(__file__).parent.parent.parent.parent.parent / "themes" / "default"


def render_pdf(
    ir: IRModel,
    diagnostics: list[Diagnostic],
    out_path: Path,
    direction: str = "LR",
    show_topic_qos: bool = False,
    show_topic_rate: bool = False,
) -> None:
    try:
        from weasyprint import HTML
    except ImportError as exc:
        raise ImportError(
            "PDF export requires the optional 'pdf' extra: pip install 'idl2icd[pdf]'"
        ) from exc

    env = Environment(loader=FileSystemLoader(str(THEME_DIR / "templates")))
    tpl = env.get_template("pdf_document.html.j2")

    all_topics = []
    for topic in sorted(ir.topics.values(), key=lambda t: t.fqn):
        data_type = ir.types.get(topic.data_type_fqn)
        fields = []
        if data_type and data_type.kind == "struct":
            for f in data_type.fields:
                fields.append({
                    "name": f.name, "is_key": f.is_key,
                    "type_ref_render": format_type_ref(f.type_ref, ir),
                    "meta": f.meta, "doc": f.doc,
                })
        all_topics.append({
            **topic.model_dump(),
            "data_type": {"fqn": data_type.fqn if data_type else "?", "fields": fields},
        })

    print_css = (THEME_DIR / "static" / "css" / "print.css").read_text()

    html_str = tpl.render(
        project=ir.project,
        all_topics=all_topics,
        diagnostics=diagnostics,
        pubsub_graph=generate_pubsub_graph(
            ir,
            direction=direction,
            show_topic_qos=show_topic_qos,
            show_topic_rate=show_topic_rate,
        ),
        print_css=print_css,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html_str, base_url=str(THEME_DIR)).write_pdf(str(out_path))
