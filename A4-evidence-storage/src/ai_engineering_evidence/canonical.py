"""
Canonical JSON and cryptographic digest utilities.

A run manifest must have a stable identity independent of formatting.

For example, these ordinary JSON documents are semantically equivalent:

    {"a": 1, "b": 2}

and

    {
      "b": 2,
      "a": 1
    }

Their human formatting differs.

Their canonical representation must not.

This module therefore provides the only serialization used when calculating
manifest identities.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel


def sha256_bytes(content: bytes) -> str:
    """Return the lowercase hexadecimal SHA-256 digest of bytes."""

    return hashlib.sha256(content).hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    """
    Convert a JSON-compatible object into deterministic UTF-8 bytes.

    Important properties:

    * dictionary keys are sorted;
    * whitespace is removed;
    * UTF-8 is used;
    * NaN and Infinity are rejected;
    * Pydantic models are converted through JSON-compatible serialization.

    This is sufficient for the POC's own manifests because every producer and
    verifier uses this exact implementation.

    If manifests later cross organizational or language boundaries, adopt a
    formally standardized JSON canonicalization scheme rather than creating a
    second home-grown representation.
    """

    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")

    text = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )

    return text.encode("utf-8")


def canonical_sha256(value: Any) -> str:
    """Calculate the SHA-256 identity of a canonical JSON value."""

    return sha256_bytes(canonical_json_bytes(value))


def pretty_json_bytes(value: Any) -> bytes:
    """Create deterministic but human-readable JSON."""

    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")

    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")
