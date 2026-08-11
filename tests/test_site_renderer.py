from pathlib import Path

from idl2icd.config import load_config
from idl2icd.model.ir import ProjectMeta
from idl2icd.model.merge import build_ir
from idl2icd.render.site.renderer import render_site


EXAMPLE_DIR = Path(__file__).parent.parent / "examples" / "robot-fleet"


def test_site_renderer_links_named_field_types_to_type_pages(tmp_path):
    cfg = load_config(EXAMPLE_DIR / "idl2icd.yaml")
    project = ProjectMeta(**cfg.project.model_dump())
    ir = build_ir(
        cfg.resolve_idl_paths(),
        cfg.resolve_metadata_paths(),
        project,
        include_dirs=cfg.resolve_include_paths(),
    )

    render_site(ir, [], tmp_path)

    topic_page = tmp_path / "topics" / "Robot.Telemetry.BatteryStatus.html"
    assert topic_page.exists()

    html = topic_page.read_text()
    assert 'href="../types/Robot.Telemetry.SharedId.html"' in html


def test_site_renderer_links_nested_module_types_to_type_pages(tmp_path):
    idl_path = tmp_path / "sample.idl"
    idl_path.write_text("""
module X {
  module Y {
    struct Body { long x; };
    struct Another { Body value; };
  };
};
""")

    ir = build_ir([idl_path], [], ProjectMeta(name="t", version="1"))
    render_site(ir, [], tmp_path / "out")

    html = (tmp_path / "out" / "types" / "X.Y.Another.html").read_text()
    assert 'href="../types/X.Y.Body.html"' in html


def test_site_renderer_links_named_types_inside_sequences_to_type_pages(tmp_path):
    idl_path = tmp_path / "sample.idl"
    idl_path.write_text("""
module x {
  module y {
    struct Wheel { long size; };
    struct WheelData { sequence<Wheel, 10> wheels; };
  };
};
""")

    ir = build_ir([idl_path], [], ProjectMeta(name="t", version="1"))
    render_site(ir, [], tmp_path / "out")

    html = (tmp_path / "out" / "types" / "x.y.WheelData.html").read_text()
    assert 'href="../types/x.y.Wheel.html"' in html
