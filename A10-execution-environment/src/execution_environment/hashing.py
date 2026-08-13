"""Canonical hashing utilities used for provenance."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    """
    Convert supported configuration objects into stable JSON.

    Stable serialization matters because fingerprints should change because
    configuration changed, not because dictionary ordering changed.
    """

    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")

    serialized = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    return serialized.encode("utf-8")


def fingerprint(value: Any) -> str:
    return sha256_bytes(
        canonical_json_bytes(value)
    )
