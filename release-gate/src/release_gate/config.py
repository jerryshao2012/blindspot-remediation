"""Strict loading and semantic validation for ``.release-gate.yaml``."""

from __future__ import annotations

import importlib.resources
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any, cast

import yaml
from jsonschema import Draft202012Validator, FormatChecker, ValidationError
from pydantic import ValidationError as PydanticValidationError

from release_gate.models import GateConfig

MAX_CONFIG_BYTES = 1_048_576


class ConfigError(ValueError):
    """A safe, source-aware configuration diagnostic."""


class _DuplicateKeyError(yaml.YAMLError):
    def __init__(self, key: object, line: int, column: int) -> None:
        super().__init__(f"duplicate key at line {line}, column {column}: {key!s}")


class _UniqueKeyLoader(yaml.SafeLoader):
    pass


def _construct_mapping(
    loader: _UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[object, object]:
    loader.flatten_mapping(node)
    mapping: dict[object, object] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except TypeError as error:
            raise yaml.YAMLError("mapping keys must be scalar") from error
        if duplicate:
            raise _DuplicateKeyError(
                key,
                key_node.start_mark.line + 1,
                key_node.start_mark.column + 1,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping
)


def load_config(
    path: str | Path,
) -> GateConfig:
    """Load and validate a working-copy policy file."""

    source = Path(path)
    try:
        data = source.read_bytes()
    except OSError as error:
        raise ConfigError(
            f"{source}: unable to read configuration: {error.strerror}"
        ) from error
    return load_config_bytes(data, source=str(source))


def load_config_bytes(data: bytes, *, source: str = "<memory>") -> GateConfig:
    """Validate policy bytes without exposing configured values in errors."""

    if len(data) > MAX_CONFIG_BYTES:
        raise ConfigError(f"{source}: configuration exceeds the 1 MiB UTF-8 limit")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ConfigError(f"{source}: configuration is not valid UTF-8") from error
    try:
        value = yaml.load(text, Loader=_UniqueKeyLoader)
    except _DuplicateKeyError as error:
        raise ConfigError(f"{source}: {error}") from error
    except yaml.YAMLError as error:
        mark = getattr(error, "problem_mark", None)
        location = f" at line {mark.line + 1}, column {mark.column + 1}" if mark else ""
        raise ConfigError(f"{source}: invalid YAML{location}") from error
    if not isinstance(value, dict):
        raise ConfigError(f"{source}: $ must be a mapping")

    schema = _load_schema()
    schema_errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value),
        key=lambda item: tuple(str(part) for part in item.absolute_path),
    )
    if schema_errors:
        raise ConfigError(_schema_diagnostic(source, schema_errors[0]))

    try:
        config = GateConfig.model_validate(value)
    except PydanticValidationError as error:
        issue = error.errors(include_input=False, include_url=False)[0]
        path = _json_path(issue["loc"])
        raise ConfigError(f"{source}: {path}: {issue['msg']}") from error

    effective = json.dumps(
        config.model_dump(mode="json", by_alias=True),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8")
    if len(effective) > MAX_CONFIG_BYTES:
        raise ConfigError(
            f"{source}: effective configuration exceeds the 1 MiB UTF-8 limit"
        )
    return config


def _load_schema() -> dict[str, Any]:
    resource = (
        importlib.resources.files("release_gate") / "schemas" / "config-v1.schema.json"
    )
    return cast(dict[str, Any], json.loads(resource.read_text(encoding="utf-8")))


def _json_path(parts: Iterable[str | int]) -> str:
    path = "$"
    for part in parts:
        if isinstance(part, int):
            path += f"[{part}]"
        else:
            path += f".{part}"
    return path


def _schema_diagnostic(source: str, error: ValidationError) -> str:
    path = _json_path(error.absolute_path)
    safe_messages = {
        "const": "contains an unsupported fixed value",
        "enum": "contains an unsupported value",
        "maxLength": "contains a value longer than allowed",
        "minLength": "contains an empty or too-short value",
        "pattern": "contains a value with an invalid format",
        "type": "contains a value of the wrong type",
        "uniqueItems": "contains duplicate entries",
    }
    validator_name = error.validator if isinstance(error.validator, str) else ""
    message = safe_messages.get(validator_name, error.message)
    return f"{source}: {path}: {message}"
