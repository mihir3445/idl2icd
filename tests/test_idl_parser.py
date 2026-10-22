from pathlib import Path

from idl2icd.parsing.doc_comments import extract_doc_comments
from idl2icd.parsing.idl_parser import parse_idl_file


def _parse(tmp_path: Path, text: str, name: str = "sample.idl"):
    p = tmp_path / name
    p.write_text(text)
    return parse_idl_file(p)


def test_block_and_line_doc_comments_are_associated(tmp_path):
    parsed = _parse(
        tmp_path,
        """
    /**
     * Temperature reading in Celsius.
     */
    struct Temp {
      /// Current temperature.
      float value;
    };
    """,
    )

    struct = parsed.types["Temp"]
    assert struct.doc == "Temperature reading in Celsius."
    assert struct.fields[0].doc == "Current temperature."


def test_sequence_array_and_bounded_string_bounds_are_recorded(tmp_path):
    parsed = _parse(
        tmp_path,
        """
    struct S {
      sequence<double, 8> values;
      float matrix[4][4];
      string<32> label;
      wstring raw_text;
    };
    """,
    )

    fields = parsed.types["S"].fields
    seq = fields[0].type_ref
    assert seq.kind == "sequence"
    assert seq.element.kind == "primitive" and seq.element.name == "double"
    assert seq.bound == 8

    arr = fields[1].type_ref
    assert arr.kind == "array"
    assert arr.array_dims == [4, 4]
    assert arr.element.kind == "primitive" and arr.element.name == "float"

    assert fields[2].type_ref.kind == "string" and fields[2].type_ref.bound == 32
    assert fields[3].type_ref.kind == "string" and fields[3].type_ref.name == "wstring"


def test_primitive_aliases_are_normalized(tmp_path):
    parsed = _parse(tmp_path, "struct T { unsigned long id; long double x; boolean on; };")

    fields = parsed.types["T"].fields
    assert fields[0].type_ref.name == "uint32"
    assert fields[1].type_ref.name == "long double"
    assert fields[2].type_ref.name == "boolean"
    assert all(f.type_ref.kind == "primitive" for f in fields)


def test_named_references_resolve_to_fqns_within_scope(tmp_path):
    parsed = _parse(
        tmp_path,
        """
    module A { struct Type { long x; }; };
    module A {
      module B { struct Uses { Type t; }; };
    };
    """,
    )

    uses = parsed.types["A::B::Uses"]
    assert uses.fields[0].type_ref.kind == "named"
    assert uses.fields[0].type_ref.name == "A::Type"


def test_named_references_resolve_inside_sequences(tmp_path):
    parsed = _parse(
        tmp_path,
        """
    module A {
      struct Item { long x; };
      struct Batch { sequence<Item> items; };
    };
    """,
    )

    batch = parsed.types["A::Batch"]
    element = batch.fields[0].type_ref.element
    assert element.kind == "named"
    assert element.name == "A::Item"


def test_union_multiple_case_labels_and_default(tmp_path):
    parsed = _parse(
        tmp_path,
        """
    union U switch(long) {
      case 1:
      case 2:
        long a;
      default:
        char b;
    };
    """,
    )

    union = parsed.types["U"]
    assert union.discriminator.kind == "primitive"
    assert [case.labels for case in union.cases] == [["1", "2"], ["default"]]
    assert union.cases[0].field.name == "a"


def test_topic_hints_collect_annotated_structs(tmp_path):
    parsed = _parse(
        tmp_path,
        """
    @topic
    struct Announce { long x; };
    struct Plain { long y; };
    """,
    )

    assert parsed.topic_hints == {"Announce"}
    assert parsed.types["Announce"].is_topic is True
    assert parsed.types["Plain"].is_topic is False


def test_preprocessor_guards_select_branches(tmp_path):
    parsed = _parse(
        tmp_path,
        """
    #define ENABLED
    #ifdef ENABLED
    struct On { long x; };
    #else
    struct Off { long y; };
    #endif
    #ifndef ENABLED
    struct AlsoOff { long z; };
    #endif
    """,
    )

    assert "On" in parsed.types
    assert "Off" not in parsed.types
    assert "AlsoOff" not in parsed.types


def test_parse_error_reports_file_line_and_column(tmp_path):
    p = tmp_path / "bad.idl"
    p.write_text("struct Broken {\n  long x\n};\n")

    try:
        parse_idl_file(p)
    except ValueError as exc:
        message = str(exc)
        assert "bad.idl" in message
        assert "line" in message and "column" in message
        assert "Context:" in message


def test_doc_comment_index_handles_blank_lines(tmp_path):
    source = "/// A\n/// B\n\nstruct S { long x; };\n"
    index = extract_doc_comments(source)
    # doc comment lands on the `struct` declaration line (3rd line, 1-indexed)
    assert index.by_next_line[3] == "A\nB"
