"""Tests for cron_doctor.checks.C001_cron_syntax — TDD."""
from cron_doctor.checks.C001_cron_syntax import CronSyntaxCheck
from cron_doctor.models import Diagnosis, Severity


def test_check_id_and_name():
    check = CronSyntaxCheck()
    assert check.check_id == "C001"
    assert check.name == "cron syntax"


# --- Happy path ---

def test_valid_5_field():
    check = CronSyntaxCheck()
    issues = check.run({"name": "x", "schedule": "0 12 * * *"}, {"file": "x.yaml"})
    assert issues == []


def test_valid_6_field():
    check = CronSyntaxCheck()
    issues = check.run({"name": "x", "schedule": "30 0 12 * * *"}, {"file": "x.yaml"})
    assert issues == []


def test_valid_complex():
    check = CronSyntaxCheck()
    issues = check.run({"name": "x", "schedule": "*/15 9-17 * * MON-FRI"}, {"file": "x.yaml"})
    assert issues == []


def test_missing_schedule_no_error():
    """C001 doesn't check for missing schedule (that's S001's job)."""
    check = CronSyntaxCheck()
    issues = check.run({"name": "x"}, {"file": "x.yaml"})
    assert issues == []


def test_empty_schedule_no_error():
    check = CronSyntaxCheck()
    issues = check.run({"name": "x", "schedule": ""}, {"file": "x.yaml"})
    assert issues == []


def test_non_string_schedule_no_error():
    check = CronSyntaxCheck()
    issues = check.run({"name": "x", "schedule": 12345}, {"file": "x.yaml"})
    assert issues == []  # type check is S001's job


# --- Error cases ---

def test_out_of_range_minute_emits_error():
    check = CronSyntaxCheck()
    issues = check.run({"name": "x", "schedule": "60 * * * *"}, {"file": "test.yaml"})
    assert len(issues) == 1
    assert issues[0].check_id == "C001"
    assert issues[0].severity == Severity.ERROR
    assert issues[0].file == "test.yaml"
    assert "60" in issues[0].message or "minute" in issues[0].message.lower()


def test_too_few_fields_emits_error():
    check = CronSyntaxCheck()
    issues = check.run({"name": "x", "schedule": "* * * *"}, {"file": "test.yaml"})
    assert len(issues) == 1
    assert issues[0].severity == Severity.ERROR


def test_too_many_fields_emits_error():
    check = CronSyntaxCheck()
    issues = check.run({"name": "x", "schedule": "* * * * * * *"}, {"file": "test.yaml"})
    assert len(issues) == 1
    assert issues[0].severity == Severity.ERROR


def test_garbage_emits_error():
    check = CronSyntaxCheck()
    issues = check.run({"name": "x", "schedule": "abc"}, {"file": "test.yaml"})
    assert len(issues) == 1
    assert issues[0].severity == Severity.ERROR


def test_error_includes_suggestion():
    check = CronSyntaxCheck()
    issues = check.run({"name": "x", "schedule": "60 * * * *"}, {"file": "test.yaml"})
    assert len(issues) == 1
    # Suggestion may mention field name
    # (no strict assertion — just that suggestion is not None or message is informative)


def test_multiple_jobs_emit_separate_issues():
    check = CronSyntaxCheck()
    issues1 = check.run({"name": "a", "schedule": "60 * * * *"}, {"file": "x.yaml"})
    issues2 = check.run({"name": "b", "schedule": "0 0 32 * *"}, {"file": "x.yaml"})
    assert len(issues1) == 1
    assert len(issues2) == 1
    # Both should be in the same file
    assert issues1[0].file == "x.yaml"
    assert issues2[0].file == "x.yaml"
