"""
Canonical hashing utilities.

HASHING RULE
------------

If two logically identical shared contracts serialize differently because of
dictionary order, their evidence hashes should NOT differ.

We therefore:

    1. serialize Pydantic models in JSON mode;
    2. sort dictionary keys;
    3. remove irrelevant whitespace;
    4. hash UTF-8 bytes with SHA-256.

This helper creates CONTENT IDENTITIES.

It does not provide signatures or attestations. Those are stronger capabilities
and remain an intentionally later implementation item.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel


def canonical_json_bytes(value: Any) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(
            mode="json",
            exclude_none=False,
        )

    serialized = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    return serialized.encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def content_sha256(value: Any) -> str:
    """
    Return the canonical SHA-256 digest of a supported JSON-compatible object.
    """

    return sha256_bytes(
        canonical_json_bytes(value)
    )

