from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class MetaField(BaseModel):
    model_config = ConfigDict(extra="forbid")
    unit: Optional[str] = None
    range: Optional[list[float]] = None
    precision: Optional[float] = None
    description: Optional[str] = None


class MetaRate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nominal_hz: Optional[float] = None
    max_hz: Optional[float] = None


class MetaEndpoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    participant: str
    instance_count: Optional[str] = None
    source: Optional[str] = None
    notes: Optional[str] = None


class MetaQoSOverride(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reliability: Optional[Literal["BEST_EFFORT", "RELIABLE"]] = None
    durability: Optional[Literal["VOLATILE", "TRANSIENT_LOCAL", "TRANSIENT", "PERSISTENT"]] = None
    history: Optional[dict] = None
    deadline: Optional[dict] = None
    liveliness: Optional[dict] = None


class MetaQoS(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile: Optional[str] = None
    overrides: Optional[MetaQoSOverride] = None


class MetaTopic(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: Optional[str] = None
    criticality: Optional[Literal["low", "medium", "high", "safety"]] = None
    rate: Optional[MetaRate] = None
    qos: Optional[MetaQoS] = None
    publishers: list[MetaEndpoint] = Field(default_factory=list)
    subscribers: list[MetaEndpoint] = Field(default_factory=list)
    fields: dict[str, MetaField] = Field(default_factory=dict)


class MetadataFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topics: dict[str, MetaTopic] = Field(default_factory=dict)
    qos_profiles: dict[str, MetaQoSOverride] = Field(default_factory=dict)
