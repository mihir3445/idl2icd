from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, PrivateAttr


class ProjectSection(BaseModel):
    name: str
    version: str
    organization: str | None = None


class SourcesSection(BaseModel):
    idl: list[str]
    metadata: list[str] = Field(default_factory=list)
    include_paths: list[str] = Field(default_factory=list)


class OutputSection(BaseModel):
    site_dir: str = "dist/site"
    pdf_path: str = "dist/icd.pdf"
    docx_path: str = "dist/icd.docx"
    snapshot_dir: str = ".idl2icd/snapshots"


class ValidationSection(BaseModel):
    rules: dict[str, str] = Field(default_factory=dict)
    fail_on: str = "warn"


class DiagramsSection(BaseModel):
    direction: str = "LR"
    show_topic_qos: bool = False
    show_topic_rate: bool = False


class PluginsSection(BaseModel):
    enabled: list[str] = Field(default_factory=list)


class ProjectConfig(BaseModel):
    project: ProjectSection
    sources: SourcesSection
    output: OutputSection = Field(default_factory=OutputSection)
    validation: ValidationSection = Field(default_factory=ValidationSection)
    diagrams: DiagramsSection = Field(default_factory=DiagramsSection)
    plugins: PluginsSection = Field(default_factory=PluginsSection)

    _base_dir: Path = PrivateAttr(default=None)

    def resolve_idl_paths(self) -> list[Path]:
        return _glob_all(self._base_dir, self.sources.idl)

    def resolve_metadata_paths(self) -> list[Path]:
        return _glob_all(self._base_dir, self.sources.metadata)

    def resolve_include_paths(self) -> list[Path]:
        return _glob_all(self._base_dir, self.sources.include_paths)


def _glob_all(base: Path, patterns: list[str]) -> list[Path]:
    out: list[Path] = []
    for pat in patterns:
        out.extend(sorted(base.glob(pat)))
    return out


def load_config(path: str | Path) -> ProjectConfig:
    p = Path(path)
    raw = yaml.safe_load(p.read_text())
    cfg = ProjectConfig.model_validate(raw)
    cfg._base_dir = p.parent.resolve()
    return cfg
