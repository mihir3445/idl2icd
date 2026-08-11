from __future__ import annotations

from markupsafe import Markup, escape

from idl2icd.model.ir import IRModel, TypeRef


def format_type_ref(type_ref: TypeRef, ir: IRModel, *, as_html: bool = False) -> str | Markup:
    """Render a field type as plain text or as HTML with a link to its type page."""
    rendered = type_ref.render()
    if not as_html:
        return rendered

    escaped = escape(rendered)
    if type_ref.kind != "named":
        return Markup(f"<code>{escaped}</code>")

    target = ir.types.get(type_ref.name)
    if target is None:
        return Markup(f"<code>{escaped}</code>")

    href = escape(f"../types/{target.fqn.replace('::', '.')}.html")
    return Markup(f'<a href="{href}"><code>{escaped}</code></a>')
