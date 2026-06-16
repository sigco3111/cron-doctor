"""Tests for cron_doctor.checks.T001_timezone — TDD.

T001 validates the `timezone` field of a cron job using the stdlib
`zoneinfo.ZoneInfo`. The check is WARNING severity (not ERROR) because
timezone is optional and a missing/bad value is usually a typo, not a
hard failure.

RED: this file imports `TimezoneCheck` and `FixProposal`, neither of which
exists yet. The test must fail before we write the implementation.
"""
from cron_doctor.checks.T001_timezone import TimezoneCheck
from cron_doctor.models import Diagnosis, Severity


def test_check_id_and_name():
    check = TimezoneCheck()
    assert check.check_id == "T001"
    assert check.name == "timezone"


# --- Happy path ---

def test_no_timezone_no_issue():
    check = TimezoneCheck()
    issues = check.run({"name": "a", "schedule": "0 * * * *", "prompt": "x"}, {"file": "f.yaml"})
    assert issues == []


def test_utc_valid():
    check = TimezoneCheck()
    issues = check.run({"name": "a", "timezone": "UTC"}, {"file": "f.yaml"})
    assert issues == []


def test_america_new_york_valid():
    check = TimezoneCheck()
    issues = check.run({"name": "a", "timezone": "America/New_York"}, {"file": "f.yaml"})
    assert issues == []


def test_asia_seoul_valid():
    check = TimezoneCheck()
    issues = check.run({"name": "a", "timezone": "Asia/Seoul"}, {"file": "f.yaml"})
    assert issues == []


def test_europe_london_valid():
    check = TimezoneCheck()
    issues = check.run({"name": "a", "timezone": "Europe/London"}, {"file": "f.yaml"})
    assert issues == []


# --- Error cases ---

def test_invalid_timezone_warns():
    check = TimezoneCheck()
    issues = check.run({"name": "a", "timezone": "Foo/Bar"}, {"file": "f.yaml"})
    assert len(issues) == 1
    assert issues[0].check_id == "T001"
    assert issues[0].severity == Severity.WARNING
    assert "Foo/Bar" in issues[0].message


def test_empty_timezone_warns():
    check = TimezoneCheck()
    issues = check.run({"name": "a", "timezone": ""}, {"file": "f.yaml"})
    assert len(issues) == 1
    assert issues[0].severity == Severity.WARNING


def test_non_string_timezone_warns():
    check = TimezoneCheck()
    issues = check.run({"name": "a", "timezone": 12345}, {"file": "f.yaml"})
    assert len(issues) == 1
    assert issues[0].severity == Severity.WARNING


def test_non_dict_job_no_crash():
    check = TimezoneCheck()
    issues = check.run("not a dict", {"file": "f.yaml"})
    assert issues == []


def test_timezone_uses_file_from_context():
    check = TimezoneCheck()
    issues = check.run({"name": "a", "timezone": "Invalid/Zone"}, {"file": "my.yaml"})
    assert issues[0].file == "my.yaml"


def test_propose_fix_returns_proposal_for_invalid_tz():
    """Per check: propose_fix static method, used by core.propose_fixes()."""
    check = TimezoneCheck()
    diag = Diagnosis(
        check_id="T001",
        severity=Severity.WARNING,
        message="Invalid timezone 'Foo/Bar'",
        file="f.yaml",
        line=3,
    )
    original = "  timezone: Foo/Bar"
    proposal = check.propose_fix(diag, original)
    assert proposal is not None
    assert "UTC" in proposal.replacement
    assert "Foo/Bar" in original
