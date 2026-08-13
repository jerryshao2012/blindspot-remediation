from execution_environment.hashing import (
    fingerprint,
)


def test_fingerprint_is_stable_for_dict_order() -> None:
    first = {
        "a": 1,
        "b": 2,
    }

    second = {
        "b": 2,
        "a": 1,
    }

    assert fingerprint(first) == fingerprint(second)


def test_fingerprint_changes_with_content() -> None:
    assert fingerprint({"a": 1}) != fingerprint({"a": 2})
