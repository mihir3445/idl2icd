from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from lark import Lark, Token, Tree
from lark.exceptions import UnexpectedCharacters, UnexpectedToken

from idl2icd.model.ir import (
    AnyType,
    EnumType,
    Field_,
    SourceSpan,
    StructType,
    TypeRef,
    UnionCase,
    UnionType,
)
from idl2icd.parsing.doc_comments import extract_doc_comments

_GRAMMAR_PATH = Path(__file__).parent / "idl_grammar.lark"
_parser = Lark(_GRAMMAR_PATH.read_text(), parser="lalr", propagate_positions=True)

_DIRECTIVE_RE = re.compile(r"^\s*#\s*(\w+)(?:\s+(.*))?\s*$")
_INCLUDE_RE = re.compile(r'^\s*#\s*include\s*(?:"([^"]+)"|<([^>]+)>)\s*$')
_TYPEDEF_ENUM_RE = re.compile(
    r"\btypedef\s+enum(?:\s+([A-Za-z_][A-Za-z0-9_]*))?\s*\{(.*?)\}\s*([A-Za-z_][A-Za-z0-9_]*)\s*;",
    re.DOTALL,
)

PRIMITIVES = {
    "boolean", "octet", "char", "wchar", "short", "unsigned",
    "long", "float", "double", "int8", "uint8", "int16", "uint16",
    "int32", "uint32", "int64", "uint64", "long double",
}

# Maps the Lark alias node names produced by the `primitive_type` rule
# (see idl_grammar.lark) to the canonical primitive name used in the IR.
_PRIMITIVE_ALIAS_TO_NAME = {
    "uint64_t": "uint64", "uint32_t": "uint32", "uint16_t": "uint16",
    "int64_t": "int64", "int32_t": "int32", "int16_t": "int16",
    "longdouble_t": "long double", "float_t": "float", "double_t": "double",
    "bool_t": "boolean", "octet_t": "octet", "char_t": "char", "wchar_t": "wchar",
    "int8_t": "int8", "uint8_t": "uint8",
}


@dataclass
class ParsedFile:
    types: dict[str, object] = field(default_factory=dict)  # fqn -> StructType/UnionType/EnumType
    topic_hints: set[str] = field(default_factory=set)       # FQNs annotated @topic


def parse_idl_file(path: str | Path, include_dirs: list[Path] | None = None) -> ParsedFile:
    source_path = Path(path)
    text = source_path.read_text()
    include_dirs = [Path(d).resolve() for d in (include_dirs or [])]
    # Preprocess a pragmatic C-style subset before handing the IDL to the
    # grammar. This lets common guard wrappers and includes work without
    # requiring callers to manually scrub the file first.
    text = _rewrite_typedef_enum(text)
    text = _preprocess_source_text(
        text,
        source_path.parent,
        defined_macros=set(),
        seen={source_path.resolve()},
        include_dirs=include_dirs,
    )
    doc_index = extract_doc_comments(text)
    try:
        tree = _parser.parse(text)
    except (UnexpectedCharacters, UnexpectedToken) as exc:
        line = getattr(exc, "line", None)
        column = getattr(exc, "column", None)
        msg = (
            f"Failed to parse IDL '{source_path}' at line {line}, column {column}. "
            f"Unexpected token: {exc}."
        )
        context = _format_source_context(text, line)
        if context:
            msg += f" Context:\n{context}"
        raise ValueError(msg) from exc
    out = ParsedFile()
    _walk(tree, scope=[], filename=str(path), doc_index=doc_index, out=out)
    _resolve_type_refs(out.types)
    return out


def _format_source_context(text: str, line_no: int | None, radius: int = 1) -> str | None:
    if line_no is None:
        return None
    lines = text.splitlines()
    start = max(1, line_no - radius)
    end = min(len(lines), line_no + radius)
    if start > end:
        return None
    selected = []
    for idx in range(start, end + 1):
        selected.append(f"{idx}: {lines[idx - 1]}")
    return "\n".join(selected)


def _rewrite_typedef_enum(text: str) -> str:
    def _replace(match: re.Match[str]) -> str:
        enum_tag = match.group(1)
        alias = match.group(3)
        body = match.group(2).strip()
        enum_name = enum_tag or alias
        return f"enum {enum_name} {{ {body} }};"

    return _TYPEDEF_ENUM_RE.sub(_replace, text)


def _visible(active_stack: list[dict[str, bool]]) -> bool:
    return all(ctx["branch_visible"] for ctx in active_stack)


def _resolve_include_file(include_name: str, current_dir: Path, include_dirs: list[Path]) -> Path | None:
    include_path = Path(include_name)
    if include_path.is_absolute():
        candidates = [include_path]
    else:
        candidates = [
            (current_dir / include_path).resolve(),
            *[(search_dir / include_path).resolve() for search_dir in include_dirs],
        ]

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _preprocess_source_text(
    text: str,
    base_dir: Path,
    *,
    defined_macros: set[str],
    seen: set[Path],
    include_dirs: list[Path] | None = None,
) -> str:
    lines = text.splitlines(keepends=True)
    active_stack: list[dict[str, bool]] = []
    out: list[str] = []
    include_dirs = list(include_dirs or [])

    for line in lines:
        directive_match = _DIRECTIVE_RE.match(line)
        if not directive_match:
            if _visible(active_stack):
                out.append(line)
            continue

        directive = directive_match.group(1).lower()
        remainder = (directive_match.group(2) or "").strip()

        if directive == "define":
            name = remainder.split()[0] if remainder else ""
            if name:
                defined_macros.add(name)
            continue

        if directive == "undef":
            name = remainder.split()[0] if remainder else ""
            if name:
                defined_macros.discard(name)
            continue

        if directive == "ifdef":
            name = remainder.split()[0] if remainder else ""
            parent_visible = _visible(active_stack)
            condition_true = name in defined_macros
            active_stack.append({
                "parent_visible": parent_visible,
                "condition_true": condition_true,
                "branch_visible": parent_visible and condition_true,
            })
            continue

        if directive == "ifndef":
            name = remainder.split()[0] if remainder else ""
            parent_visible = _visible(active_stack)
            condition_true = name not in defined_macros
            active_stack.append({
                "parent_visible": parent_visible,
                "condition_true": condition_true,
                "branch_visible": parent_visible and condition_true,
            })
            continue

        if directive == "else":
            if active_stack:
                ctx = active_stack[-1]
                ctx["branch_visible"] = ctx["parent_visible"] and not ctx["condition_true"]
            continue

        if directive == "endif":
            if active_stack:
                active_stack.pop()
            continue

        # pragma directives (e.g. #pragma once) are silently ignored.
        if directive == "pragma":
            continue

        include_match = _INCLUDE_RE.match(line)
        if directive == "include" and include_match:
            include_name = include_match.group(1) or include_match.group(2)
            if _visible(active_stack):
                include_path = _resolve_include_file(include_name, base_dir, include_dirs)
                if include_path is not None and include_path.resolve() not in seen:
                    seen.add(include_path.resolve())
                    included_text = _rewrite_typedef_enum(include_path.read_text())
                    out.append(_preprocess_source_text(
                        included_text,
                        include_path.parent,
                        defined_macros=defined_macros,
                        seen=seen,
                        include_dirs=include_dirs,
                    ))
            continue

        # Unknown directives are treated as a no-op. This keeps the parser
        # tolerant of common guard metadata while preserving real IDL syntax.
        if _visible(active_stack):
            out.append(line)

    return "".join(out)


def _fqn(scope: list[str], name: str) -> str:
    return "::".join([*scope, name])


def _line_of(node) -> int:
    if isinstance(node, Tree) and node.meta and not node.meta.empty:
        return node.meta.line
    if isinstance(node, Token):
        return node.line
    return 0


def _find_annotations(children) -> list[Tree]:
    return [c for c in children if isinstance(c, Tree) and c.data == "annotation"]


def _has_annotation(children, name: str) -> bool:
    return any(a.children[0].value == name for a in _find_annotations(children))


def _walk(tree: Tree, scope: list[str], filename: str, doc_index, out: ParsedFile):
    for node in tree.children:
        if not isinstance(node, Tree):
            continue
        if node.data == "module_def":
            ident = next(c for c in node.children if isinstance(c, Token) and c.type == "IDENT")
            inner_defs = [c for c in node.children if isinstance(c, Tree) and c.data == "definition"]
            _walk_definitions(inner_defs, [*scope, ident.value], filename, doc_index, out)
        elif node.data == "definition":
            _walk_definitions([node], scope, filename, doc_index, out)


def _walk_definitions(defs: list[Tree], scope: list[str], filename: str, doc_index, out: ParsedFile):
    for d in defs:
        inner = d.children[0]
        if inner.data == "module_def":
            ident = next(c for c in inner.children if isinstance(c, Token) and c.type == "IDENT")
            sub_defs = [c for c in inner.children if isinstance(c, Tree) and c.data == "definition"]
            _walk_definitions(sub_defs, [*scope, ident.value], filename, doc_index, out)
        elif inner.data == "struct_def":
            _handle_struct(inner, scope, filename, doc_index, out)
        elif inner.data == "union_def":
            _handle_union(inner, scope, filename, doc_index, out)
        elif inner.data == "enum_def":
            _handle_enum(inner, scope, filename, doc_index, out)
        # typedef_def / const_def: not yet surfaced in IR (v0.1 scope)


def _doc_for(node, doc_index) -> str | None:
    line = _line_of(node)
    return doc_index.for_line(line) if line else None


def _resolve_type_refs(types: dict[str, AnyType]) -> None:
    for fqn, type_ in types.items():
        scope = fqn.split("::")[:-1]
        if isinstance(type_, StructType):
            for field in type_.fields:
                field.type_ref = _resolve_type_ref(field.type_ref, scope, types)
        elif isinstance(type_, UnionType):
            type_.discriminator = _resolve_type_ref(type_.discriminator, scope, types)
            for case in type_.cases:
                case.field.type_ref = _resolve_type_ref(case.field.type_ref, scope, types)


def _resolve_type_ref(type_ref: TypeRef, scope: list[str], types: dict[str, AnyType]) -> TypeRef:
    if type_ref.kind == "sequence":
        element = _resolve_type_ref(type_ref.element, scope, types) if type_ref.element else None
        return TypeRef(kind="sequence", name="sequence", element=element, bound=type_ref.bound)
    if type_ref.kind == "array":
        element = _resolve_type_ref(type_ref.element, scope, types) if type_ref.element else None
        return TypeRef(kind="array", name=type_ref.name, element=element, array_dims=type_ref.array_dims)
    if type_ref.kind != "named":
        return type_ref.model_copy(deep=True)

    resolved_name = _resolve_named_type_name(type_ref.name, scope, types)
    return TypeRef(kind="named", name=resolved_name or type_ref.name)


def _resolve_named_type_name(name: str, scope: list[str], types: dict[str, AnyType]) -> str | None:
    parts = name.split("::")
    if not parts:
        return None

    for prefix_len in range(len(scope), -1, -1):
        candidate = "::".join([*scope[:prefix_len], *parts])
        if candidate in types:
            return candidate
    return None


def _type_spec_to_ref(node: Tree) -> TypeRef:
    if node.data == "prim_type":
        alias_node = node.children[0]
        name = _PRIMITIVE_ALIAS_TO_NAME.get(alias_node.data, alias_node.data)
        return TypeRef(kind="primitive", name=name)
    if node.data == "named_type":
        scoped = node.children[0]
        parts = [t.value for t in scoped.children if isinstance(t, Token)]
        name = "::".join(parts)
        kind = "primitive" if name in PRIMITIVES else "named"
        return TypeRef(kind=kind, name=name)
    if node.data == "string_type":
        bound = _const_expr_to_int(node.children[0]) if node.children else None
        return TypeRef(kind="string", name="string", bound=bound)
    if node.data == "wstring_type":
        bound = _const_expr_to_int(node.children[0]) if node.children else None
        return TypeRef(kind="string", name="wstring", bound=bound)
    if node.data == "seq_type":
        elem = _type_spec_to_ref(node.children[0])
        bound = _const_expr_to_int(node.children[1]) if len(node.children) > 1 else None
        return TypeRef(kind="sequence", name="sequence", element=elem, bound=bound)
    raise ValueError(f"Unknown type_spec node: {node.data}")


def _const_expr_to_int(node: Tree) -> int | None:
    if node.data == "num_expr":
        try:
            # int() with base 0 auto-detects 0x prefix for hex literals
            # and falls back to decimal for plain numbers.
            return int(node.children[0].value, 0)
        except ValueError:
            return None
    return None


def _const_expr_to_str(node: Tree) -> str:
    if node.data == "num_expr":
        return node.children[0].value
    if node.data == "str_expr":
        return node.children[0].value.strip('"')
    if node.data == "ref_expr":
        parts = [t.value for t in node.children[0].children if isinstance(t, Token)]
        return "::".join(parts)
    return "?"


def _handle_struct(node: Tree, scope, filename, doc_index, out: ParsedFile):
    ident = next(c for c in node.children if isinstance(c, Token) and c.type == "IDENT")
    fqn = _fqn(scope, ident.value)
    members = [c for c in node.children if isinstance(c, Tree) and c.data == "member"]

    fields: list[Field_] = []
    for m in members:
        rest = [c for c in m.children if isinstance(c, Tree) and c.data != "annotation"]
        type_spec = rest[0]
        declarators = rest[1:]
        type_ref = _type_spec_to_ref(type_spec)
        is_key = _has_annotation(m.children, "key")
        optional = _has_annotation(m.children, "optional")
        for decl in declarators:
            fname = decl.children[0].value
            array_node = decl.children[1] if len(decl.children) > 1 else None
            dims = []
            if array_node is not None:
                dims = [_const_expr_to_int(c) for c in array_node.children]
            tr = type_ref
            if dims:
                tr = TypeRef(kind="array", name=type_ref.render(), element=type_ref, array_dims=[d for d in dims if d])
            fields.append(Field_(
                name=fname,
                type_ref=tr,
                is_key=is_key,
                optional=optional,
                doc=_doc_for(m, doc_index),
                source_span=SourceSpan(file=filename, line=_line_of(m)),
            ))

    struct = StructType(
        fqn=fqn,
        fields=fields,
        doc=_doc_for(node, doc_index),
        is_topic=_has_annotation(node.children, "topic"),
        source_span=SourceSpan(file=filename, line=_line_of(node)),
    )
    out.types[fqn] = struct
    if struct.is_topic:
        out.topic_hints.add(fqn)


def _handle_union(node: Tree, scope, filename, doc_index, out: ParsedFile):
    ident = next(c for c in node.children if isinstance(c, Token) and c.type == "IDENT")
    fqn = _fqn(scope, ident.value)
    type_specs = [c for c in node.children if isinstance(c, Tree) and c.data in
                  ("named_type", "string_type", "wstring_type", "seq_type", "prim_type")]
    discriminator = _type_spec_to_ref(type_specs[0])
    case_nodes = [c for c in node.children if isinstance(c, Tree) and c.data in ("case_labelled", "case_default")]

    cases: list[UnionCase] = []
    for c in case_nodes:
        if c.data == "case_labelled":
            label_exprs = [ch for ch in c.children if isinstance(ch, Tree) and ch.data in
                           ("num_expr", "str_expr", "ref_expr")]
            rest = [ch for ch in c.children if ch not in label_exprs]
            labels = [_const_expr_to_str(le) for le in label_exprs]
        else:
            rest = c.children
            labels = ["default"]
        type_spec = rest[0]
        decl = rest[1]
        type_ref = _type_spec_to_ref(type_spec)
        fname = decl.children[0].value
        cases.append(UnionCase(labels=labels, field=Field_(
            name=fname, type_ref=type_ref,
            source_span=SourceSpan(file=filename, line=_line_of(c)),
        )))

    union = UnionType(
        fqn=fqn,
        discriminator=discriminator,
        cases=cases,
        doc=_doc_for(node, doc_index),
        source_span=SourceSpan(file=filename, line=_line_of(node)),
    )
    out.types[fqn] = union


def _handle_enum(node: Tree, scope, filename, doc_index, out: ParsedFile):
    ident = next(c for c in node.children if isinstance(c, Token) and c.type == "IDENT")
    fqn = _fqn(scope, ident.value)
    members = [c for c in node.children if isinstance(c, Tree) and c.data == "enum_member"]
    values = [
        next(t for t in m.children if isinstance(t, Token) and t.type == "IDENT").value
        for m in members
    ]
    enum = EnumType(
        fqn=fqn,
        values=values,
        doc=_doc_for(node, doc_index),
        source_span=SourceSpan(file=filename, line=_line_of(node)),
    )
    out.types[fqn] = enum
