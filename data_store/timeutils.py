"""UTC ISO-8601 timestamp helpers for the data store.

Every time column in the store (``event_time`` and ``knowable_time``) is stored
as text in ONE canonical shape::

    2026-06-15T00:00:00Z

That is: zero-padded calendar date, a ``T`` separator, 24-hour time to whole
seconds, and a literal ``Z`` meaning UTC ("Zulu" time). No sub-second part, no
numeric ``+00:00`` offset, no local time.

Why one rigid shape? Because the store compares timestamps as plain text. With a
single canonical form, lexical (text) ordering equals chronological ordering and
the point-in-time guard ``knowable_time <= as_of`` is an exact, unambiguous
string comparison. A stray ``+00:00`` or a missing ``Z`` would silently break
that ordering -- so :func:`validate_iso` rejects anything non-canonical at the
door.
"""

from __future__ import annotations

from datetime import datetime, timezone

# Pattern for the canonical shape. The trailing ``Z`` is a *literal* character
# here (strptime/strftime match it verbatim); we attach real UTC tzinfo
# ourselves in parse_iso, since the literal carries no timezone on its own.
ISO_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

# A concrete example, reused in error messages so callers see the target shape.
_EXAMPLE = "2026-06-15T00:00:00Z"


def to_utc_iso(dt: datetime) -> str:
    """Render ``dt`` as a canonical UTC ISO-8601 string.

    A timezone-aware ``dt`` is converted to UTC. A naive ``dt`` (no tzinfo) is
    *assumed to already be UTC* -- code that works in local time must attach
    tzinfo before calling. Sub-second precision is dropped (the store keeps
    whole-second timestamps only).
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime(ISO_FORMAT)


def validate_iso(value: str) -> str:
    """Return ``value`` unchanged iff it is a canonical UTC ISO-8601 string.

    Raise ``ValueError`` otherwise. This is the store's boundary guard: every
    timestamp entering the store is validated so a malformed or non-UTC value
    can never corrupt point-in-time ordering.

    Strictness note: ``strptime`` alone is lenient (it would accept the
    non-zero-padded ``2026-6-5T...``), so we additionally require that
    re-rendering the parsed value reproduces the input byte-for-byte.
    """
    try:
        parsed = datetime.strptime(value, ISO_FORMAT)
    except (ValueError, TypeError) as exc:
        raise ValueError(
            f"not a canonical UTC ISO-8601 timestamp "
            f"(want e.g. {_EXAMPLE!r}): {value!r}"
        ) from exc
    if parsed.strftime(ISO_FORMAT) != value:
        raise ValueError(
            f"timestamp is not in canonical zero-padded form "
            f"(want e.g. {_EXAMPLE!r}): {value!r}"
        )
    return value


def parse_iso(value: str) -> datetime:
    """Parse a canonical UTC ISO-8601 string into a tz-aware UTC datetime."""
    validate_iso(value)
    return datetime.strptime(value, ISO_FORMAT).replace(tzinfo=timezone.utc)


def now_utc_iso() -> str:
    """Current wall-clock time as a canonical UTC ISO-8601 string."""
    return to_utc_iso(datetime.now(timezone.utc))
