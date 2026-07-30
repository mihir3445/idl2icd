"""The core Intermediate Representation (IR). This is the ONLY model that
renderers, diagram generators, validation rules, and the change-report
engine are allowed to depend on. IDL parsing and metadata merging both
produce this; nothing downstream re-reads source files.
"""
from __future__ import annotations

from typing import Literal, Union

from pydantic import BaseModel, Field


class SourceSpan(BaseModel):
    file: str
    line: int


class TypeRef(BaseModel):
    """A resolved reference to a type: either a primitive, a bounded
    string/sequence, or a named user type (FQN)."""
    kind: Literal["primitive", "string", "sequence", "named", "array"]
    name: str  # primitive name, "string", "sequence", or the FQN for named
    bound: int | None = None          # string/sequence bound, if any
    element: TypeRef | None = None  # element type for sequence/array
    array_dims: list[int] = Field(default_factory=list)

    def render(self) -> str:
        if self.kind == "primitive" or self.kind == "named":
            base = self.name
        elif self.kind == "string":
            base = f"string<{self.bound}>" if self.bound else "string"
        elif self.kind == "sequence":
            inner = self.element.render() if self.element else "?"
            base = f"sequence<{inner}, {self.bound}>" if self.bound else f"sequence<{inner}>"
        else:
            base = self.name
        if self.array_dims:
            base += "".join(f"[{d}]" for d in self.array_dims)
        return base


TypeRef.model_rebuild()


class FieldMeta(BaseModel):
    """Metadata that can be attached to a field from the metadata YAML."""
    unit: str | None = None
    range: list[float] | None = None
    precision: float | None = None
    description: str | None = None


class Field_(BaseModel):
    name: str
    type_ref: TypeRef
    is_key: bool = False
    optional: bool = False
    doc: str | None = None
    meta: FieldMeta = Field(default_factory=FieldMeta)
    source_span: SourceSpan | None = None


class StructType(BaseModel):
    fqn: str
    kind: Literal["struct"] = "struct"
    fields: list[Field_] = Field(default_factory=list)
    doc: str | None = None
    is_topic: bool = False
    source_span: SourceSpan | None = None


class UnionCase(BaseModel):
    labels: list[str]  # rendered const expressions, or ["default"]
    field: Field_


class UnionType(BaseModel):
    fqn: str
    kind: Literal["union"] = "union"
    discriminator: TypeRef
    cases: list[UnionCase] = Field(default_factory=list)
    doc: str | None = None
    source_span: SourceSpan | None = None


class EnumType(BaseModel):
    fqn: str
    kind: Literal["enum"] = "enum"
    values: list[str] = Field(default_factory=list)
    doc: str | None = None
    source_span: SourceSpan | None = None


AnyType = Union[StructType, UnionType, EnumType]


class RateSpec(BaseModel):
    nominal_hz: float | None = None
    max_hz: float | None = None


class QoSHistory(BaseModel):
    kind: Literal["KEEP_LAST", "KEEP_ALL"] = "KEEP_LAST"
    depth: int | None = 1


class QoSDeadline(BaseModel):
    period_ms: float | None = None


class QoSLiveliness(BaseModel):
    kind: Literal["AUTOMATIC", "MANUAL_BY_PARTICIPANT", "MANUAL_BY_TOPIC"] = "AUTOMATIC"
    lease_duration_ms: float | None = None


class ResolvedQoS(BaseModel):
    reliability: Literal["BEST_EFFORT", "RELIABLE"] = "BEST_EFFORT"
    durability: Literal["VOLATILE", "TRANSIENT_LOCAL", "TRANSIENT", "PERSISTENT"] = "VOLATILE"
    history: QoSHistory = Field(default_factory=QoSHistory)
    deadline: QoSDeadline | None = None
    liveliness: QoSLiveliness | None = None


class Endpoint(BaseModel):
    participant: str
    instance_count: str | None = None
    source: str | None = None
    notes: str | None = None


class Topic(BaseModel):
    fqn: str
    data_type_fqn: str
    description: str | None = None
    criticality: Literal["low", "medium", "high", "safety"] | None = None
    rate: RateSpec | None = None
    qos: ResolvedQoS = Field(default_factory=ResolvedQoS)
    publishers: list[Endpoint] = Field(default_factory=list)
    subscribers: list[Endpoint] = Field(default_factory=list)


class ProjectMeta(BaseModel):
    name: str
    version: str
    organization: str | None = None


class Diagnostic(BaseModel):
    rule: str
    severity: Literal["error", "warn", "info"]
    message: str
    location: SourceSpan | None = None


class IRModel(BaseModel):
    schema_version: str = "1.0"
    project: ProjectMeta
    types: dict[str, AnyType] = Field(default_factory=dict)
    topics: dict[str, Topic] = Field(default_factory=dict)
    diagnostics: list[Diagnostic] = Field(default_factory=list)
