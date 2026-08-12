from ai_engineering_evidence.canonical import (
    canonical_json_bytes,
    canonical_sha256,
)


def test_dictionary_order_does_not_change_identity() -> None:
    first = {
        "a": 1,
        "b": 2,
        "nested": {
            "x": True,
            "y": "value",
        },
    }

    second = {
        "nested": {
            "y": "value",
            "x": True,
        },
        "b": 2,
        "a": 1,
    }

    assert canonical_json_bytes(first) == canonical_json_bytes(second)
    assert canonical_sha256(first) == canonical_sha256(second)


def test_value_change_changes_identity() -> None:
    first = {"score": 0.90}
    second = {"score": 0.91}

    assert canonical_sha256(first) != canonical_sha256(second)
