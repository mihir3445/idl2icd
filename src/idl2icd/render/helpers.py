from __future__ import annotations

from markupsafe import Markup, escape

from idl2icd.model.ir import IRModel, StructType, TypeRef


def _render_named_type_link(type_ref: TypeRef, ir: IRModel, *, rendered: str) -> Markup:
    target = ir.types.get(type_ref.name)
    if target is None:
        return Markup(f"<code>{escape(rendered)}</code>")

    href = escape(f"../types/{target.fqn.replace('::', '.')}.html")
    return Markup(f'<a href="{href}"><code>{escape(rendered)}</code></a>')


def _render_type_ref_markup(type_ref: TypeRef, ir: IRModel) -> Markup:
    rendered = type_ref.render()
    if type_ref.kind == "named":
        return _render_named_type_link(type_ref, ir, rendered=rendered)

    if type_ref.kind in {"sequence", "array"} and type_ref.element is not None:
        element = _render_type_ref_markup(type_ref.element, ir)
        if type_ref.kind == "sequence":
            bound = f", {type_ref.bound}" if type_ref.bound is not None else ""
            return Markup(f"<code>sequence&lt;{element}{escape(bound)}&gt;</code>")

        return Markup(f"<code>{escape(type_ref.render())}</code>")

    return Markup(f"<code>{escape(rendered)}</code>")


def format_type_ref(type_ref: TypeRef, ir: IRModel, *, as_html: bool = False) -> str | Markup:
    """Render a field type as plain text or as HTML with a link to its type page."""
    if not as_html:
        return type_ref.render()

    return _render_type_ref_markup(type_ref, ir)


def struct_fields_context(struct: StructType, ir: IRModel) -> list[dict]:
    """One dict per struct field with everything the site/PDF/Word renderers need."""
    return [
        {
            "name": f.name,
            "is_key": f.is_key,
            "type_ref_render": format_type_ref(f.type_ref, ir),
            "type_ref_html": format_type_ref(f.type_ref, ir, as_html=True),
            "meta": f.meta,
            "doc": f.doc,
        }
        for f in struct.fields
    ]
