"""Tests for cron_doctor.checks.C002_cron_semantics — TDD."""
from cron_doctor.checks.C002_cron_semantics import CronSemanticsCheck
from cron_doctor.models import Diagnosis, Severity


def test_check_id_and_name():
    check = CronSemanticsCheck()
    assert check.check_id == "C002"
    assert check.name == "cron semantics"


# --- Every-minute detection ---

def test_every_minute_warns():
    check = CronSemanticsCheck()
    issues = check.run({"name": "x", "schedule": "* * * * *"}, {"file": "f.yaml"})
    assert any(i.severity == Severity.WARNING for i in issues)


def test_step_1_in_minute_warns():
    check = CronSemanticsCheck()
    issues = check.run({"name": "x", "schedule": "*/1 * * * *"}, {"file": "f.yaml"})
    assert any(i.severity == Severity.WARNING for i in issues)


def test_6_field_every_minute_warns():
    check = CronSemanticsCheck()
    issues = check.run({"name": "x", "schedule": "* * * * * *"}, {"file": "f.yaml"})
    assert any(i.severity == Severity.WARNING for i in issues)


def test_every_5_minutes_no_warn():
    check = CronSemanticsCheck()
    issues = check.run({"name": "x", "schedule": "*/5 * * * *"}, {"file": "f.yaml"})
    assert not any(i.severity == Severity.WARNING and "every minute" in i.message.lower() for i in issues)


def test_daily_midnight_no_warn():
    check = CronSemanticsCheck()
    issues = check.run({"name": "x", "schedule": "0 0 * * *"}, {"file": "f.yaml"})
    assert issues == []


def test_sunday_midnight_no_warn():
    check = CronSemanticsCheck()
    issues = check.run({"name": "x", "schedule": "0 0 * * 0"}, {"file": "f.yaml"})
    assert issues == []


def test_workday_morning_no_warn():
    check = CronSemanticsCheck()
    issues = check.run({"name": "x", "schedule": "0 9 * * MON-FRI"}, {"file": "f.yaml"})
    assert issues == []


# --- dom=31 / 30 in February ---

def test_dom_31_info():
    check = CronSemanticsCheck()
    issues = check.run({"name": "x", "schedule": "0 0 31 * *"}, {"file": "f.yaml"})
    assert any(i.severity == Severity.INFO for i in issues)


def test_dom_30_in_feb_info():
    check = CronSemanticsCheck()
    issues = check.run({"name": "x", "schedule": "0 0 30 2 *"}, {"file": "f.yaml"})
    assert any(i.severity == Severity.INFO for i in issues)


def test_dom_29_in_feb_info():
    check = CronSemanticsCheck()
    issues = check.run({"name": "x", "schedule": "0 0 29 2 *"}, {"file": "f.yaml"})
    assert any(i.severity == Severity.INFO for i in issues)


def test_dom_15_no_info():
    check = CronSemanticsCheck()
    issues = check.run({"name": "x", "schedule": "0 0 15 * *"}, {"file": "f.yaml"})
    assert not any(i.severity == Severity.INFO and "day-of-month" in i.message.lower() for i in issues)


# --- weekday 0/7 duplication ---

def test_dow_0_and_7_warns():
    check = CronSemanticsCheck()
    issues = check.run({"name": "x", "schedule": "0 0 * * 0,7"}, {"file": "f.yaml"})
    assert any(i.severity == Severity.WARNING and ("0" in i.message and "7" in i.message) for i in issues)


def test_dow_0_alone_no_warn():
    check = CronSemanticsCheck()
    issues = check.run({"name": "x", "schedule": "0 0 * * 0"}, {"file": "f.yaml"})
    assert not any(i.severity == Severity.WARNING and "0 and 7" in i.message for i in issues)


def test_dow_7_alone_no_warn():
    """Per spec, 7 is normalized to 0 — so it's valid usage, not a duplication."""
    check = CronSemanticsCheck()
    issues = check.run({"name": "x", "schedule": "0 0 * * 7"}, {"file": "f.yaml"})
    assert not any(i.severity == Severity.WARNING and "0 and 7" in i.message for i in issues)


# --- Edge: empty / missing schedule ---

def test_missing_schedule_no_issues():
    check = CronSemanticsCheck()
    issues = check.run({"name": "x"}, {"file": "f.yaml"})
    assert issues == []


def test_empty_schedule_no_issues():
    check = CronSemanticsCheck()
    issues = check.run({"name": "x", "schedule": ""}, {"file": "f.yaml"})
    assert issues == []


def test_invalid_cron_no_issues():
    """Parse errors are C001's job."""
    check = CronSemanticsCheck()
    issues = check.run({"name": "x", "schedule": "60 * * * *"}, {"file": "f.yaml"})
    assert issues == []
