"""RED tests for cron_doctor.exceptions — must FAIL until exceptions.py is implemented."""
import pytest
from cron_doctor.exceptions import (
    CronDoctorError,
    ParseError,
    InvalidCronExpression,
    UnreadableFileError,
    SchemaViolation,
)


def test_cron_doctor_error_is_exception():
    assert issubclass(CronDoctorError, Exception)


def test_all_subclasses_inherit_from_cron_doctor_error():
    for cls in (ParseError, InvalidCronExpression, UnreadableFileError, SchemaViolation):
        assert issubclass(cls, CronDoctorError), f"{cls.__name__} must inherit from CronDoctorError"


def test_parse_error_carries_location_attributes():
    err = ParseError("cron.yaml", "bad indent", line=3, column=7)
    assert err.file == "cron.yaml"
    assert err.message == "bad indent"
    assert err.line == 3
    assert err.column == 7
    assert str(err)


def test_parse_error_location_optional():
    err = ParseError("cron.yaml", "unknown")
    assert err.line is None
    assert err.column is None


def test_invalid_cron_expression_carries_field_info():
    err = InvalidCronExpression("60 * * * *", "minute out of range", field_index=0, field_name="minute")
    assert err.expression == "60 * * * *"
    assert err.field_index == 0
    assert err.field_name == "minute"
    assert "minute" in str(err).lower() or "60" in str(err)


def test_invalid_cron_expression_field_optional():
    err = InvalidCronExpression("garbage", "too few fields")
    assert err.field_index is None
    assert err.field_name is None


def test_unreadable_file_error():
    err = UnreadableFileError("/no/such.yaml", "No such file")
    assert err.path == "/no/such.yaml"
    assert "No such file" in str(err)


def test_schema_violation_with_key():
    err = SchemaViolation("cron.yaml", "unknown key 'foo'", key="foo")
    assert err.file == "cron.yaml"
    assert err.key == "foo"


def test_schema_violation_without_key():
    err = SchemaViolation("cron.yaml", "missing 'name'")
    assert err.key is None


def test_catchable_as_cron_doctor_error():
    for cls, args in [
        (ParseError, ("f", "m")),
        (InvalidCronExpression, ("e", "m")),
        (UnreadableFileError, ("p", "r")),
        (SchemaViolation, ("f", "r")),
    ]:
        try:
            raise cls(*args)
        except CronDoctorError:
            pass
        else:
            pytest.fail(f"{cls.__name__} not catchable as CronDoctorError")
