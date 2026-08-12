"""
Tests for content identity.

These tests are intentionally simple because this function will underpin
evidence and specification identities throughout the POC.
"""

from ai_engineering_contracts import content_sha256


def test_dictionary_order_does_not_change_digest() -> None:
    first = {
        "a": 1,
        "b": 2,
    }

    second = {
        "b": 2,
        "a": 1,
    }

    assert content_sha256(first) == content_sha256(second)


def test_content_change_changes_digest() -> None:
    assert (
        content_sha256({"value": 1})
        != content_sha256({"value": 2})
    )


def test_sha256_has_expected_length() -> None:
    digest = content_sha256(
        {"example": "contract"}
    )

    assert len(digest) == 64

