"""Strict Release Gate v1 timestamp parsing and emission."""

from __future__ import annotations

import re
from datetime import UTC, datetime

_PROFILE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})T"
    r"(?P<time>\d{2}:\d{2}:\d{2})"
    r"(?P<fraction>\.\d{1,9})?"
    r"(?P<zone>Z|[+-]\d{2}:\d{2})$",
    re.ASCII,
)


def parse_timestamp(value: str) -> datetime:
    """Parse the documented RFC 3339 subset, rejecting normalization."""

    match = _PROFILE.fullmatch(value)
    if match is None:
        raise ValueError("timestamp is outside the Release Gate v1 profile")
    zone = match.group("zone")
    if zone == "-00:00":
        raise ValueError("unknown local offset is not accepted")
    if zone != "Z":
        hours = int(zone[1:3])
        minutes = int(zone[4:6])
        if hours > 14 or minutes > 59 or (hours == 14 and minutes != 0):
            raise ValueError("timestamp offset is outside the supported range")
    fraction = match.group("fraction") or ""
    # datetime validates calendar reality. It accepts only microseconds, so the
    # final three permitted fractional digits are ignored after syntax checking.
    parse_fraction = fraction[:7]
    normalized_zone = "+00:00" if zone == "Z" else zone
    try:
        return datetime.fromisoformat(
            f"{match.group('date')}T{match.group('time')}{parse_fraction}"
            f"{normalized_zone}"
        )
    except ValueError as error:
        raise ValueError("timestamp has an impossible calendar value") from error


def utc_timestamp(value: datetime | None = None) -> str:
    """Emit a stable UTC timestamp using the v1 ``Z`` spelling."""

    current = value or datetime.now(UTC)
    if current.tzinfo is None:
        raise ValueError("timestamp emission requires an aware datetime")
    utc = current.astimezone(UTC)
    if utc.microsecond:
        fraction = f".{utc.microsecond:06d}".rstrip("0")
    else:
        fraction = ""
    return utc.strftime("%Y-%m-%dT%H:%M:%S") + fraction + "Z"
