"""Golden file tests: end-to-end validation of the diagnose() API against
hand-curated fixture YAMLs.

These tests prove that:
  - valid.yaml produces no issues
  - invalid-cron.yaml produces C001 ERROR
  - circular-dep.yaml produces D001 cycle ERROR
  - broken-context.yaml produces D001 broken-ref ERROR
  - semantic-warnings.yaml produces C002 mix (WARNING + INFO)
"""
from pathlib import Path

import pytest

from cron_doctor.core import diagnose
from cron_doctor.models import Severity


FIXTURES = Path(__file__).parent / "fixtures"


def _issues_for(check_id: str, results, severity=None):
    out = []
    for r in results:
        for i in r.issues:
            if i.check_id != check_id:
                continue
            if severity is not None and i.severity != severity:
                continue
            out.append(i)
    return out


# --- valid.yaml ---

def test_valid_yaml_no_issues():
    results = diagnose(FIXTURES / "valid.yaml")
    assert len(results) == 1
    assert results[0].issues == []


def test_valid_yaml_loaded_three_jobs():
    results = diagnose(FIXTURES / "valid.yaml")
    assert len(results[0].jobs) == 3


# --- invalid-cron.yaml ---

def test_invalid_cron_emits_c001_error():
    results = diagnose(FIXTURES / "invalid-cron.yaml")
    c001_errors = _issues_for("C001", results, severity=Severity.ERROR)
    assert len(c001_errors) >= 1
    assert "60" in c001_errors[0].message or "minute" in c001_errors[0].message.lower()


def test_invalid_cron_no_other_checks_triggered():
    """For a single bad-cron job, no D001/S001 issues should be raised."""
    results = diagnose(FIXTURES / "invalid-cron.yaml")
    for r in results:
        for i in r.issues:
            assert i.check_id in ("C001", "Y001"), f"unexpected: {i.check_id}"


# --- circular-dep.yaml ---

def test_circular_dep_emits_d001_cycle_error():
    results = diagnose(FIXTURES / "circular-dep.yaml")
    d001_errors = _issues_for("D001", results, severity=Severity.ERROR)
    cycle_errors = [i for i in d001_errors if "ircular" in i.message.lower()]
    assert len(cycle_errors) >= 1


def test_circular_dep_message_mentions_all_jobs():
    results = diagnose(FIXTURES / "circular-dep.yaml")
    d001_errors = _issues_for("D001", results, severity=Severity.ERROR)
    cycle_errors = [i for i in d001_errors if "ircular" in i.message.lower()]
    msg = " ".join(i.message for i in cycle_errors)
    for name in ("job_a", "job_b", "job_c"):
        assert name in msg, f"cycle message should mention {name}: {msg}"


# --- broken-context.yaml ---

def test_broken_context_emits_d001_error():
    results = diagnose(FIXTURES / "broken-context.yaml")
    d001_errors = _issues_for("D001", results, severity=Severity.ERROR)
    assert len(d001_errors) >= 1
    assert "nonexistent" in d001_errors[0].message


# --- semantic-warnings.yaml ---

def test_semantic_every_minute_warning():
    results = diagnose(FIXTURES / "semantic-warnings.yaml")
    c002_warnings = _issues_for("C002", results, severity=Severity.WARNING)
    every_min = [i for i in c002_warnings if "every minute" in i.message.lower()]
    assert len(every_min) >= 1


def test_semantic_leap_year_info():
    results = diagnose(FIXTURES / "semantic-warnings.yaml")
    c002_info = _issues_for("C002", results, severity=Severity.INFO)
    leap = [i for i in c002_info if "leap" in i.message.lower() or "feb" in i.message.lower()]
    assert len(leap) >= 1


def test_semantic_dow_0_and_7_warning():
    results = diagnose(FIXTURES / "semantic-warnings.yaml")
    c002_warnings = _issues_for("C002", results, severity=Severity.WARNING)
    dup = [i for i in c002_warnings if "0 and 7" in i.message or ("0" in i.message and "7" in i.message)]
    assert len(dup) >= 1


# --- directory mode on fixtures ---

def test_directory_mode_processes_all_yaml_fixtures(tmp_path: Path):
    """Running diagnose() on the fixtures dir should find all 5 YAMLs."""
    results = diagnose(FIXTURES)
    yaml_count = sum(1 for r in results if r.file.endswith((".yaml", ".yml")))
    assert yaml_count == 5
