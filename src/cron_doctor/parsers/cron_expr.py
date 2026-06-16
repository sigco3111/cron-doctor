"""Cron expression parser — pure stdlib, zero external deps.

Supports two layouts, distinguished by field count:

  5-field (classic crontab):      min hour dom mon dow
  6-field (Hermes style):         sec min hour dom mon dow  (second is first)

Each field supports:

    *              all valid values for that field
    N              single value
    N-M            range, inclusive
    */S            step every S starting from the field's minimum
    N-M/S          ranged step
    A,B,C          list (each item may itself use any of the forms above)
    JAN-DEC        month names (case-insensitive)
    SUN-SAT        weekday names (case-insensitive)

Field ranges (inclusive):

    second, minute:  0-59
    hour:            0-23
    day (dom):       1-31
    month:           1-12
    weekday:         0-6  (with 7 normalized to 0, matching Vixie cron)

Raises:
    InvalidCronExpression: on any parse error, with ``.field_name`` and
        ``.field_index`` (0-based) set whenever a specific field can be
        identified.
"""

from __future__ import annotations

from typing import List, NamedTuple, Optional, Tuple

from cron_doctor.exceptions import InvalidCronExpression


# (lo, hi) inclusive ranges per field name.
_FIELD_RANGES: dict[str, Tuple[int, int]] = {
    "second":  (0, 59),
    "minute":  (0, 59),
    "hour":    (0, 23),
    "day":     (1, 31),
    "month":   (1, 12),
    "weekday": (0, 6),
}

_MONTH_NAMES: dict[str, int] = {
    "JAN": 1,  "FEB": 2,  "MAR": 3,  "APR": 4,  "MAY": 5,  "JUN": 6,
    "JUL": 7,  "AUG": 8,  "SEP": 9,  "OCT": 10, "NOV": 11, "DEC": 12,
}

_WEEKDAY_NAMES: dict[str, int] = {
    "SUN": 0, "MON": 1, "TUE": 2, "WED": 3, "THU": 4, "FRI": 5, "SAT": 6,
}


class CronExpression(NamedTuple):
    """A parsed cron expression with each field expanded to a sorted list.

    Attributes:
        minute:   valid minute values, 0-59.
        hour:     valid hour values, 0-23.
        day:      valid day-of-month values, 1-31.
        month:    valid month values, 1-12.
        weekday:  valid day-of-week values, 0-6 (0 = Sunday).
        second:   valid second values (0-59) for 6-field expressions,
                  or ``None`` for 5-field expressions.
    """

    minute: List[int]
    hour: List[int]
    day: List[int]
    month: List[int]
    weekday: List[int]
    second: Optional[List[int]] = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_name(token: str, field_name: str) -> Optional[int]:
    """If *token* is a valid name for *field_name*, return its int value."""
    upper = token.upper()
    if field_name == "month" and upper in _MONTH_NAMES:
        return _MONTH_NAMES[upper]
    if field_name == "weekday" and upper in _WEEKDAY_NAMES:
        return _WEEKDAY_NAMES[upper]
    return None


def _resolve_value(token: str, field_name: str) -> int:
    """Resolve a single field token (name or integer) to an int.

    Weekday value ``7`` is normalized to ``0`` here so range/step
    expansion can treat it uniformly.
    """
    token = token.strip()
    if not token:
        raise InvalidCronExpression(
            f"<{field_name}>", f"empty value in {field_name!r}",
            field_name=field_name,
        )

    named = _resolve_name(token, field_name)
    if named is not None:
        value = named
    else:
        try:
            value = int(token)
        except ValueError as exc:
            raise InvalidCronExpression(
                f"<{field_name}>", f"invalid token {token!r} in {field_name!r}",
                field_name=field_name,
            ) from exc

    if field_name == "weekday" and value == 7:
        value = 0
    return value


def _resolve_base(base: str, field_name: str) -> Tuple[int, int]:
    """Resolve the *base* part of a field (the part before ``/step``) to a
    ``(start, end)`` pair, both inclusive.

    Handles ``*`` (full field range), ``N-M`` (range), and ``N`` (single
    value, returned as ``(N, N)``).
    """
    base = base.strip()
    if not base:
        raise InvalidCronExpression(
            f"<{field_name}>", f"empty base in {field_name!r}",
            field_name=field_name,
        )

    if base == "*":
        lo, hi = _FIELD_RANGES[field_name]
        return lo, hi

    if "-" in base:
        a_str, b_str = base.split("-", 1)
        a = _resolve_value(a_str, field_name)
        b = _resolve_value(b_str, field_name)
        return a, b

    v = _resolve_value(base, field_name)
    return v, v


def _expand_field(
    token: str, field_name: str, lo: int, hi: int,
) -> List[int]:
    """Expand a single cron field token into a sorted, deduplicated list.

    Raises ``InvalidCronExpression`` with ``field_name`` set whenever the
    token is malformed or out of range.
    """
    def _err(message: str) -> InvalidCronExpression:
        return InvalidCronExpression(
            f"<{field_name}>", message, field_name=field_name,
        )

    values: set[int] = set()

    for part in token.split(","):
        part = part.strip()
        if not part:
            raise _err(f"empty list item in {field_name!r}")

        if "/" in part:
            base, step_str = part.split("/", 1)
            try:
                step = int(step_str)
            except ValueError:
                raise _err(
                    f"invalid step {step_str!r} in {field_name!r}",
                )
            if step <= 0:
                raise _err(
                    f"step must be positive (got {step}) — "
                    f"division by zero not allowed",
                )
            start, end = _resolve_base(base, field_name)
        else:
            step = 1
            start, end = _resolve_base(part, field_name)

        if start > end:
            raise _err(
                f"range start {start} greater than end {end} for {field_name}",
            )

        for v in range(start, end + 1, step):
            if field_name == "weekday" and v == 7:
                v = 0
            if v < lo or v > hi:
                raise _err(
                    f"value {v} out of range for {field_name} "
                    f"(must be {lo}-{hi})",
                )
            values.add(v)

    return sorted(values)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse(expr: str) -> CronExpression:
    """Parse a 5-field or 6-field cron expression.

    See the module docstring for the full grammar.

    Raises:
        InvalidCronExpression: on any parse error. ``field_index`` is
            0-based and points at the offending field when identifiable,
            or ``-1`` for structural errors (wrong field count, blank
            input).
    """
    if expr is None or not str(expr).strip():
        raise InvalidCronExpression(
            expr or "", "empty expression", field_index=-1,
        )

    fields = expr.split()

    if len(fields) == 5:
        field_names = ["minute", "hour", "day", "month", "weekday"]
    elif len(fields) == 6:
        field_names = ["second", "minute", "hour", "day", "month", "weekday"]
    else:
        raise InvalidCronExpression(
            expr,
            f"expected 5 or 6 whitespace-separated fields, got {len(fields)}",
            field_index=-1,
        )

    expanded: List[List[int]] = []
    for i, (token, name) in enumerate(zip(fields, field_names)):
        lo, hi = _FIELD_RANGES[name]
        try:
            values = _expand_field(token, name, lo, hi)
        except InvalidCronExpression as exc:
            # Always set field_index to the current position so callers
            # can pinpoint the bad field.
            if exc.field_index is None:
                exc.field_index = i
            raise
        if not values:
            raise InvalidCronExpression(
                expr, f"field {name!r} matched no values",
                field_index=i, field_name=name,
            )
        expanded.append(values)

    if len(fields) == 5:
        return CronExpression(
            minute=expanded[0],
            hour=expanded[1],
            day=expanded[2],
            month=expanded[3],
            weekday=expanded[4],
            second=None,
        )
    return CronExpression(
        second=expanded[0],
        minute=expanded[1],
        hour=expanded[2],
        day=expanded[3],
        month=expanded[4],
        weekday=expanded[5],
    )


__all__ = ["CronExpression", "parse"]
