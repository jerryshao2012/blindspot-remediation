"""Strict, base-trusted assurance policy; finite reviewed concept values."""

from __future__ import annotations

import json
from pathlib import PurePosixPath
from typing import Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from release_gate.config import ConfigError, _UniqueKeyLoader

Value = str | bool


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class Selector(Model):
    check_id: str = Field(min_length=1)
    report_id: str | None = None
    suite: str | None = None
    classname: str | None = None
    name: str | None = None

    @model_validator(mode="after")
    def complete(self) -> Self:
        case = (self.report_id, self.suite, self.classname, self.name)
        if any(x is not None for x in case) and not all(x is not None for x in case):
            raise ValueError(
                "case selectors require report_id, suite, classname and name"
            )
        return self


class Dimension(Model):
    dimension_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    definition: str = Field(min_length=1)
    values: list[Value] = Field(min_length=1, max_length=64)


class Schema(Model):
    schema_id: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)
    dimensions: list[Dimension] = Field(min_length=1, max_length=32)


class Mapping(Model):
    selector: Selector
    concepts: dict[str, Value] = Field(min_length=1)
    sources: dict[str, str] = Field(min_length=1, max_length=64)
    independence_group: str | None = Field(default=None, min_length=1)


class Requirement(Model):
    dimension_id: str
    value: Value
    minimum_independent_support: int = Field(ge=1, le=1024)


class Limits(Model):
    max_artifacts: int = Field(default=256, ge=1, le=1024)
    max_report_bytes: int = Field(default=4194304, ge=1, le=16777216)
    max_total_report_bytes: int = Field(default=16777216, ge=1, le=33554432)
    max_elapsed_seconds: float = Field(default=30.0, gt=0, le=300)


class AssurancePolicy(Model):
    version: Literal[1]
    mode: Literal["advisory", "enforce"]
    concept_schema: Schema
    mappings: list[Mapping] = Field(max_length=1024)
    required_regions: list[Requirement] = Field(min_length=1, max_length=1024)
    maximum_mapping_uncertainty_rate: float = Field(ge=0, le=1)
    limits: Limits = Field(default_factory=Limits)

    @model_validator(mode="after")
    def semantics(self) -> Self:
        dimensions = {d.dimension_id: d for d in self.concept_schema.dimensions}
        if len(dimensions) != len(self.concept_schema.dimensions):
            raise ValueError("duplicate dimension ID")
        selectors = [m.selector.model_dump_json() for m in self.mappings]
        if len(set(selectors)) != len(selectors):
            raise ValueError("duplicate mapping selector")
        regions = [(r.dimension_id, json.dumps(r.value)) for r in self.required_regions]
        if len(set(regions)) != len(regions):
            raise ValueError("duplicate required region")
        for dimension in dimensions.values():
            values = [json.dumps(v) for v in dimension.values]
            if len(set(values)) != len(values):
                raise ValueError("duplicate concept value")
        for dimension_id, value in [
            *((r.dimension_id, r.value) for r in self.required_regions),
            *((key, value) for m in self.mappings for key, value in m.concepts.items()),
        ]:
            if (
                dimension_id not in dimensions
                or value not in dimensions[dimension_id].values
            ):
                raise ValueError("unknown dimension or concept value")
        for mapping in self.mappings:
            for path, digest in mapping.sources.items():
                parts = PurePosixPath(path)
                if (
                    not path
                    or parts.is_absolute()
                    or ".." in parts.parts
                    or "\\" in path
                    or ":" in path
                    or str(parts) != path
                ):
                    raise ValueError("reviewed source path must be repository relative")
                if len(digest) != 64 or any(
                    c not in "0123456789abcdef" for c in digest
                ):
                    raise ValueError("reviewed source requires SHA-256")
        return self


def load_policy(data: bytes) -> AssurancePolicy:
    try:
        if len(data) > 1048576:
            raise ValueError("assurance policy exceeds 1 MiB")
        value = yaml.load(data.decode("utf-8"), Loader=_UniqueKeyLoader)
        return AssurancePolicy.model_validate(value)
    except (ValueError, UnicodeError, yaml.YAMLError, RecursionError) as error:
        raise ConfigError("invalid assurance policy: " + str(error)) from error
