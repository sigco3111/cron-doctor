"""Golden file tests: end-to-end validation of the diagnose() API against
hand-curated fixture YAMLs.

v0.1.0 fixtures:
  - valid.yaml               — no issues
  - invalid-cron.yaml        — C001 ERROR
  - circular-dep.yaml        — D001 cycle ERROR
  - broken-context.yaml      — D001 broken-ref ERROR
  - semantic-warnings.yaml   — C002 mix (WARNING + INFO)

v0.2.0 fixtures:
  - t001_timezone.yaml       — T001 WARNING for invalid TZ
  - p001_prompt.yaml         — P001 ERROR for embedded secrets + WARNING for long
  - m001_mcp.yaml            — M001 ERROR for broken toolset refs + WARNING for dup
  - fix-dryrun.yaml          — mixed fixable + unfixable for end-to-end fix test
"""
from pathlib import Path

import pytest

from cron_doctor.core import diagnose, fix
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
    """Running diagnose() on the fixtures dir should find all 11 YAMLs (5 v0.1.0 + 4 v0.2.0 + 2 v0.3.0 watch-test)."""
    results = diagnose(FIXTURES)
    yaml_count = sum(1 for r in results if r.file.endswith((".yaml", ".yml")))
    assert yaml_count == 11


# --- t001_timezone.yaml ---

def test_t001_warns_on_invalid_timezone():
    results = diagnose(FIXTURES / "t001_timezone.yaml")
    t001_warnings = _issues_for("T001", results, severity=Severity.WARNING)
    assert any("Foo/Bar" in i.message for i in t001_warnings)
    assert any("empty" in i.message.lower() for i in t001_warnings)


def test_t001_no_issue_for_utc():
    results = diagnose(FIXTURES / "t001_timezone.yaml")
    t001_warnings = _issues_for("T001", results, severity=Severity.WARNING)
    utc_warning = [i for i in t001_warnings if "UTC" in i.message and "Foo" not in i.message]
    assert utc_warning == []


# --- p001_prompt.yaml ---

def test_p001_detects_openai_key():
    results = diagnose(FIXTURES / "p001_prompt.yaml")
    p001_errors = _issues_for("P001", results, severity=Severity.ERROR)
    openai = [i for i in p001_errors if "sk-" in i.message]
    assert len(openai) >= 1


def test_p001_detects_aws_key():
    results = diagnose(FIXTURES / "p001_prompt.yaml")
    p001_errors = _issues_for("P001", results, severity=Severity.ERROR)
    aws = [i for i in p001_errors if "AWS" in i.message]
    assert len(aws) >= 1


def test_p001_warns_on_long_prompt():
    results = diagnose(FIXTURES / "p001_prompt.yaml")
    p001_warnings = _issues_for("P001", results, severity=Severity.WARNING)
    long_warn = [i for i in p001_warnings if "chars" in i.message.lower() or "long" in i.message.lower()]
    assert len(long_warn) >= 1


def test_p001_no_fp_on_placeholder_password():
    results = diagnose(FIXTURES / "p001_prompt.yaml")
    p001_errors = _issues_for("P001", results, severity=Severity.ERROR)
    fp = [i for i in p001_errors if "CHANGEME" in i.message or "placeholder" in i.message]
    assert fp == []


# --- m001_mcp.yaml ---

def test_m001_errors_for_broken_refs():
    results = diagnose(FIXTURES / "m001_mcp.yaml")
    m001_errors = _issues_for("M001", results, severity=Severity.ERROR)
    assert any("nonexistent" in i.message for i in m001_errors)
    assert any("another_missing" in i.message for i in m001_errors)


def test_m001_warns_on_duplicate_toolset():
    results = diagnose(FIXTURES / "m001_mcp.yaml")
    m001_warnings = _issues_for("M001", results, severity=Severity.WARNING)
    dup = [i for i in m001_warnings if "duplicate" in i.message.lower() and "search" in i.message]
    assert len(dup) >= 1


# --- fix-dryrun.yaml (end-to-end fix test) ---

def test_fix_dryrun_proposes_fixable_issues():
    results = diagnose(FIXTURES / "fix-dryrun.yaml")
    all_issues = [i for r in results for i in r.issues]
    t001 = [i for i in all_issues if i.check_id == "T001"]
    m001 = [i for i in all_issues if i.check_id == "M001"]
    c001 = [i for i in all_issues if i.check_id == "C001"]
    assert len(t001) >= 1
    assert len(m001) >= 1
    assert len(c001) >= 1  # C001 is unfixable but should still be detected


def test_fix_dryrun_proposes_fixes_for_fixable_only():
    """propose_fixes() should yield proposals for T001 + M001 but NOT C001."""
    proposals = fix(FIXTURES / "fix-dryrun.yaml", dry_run=True)
    check_ids = {p.check_id for p in proposals["proposals"]}
    assert "T001" in check_ids
    assert "M001" in check_ids
    assert "C001" not in check_ids  # C001 has no auto-fix


def test_fix_apply_resolves_fixable_keeps_unfixable(tmp_path):
    """After --apply, T001 + M001 issues gone; C001 remains."""
    import shutil
    src = FIXTURES / "fix-dryrun.yaml"
    dst = tmp_path / "fix-dryrun.yaml"
    shutil.copy(src, dst)
    result = fix(dst, dry_run=False)
    assert result["applied"] >= 2  # T001 + M001
    new_text = dst.read_text()
    assert "UTC" in new_text  # T001 fixed
    assert "missing_toolset" not in new_text or "#" in new_text  # M001 commented
    # C001 issue should still be in the file (60 * * * * * is unfixable)
    assert "60 * * * *" in new_text
