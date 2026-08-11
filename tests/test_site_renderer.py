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
