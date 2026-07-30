from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MetaField(BaseModel):
    model_config = ConfigDict(extra="forbid")
    unit: str | None = None
    range: list[float] | None = None
    precision: float | None = None
    description: str | None = None


class MetaRate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nominal_hz: float | None = None
    max_hz: float | None = None


class MetaEndpoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    participant: str
    instance_count: str | None = None
    source: str | None = None
    notes: str | None = None


class MetaQoSOverride(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reliability: Literal["BEST_EFFORT", "RELIABLE"] | None = None
    durability: Literal["VOLATILE", "TRANSIENT_LOCAL", "TRANSIENT", "PERSISTENT"] | None = None
    history: dict | None = None
    deadline: dict | None = None
    liveliness: dict | None = None


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
