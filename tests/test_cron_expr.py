"""Tests for cron_doctor.parsers.cron_expr — TDD."""
import pytest
from cron_doctor.exceptions import InvalidCronExpression
from cron_doctor.parsers.cron_expr import CronExpression, parse


# --- 5-field happy path ---

def test_parse_5_field_all_stars():
    e = parse("* * * * *")
    assert e.minute == list(range(0, 60))
    assert e.hour == list(range(0, 24))
    assert e.day == list(range(1, 32))
    assert e.month == list(range(1, 13))
    assert e.weekday == [0, 1, 2, 3, 4, 5, 6]  # 0-6
    assert e.second is None


def test_parse_5_field_specific():
    e = parse("0 12 * * *")
    assert e.minute == [0]
    assert e.hour == [12]
    assert e.second is None


def test_parse_5_field_range():
    e = parse("0 9-17 * * *")
    assert e.hour == [9, 10, 11, 12, 13, 14, 15, 16, 17]


def test_parse_5_field_step():
    e = parse("*/15 * * * *")
    assert e.minute == [0, 15, 30, 45]


def test_parse_5_field_ranged_step():
    e = parse("10-30/5 * * * *")
    assert e.minute == [10, 15, 20, 25, 30]


def test_parse_5_field_list():
    e = parse("1,15,45 * * * *")
    assert e.minute == [1, 15, 45]


def test_parse_5_field_weekday_names():
    e = parse("0 0 * * SUN")
    assert e.weekday == [0]
    e = parse("0 0 * * MON-FRI")
    assert e.weekday == [1, 2, 3, 4, 5]
    e = parse("0 0 * * sun")
    assert e.weekday == [0]


def test_parse_5_field_month_names():
    e = parse("0 0 1 JAN *")
    assert e.month == [1]
    e = parse("0 0 1 jan-dec *")
    assert e.month == list(range(1, 13))


# --- 6-field (Hermes) ---

def test_parse_6_field_all_stars():
    e = parse("* * * * * *")
    assert e.second == list(range(0, 60))
    assert e.minute == list(range(0, 60))
    assert e.hour == list(range(0, 24))


def test_parse_6_field_specific():
    e = parse("30 0 12 * * *")
    assert e.second == [30]
    assert e.minute == [0]
    assert e.hour == [12]
    assert e.second is not None


# --- 7 normalized to 0 ---

def test_weekday_7_normalized_to_0():
    e = parse("0 0 * * 7")
    assert e.weekday == [0]


def test_weekday_0_and_7_list():
    e = parse("0 0 * * 0,7")
    assert e.weekday == [0]  # dedup


# --- Errors ---

def test_too_few_fields_raises():
    with pytest.raises(InvalidCronExpression) as exc:
        parse("* * * *")
    assert exc.value.field_index is not None


def test_too_many_fields_raises():
    with pytest.raises(InvalidCronExpression):
        parse("* * * * * * *")


def test_empty_string_raises():
    with pytest.raises(InvalidCronExpression):
        parse("")


def test_whitespace_only_raises():
    with pytest.raises(InvalidCronExpression):
        parse("   ")


def test_out_of_range_minute_raises():
    with pytest.raises(InvalidCronExpression) as exc:
        parse("60 * * * *")
    assert exc.value.field_name == "minute"
    assert exc.value.field_index == 0


def test_out_of_range_hour_raises():
    with pytest.raises(InvalidCronExpression) as exc:
        parse("0 24 * * *")
    assert exc.value.field_name == "hour"
    assert exc.value.field_index == 1


def test_out_of_range_day_raises():
    with pytest.raises(InvalidCronExpression) as exc:
        parse("0 0 32 * *")
    assert exc.value.field_name == "day"


def test_out_of_range_month_raises():
    with pytest.raises(InvalidCronExpression) as exc:
        parse("0 0 1 13 *")
    assert exc.value.field_name == "month"


def test_out_of_range_weekday_raises():
    with pytest.raises(InvalidCronExpression) as exc:
        parse("0 0 * * 8")
    assert exc.value.field_name == "weekday"


def test_division_by_zero_step_raises():
    with pytest.raises(InvalidCronExpression) as exc:
        parse("*/0 * * * *")
    assert "step" in str(exc.value).lower() or "divide" in str(exc.value).lower()


def test_invalid_token_raises():
    with pytest.raises(InvalidCronExpression):
        parse("abc * * * *")


def test_garbage_in_field_raises():
    with pytest.raises(InvalidCronExpression):
        parse("0 0 abc * *")


def test_range_start_greater_than_end_raises():
    with pytest.raises(InvalidCronExpression):
        parse("5-1 * * * *")


def test_range_out_of_bounds_raises():
    with pytest.raises(InvalidCronExpression) as exc:
        parse("0 0 1-40 * *")
    assert exc.value.field_name == "day"
