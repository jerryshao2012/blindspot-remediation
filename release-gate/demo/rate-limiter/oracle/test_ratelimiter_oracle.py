"""Independent behavioral oracle kept outside the candidate repository."""

from __future__ import annotations

import math
import random
from collections import defaultdict

import pytest

from ratelimiter import RateLimiter


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class ReferenceLimiter:
    """Brute-force model intentionally structured unlike the implementation."""

    def __init__(self, limit: int, window: float) -> None:
        self.limit = limit
        self.window = window
        self.allowed: dict[str, list[float]] = defaultdict(list)

    def allow(self, key: str, now: float) -> bool:
        active = [stamp for stamp in self.allowed[key] if now - stamp <= self.window]
        self.allowed[key] = active
        if len(active) == self.limit:
            return False
        active.append(now)
        return True


def compare_trace(limit: int, window: float, trace: list[tuple[float, str]]) -> None:
    clock = Clock()
    candidate = RateLimiter(limit, window, clock)
    reference = ReferenceLimiter(limit, window)
    for now, key in trace:
        clock.now = now
        assert candidate.allow(key) is reference.allow(key, now), (now, key)


def test_reference_model_matches_boundaries_interleaving_and_clock_rollback() -> None:
    compare_trace(
        3,
        10,
        [
            (0, "a"),
            (0, "a"),
            (0, "a"),
            (1, "a"),
            (1, "b"),
            (10, "a"),
            (10.1, "a"),
            (10.2, "a"),
            (20.3, "a"),
            (5, "a"),
        ],
    )
    compare_trace(
        3,
        10,
        [(0, "k"), (5, "k"), (6, "k"), (10.1, "k"), (10.2, "k")],
    )


def test_reference_model_matches_deterministic_generated_sequences() -> None:
    generator = random.Random(20260821)
    for limit in (1, 2, 4):
        for window in (0.5, 10.0, 60.0):
            now = 0.0
            trace: list[tuple[float, str]] = []
            for _ in range(120):
                now += generator.choice((0.0, window, window + 0.01, 0.1))
                trace.append((now, generator.choice(("a", "b", "c"))))
            compare_trace(limit, window, trace)


def test_backward_clock_jump_cannot_reopen_quota() -> None:
    clock = Clock()
    limiter = RateLimiter(1, 60, clock)
    clock.now = 100
    assert limiter.allow("key") is True
    clock.now = 50
    assert limiter.allow("key") is False


@pytest.mark.parametrize(
    ("limit", "window", "parameter"),
    [
        (0, 1.0, "limit"),
        (-1, 1.0, "limit"),
        (1, 0.0, "window_seconds"),
        (1, -1.0, "window_seconds"),
        (1, math.nan, "window_seconds"),
        (1, math.inf, "window_seconds"),
        (1, -math.inf, "window_seconds"),
    ],
)
def test_constructor_rejects_unsafe_values(
    limit: int, window: float, parameter: str
) -> None:
    with pytest.raises(ValueError, match=parameter):
        RateLimiter(limit, window, lambda: 0.0)


def test_denials_do_not_change_internal_storage() -> None:
    clock = Clock()
    limiter = RateLimiter(1, 60, clock)
    assert limiter.allow("key") is True
    before = {key: tuple(stamps) for key, stamps in limiter._hits.items()}
    clock.now = 10
    assert [limiter.allow("key") for _ in range(100)] == [False] * 100
    assert {key: tuple(stamps) for key, stamps in limiter._hits.items()} == before
