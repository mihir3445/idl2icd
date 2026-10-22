from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from idl2icd.model.ir import (
    Endpoint,
    FieldMeta,
    QoSDeadline,
    QoSHistory,
    QoSLiveliness,
    RateSpec,
)


class MetaField(FieldMeta):
    model_config = ConfigDict(extra="forbid")


class MetaRate(RateSpec):
    model_config = ConfigDict(extra="forbid")


class MetaEndpoint(Endpoint):
    model_config = ConfigDict(extra="forbid")


class MetaQoSOverride(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reliability: Literal["BEST_EFFORT", "RELIABLE"] | None = None
    durability: Literal["VOLATILE", "TRANSIENT_LOCAL", "TRANSIENT", "PERSISTENT"] | None = None
    history: QoSHistory | None = None
    deadline: QoSDeadline | None = None
    liveliness: QoSLiveliness | None = None


class MetaQoS(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile: str | None = None
    overrides: MetaQoSOverride | None = None


class MetaTopic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str | None = None
    criticality: Literal["low", "medium", "high", "safety"] | None = None
    rate: MetaRate | None = None
    qos: MetaQoS | None = None
    publishers: list[MetaEndpoint] = Field(default_factory=list)
    subscribers: list[MetaEndpoint] = Field(default_factory=list)
    fields: dict[str, MetaField] = Field(default_factory=dict)


class MetadataFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topics: dict[str, MetaTopic] = Field(default_factory=dict)
    qos_profiles: dict[str, MetaQoSOverride] = Field(default_factory=dict)
