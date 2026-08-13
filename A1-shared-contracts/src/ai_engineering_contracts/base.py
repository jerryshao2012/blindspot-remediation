"""
Base models and reusable validation functions.

The package uses immutable Pydantic models with ``extra='forbid'``. This is
intentional:

1. A misspelled field must fail validation rather than being silently ignored.
2. Historical evidence must not be mutated after a decision is produced.
3. Contract evolution should be explicit and versioned.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict

from .constants import (
    MAX_METADATA_ENTRIES,
    MAX_METADATA_KEY_LENGTH,
    MAX_METADATA_VALUE_LENGTH,
)


class ContractModel(BaseModel):
    """Base class for all public contracts."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        validate_default=True,
        validate_assignment=True,
        use_enum_values=False,
    )

    def to_pretty_json(self) -> str:
        """Serialize the contract as stable, human-readable JSON."""
        return self.model_dump_json(
            indent=2,
            exclude_none=True,
            by_alias=True,
        )

    def to_json_compatible_dict(self) -> dict[str, Any]:
        """
        Return a dictionary containing only JSON-compatible values.

        ``model_dump(mode='json')`` converts enums, datetimes, and other typed
        fields to their serialized representations.
        """
        return self.model_dump(
            mode="json",
            exclude_none=True,
            by_alias=True,
        )

    def content_fingerprint(self) -> str:
        """
        Calculate a SHA-256 fingerprint of the canonical serialized contract.

        This fingerprint is useful for detecting accidental changes. It is not
        a digital signature and must not be presented as proof of authorship or
        approval.
        """
        import hashlib

        canonical = json.dumps(
            self.to_json_compatible_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def ensure_timezone_aware(value: datetime, field_name: str) -> datetime:
    """Reject timestamps whose UTC offset is unknown."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware.")
    return value


def validate_uri(value: str, field_name: str) -> str:
    """
    Validate an artifact or repository URI.

    Supported schemes are deliberately limited to URI forms useful in local and
    Azure development. Credentials must never be embedded in a URI.
    """
    parsed = urlparse(value)
    supported_schemes = {
        "https",
        "http",
        "file",
        "az",
        "azure",
        "abfs",
        "abfss",
    }
    if parsed.scheme.lower() not in supported_schemes:
        raise ValueError(
            f"{field_name} uses unsupported URI scheme {parsed.scheme!r}. "
            f"Supported schemes: {sorted(supported_schemes)}."
        )
    if parsed.username is not None or parsed.password is not None:
        raise ValueError(
            f"{field_name} must not contain embedded credentials. "
            "Use managed identity, a credential provider, or a secret store."
        )
    if parsed.scheme in {"http", "https", "az", "azure", "abfs", "abfss"}:
        if not parsed.netloc:
            raise ValueError(f"{field_name} must include a network location.")
    if parsed.scheme == "file" and not parsed.path:
        raise ValueError(f"{field_name} must include a file path.")
    return value


def validate_relative_glob(value: str, field_name: str) -> str:
    """
    Validate a repository-relative path or glob.

    Absolute paths and parent traversal are rejected because task contracts
    should describe repository scope rather than host-machine locations.
    """
    normalized = value.replace("\\", "/")
    if normalized.startswith("/"):
        raise ValueError(f"{field_name} must be repository-relative, not absolute.")
    path_without_glob = (
        normalized.replace("**", "segment")
        .replace("*", "segment")
        .replace("?", "x")
        .replace("[", "")
        .replace("]", "")
    )
    path = PurePosixPath(path_without_glob)
    if ".." in path.parts:
        raise ValueError(f"{field_name} must not contain parent-directory traversal.")
    if not normalized or normalized == ".":
        raise ValueError(f"{field_name} must not be empty or refer only to '.'.")
    return normalized


def validate_metadata(metadata: dict[str, str]) -> dict[str, str]:
    """Apply predictable limits to arbitrary metadata."""
    if len(metadata) > MAX_METADATA_ENTRIES:
        raise ValueError(
            f"metadata may contain at most {MAX_METADATA_ENTRIES} entries."
        )
    for key, value in metadata.items():
        if not key.strip():
            raise ValueError("metadata keys must not be blank.")
        if len(key) > MAX_METADATA_KEY_LENGTH:
            raise ValueError(
                f"metadata key {key!r} exceeds {MAX_METADATA_KEY_LENGTH} characters."
            )
        if len(value) > MAX_METADATA_VALUE_LENGTH:
            raise ValueError(
                f"metadata value for {key!r} exceeds "
                f"{MAX_METADATA_VALUE_LENGTH} characters."
            )
    return metadata
