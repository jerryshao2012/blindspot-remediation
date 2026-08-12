from __future__ import annotations

import json
from pathlib import Path

from ai_engineering_contracts.schema_export import (
    PUBLIC_CONTRACTS,
    export_schemas,
)


def test_schema_export_writes_every_public_contract(tmp_path: Path) -> None:
    written = export_schemas(tmp_path)
    assert len(written) == len(PUBLIC_CONTRACTS)
    for path in written:
        assert path.exists()
        schema = json.loads(path.read_text(encoding="utf-8"))
        assert schema["$schema"] == (
            "https://json-schema.org/draft/2020-12/schema"
        )
        assert "$id" in schema
        assert "properties" in schema
