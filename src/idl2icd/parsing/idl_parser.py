from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from lark import Lark, Token, Tree

from idl2icd.model.ir import (
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


def parse_idl_file(path: str | Path) -> ParsedFile:
    text = Path(path).read_text()
    doc_index = extract_doc_comments(text)
    tree = _parser.parse(text)
    out = ParsedFile()
    _walk(tree, scope=[], filename=str(path), doc_index=doc_index, out=out)
    return out


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
            return int(float(node.children[0].value))
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
    values = [c.value for c in node.children if isinstance(c, Token) and c.type == "IDENT"][1:]
    enum = EnumType(
        fqn=fqn,
        values=values,
        doc=_doc_for(node, doc_index),
        source_span=SourceSpan(file=filename, line=_line_of(node)),
    )
    out.types[fqn] = enum
