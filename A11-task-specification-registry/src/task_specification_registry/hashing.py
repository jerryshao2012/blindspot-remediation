"""Canonical content hashing for governed specifications."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel


def canonical_json_bytes(value: Any) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def specification_hash(value: Any) -> str:
    return hashlib.sha256(
        canonical_json_bytes(value)
    ).hexdigest()
