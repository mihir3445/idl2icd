from __future__ import annotations

import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from idl2icd.diagrams.pubsub_graph import (
    generate_pubsub_graph,
    generate_type_diagram_for_struct,
)
from idl2icd.model.ir import AnyType, Diagnostic, IRModel
from idl2icd.render.helpers import struct_fields_context

THEME_DIR = Path(__file__).parent.parent.parent.parent.parent / "themes" / "default"


def _prepare_type_context(type_: AnyType, ir: IRModel) -> dict:
    return {
        "fqn": type_.fqn,
        "kind": type_.kind,
        "doc": type_.doc,
        "fields": struct_fields_context(type_, ir) if type_.kind == "struct" else [],
        "enum_values": getattr(type_, "values", None) or [],
        "discriminator": getattr(type_, "discriminator", None),
        "cases": getattr(type_, "cases", None) or [],
    }


def render_site(
    ir: IRModel,
    diagnostics: list[Diagnostic],
    out_dir: Path,
    direction: str = "LR",
    show_topic_qos: bool = False,
    show_topic_rate: bool = False,
):
    templates_dir = THEME_DIR / "templates"
    env = Environment(loader=FileSystemLoader(str(templates_dir)), autoescape=True)

    out_dir.mkdir(parents=True, exist_ok=True)
    static_src = THEME_DIR / "static"
    static_dst = out_dir / "static"
    if static_dst.exists():
        shutil.rmtree(static_dst)
    shutil.copytree(static_src, static_dst)

    all_topics = sorted(ir.topics.values(), key=lambda t: t.fqn)
    pubsub_graph = generate_pubsub_graph(
        ir,
        direction=direction,
        show_topic_qos=show_topic_qos,
        show_topic_rate=show_topic_rate,
        # The pubsub graph is rendered on the site-root index page, so topic
        # links resolve relative to the root: "topics/<fqn>.html".
        topic_base_path="topics/",
    )

    index_tpl = env.get_template("index.html.j2")
    (out_dir / "index.html").write_text(index_tpl.render(
        project=ir.project, all_topics=all_topics, pubsub_graph=pubsub_graph,
        diagnostics=diagnostics, asset_prefix="",
    ))

    topics_dir = out_dir / "topics"
    topics_dir.mkdir(exist_ok=True)
    topic_tpl = env.get_template("topic.html.j2")
    types_dir = out_dir / "types"
    types_dir.mkdir(exist_ok=True)
    type_tpl = env.get_template("type.html.j2")

    for topic in all_topics:
        data_type = ir.types.get(topic.data_type_fqn)
        is_struct = data_type is not None and data_type.kind == "struct"
        type_diagram = generate_type_diagram_for_struct(data_type) if is_struct else "classDiagram"
        html = topic_tpl.render(
            project=ir.project, topic=topic,
            data_type={"fqn": data_type.fqn, "fields": struct_fields_context(data_type, ir)} if is_struct
            else {"fqn": "?", "fields": []},
            type_diagram=type_diagram, all_topics=all_topics, asset_prefix="../",
        )
        fname = topic.fqn.replace("::", ".") + ".html"
        (topics_dir / fname).write_text(html)

    for type_ in ir.types.values():
        type_html = type_tpl.render(
            project=ir.project,
            type_=_prepare_type_context(type_, ir),
            all_topics=all_topics,
            asset_prefix="../",
        )
        fname = type_.fqn.replace("::", ".") + ".html"
        (types_dir / fname).write_text(type_html)
