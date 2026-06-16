"""Tests for cron_doctor.core — TDD."""
import textwrap
from pathlib import Path

import pytest

from cron_doctor.core import diagnose
from cron_doctor.models import CheckResult, Severity
from cron_doctor.checks import default_checks


# --- Single file ---

def test_diagnose_file_returns_list_with_one_result(tmp_path: Path):
    f = tmp_path / "ok.yaml"
    f.write_text("- name: a\n  schedule: '0 * * * *'\n  prompt: x\n")
    results = diagnose(f)
    assert isinstance(results, list)
    assert len(results) == 1
    assert isinstance(results[0], CheckResult)
    assert results[0].file == str(f)


def test_diagnose_valid_file_no_issues(tmp_path: Path):
    f = tmp_path / "ok.yaml"
    f.write_text("- name: a\n  schedule: '0 12 * * *'\n  prompt: x\n")
    results = diagnose(f)
    assert results[0].issues == []


def test_diagnose_invalid_cron_emits_c001_error(tmp_path: Path):
    f = tmp_path / "bad.yaml"
    f.write_text("- name: a\n  schedule: '60 * * * *'\n  prompt: x\n")
    results = diagnose(f)
    c001_errors = [i for i in results[0].issues if i.check_id == "C001" and i.severity == Severity.ERROR]
    assert len(c001_errors) >= 1


def test_diagnose_circular_dep(tmp_path: Path):
    f = tmp_path / "circ.yaml"
    f.write_text(textwrap.dedent("""\
        - name: a
          schedule: '0 * * * *'
          prompt: x
          context_from: [b]
        - name: b
          schedule: '0 * * * *'
          prompt: x
          context_from: [a]
    """))
    results = diagnose(f)
    cycle_errors = [i for i in results[0].issues if i.check_id == "D001" and "ircular" in i.message]
    assert len(cycle_errors) >= 1


def test_diagnose_broken_ref(tmp_path: Path):
    f = tmp_path / "broken.yaml"
    f.write_text("- name: a\n  schedule: '0 * * * *'\n  prompt: x\n  context_from: [nonexistent]\n")
    results = diagnose(f)
    broken = [i for i in results[0].issues if i.check_id == "D001" and "nonexistent" in i.message]
    assert len(broken) >= 1


def test_diagnose_yaml_syntax_error(tmp_path: Path):
    f = tmp_path / "bad.yaml"
    f.write_text("- name: a\n\t  schedule: bad\n")  # tab indent invalid
    results = diagnose(f)
    y001_errors = [i for i in results[0].issues if i.check_id == "Y001" and i.severity == Severity.ERROR]
    assert len(y001_errors) >= 1


def test_diagnose_unreadable_file(tmp_path: Path):
    f = tmp_path / "nonexistent.yaml"
    results = diagnose(f)
    # Y001 should flag the unreadable file
    y001 = [i for i in results[0].issues if i.check_id == "Y001"]
    assert len(y001) >= 1


# --- Directory recursion ---

def test_diagnose_directory_recursive(tmp_path: Path):
    d = tmp_path / "jobs"
    d.mkdir()
    (d / "a.yaml").write_text("- name: a\n  schedule: '0 * * * *'\n  prompt: x\n")
    (d / "b.yaml").write_text("- name: b\n  schedule: '60 * * * *'\n  prompt: x\n")
    results = diagnose(d)
    files = [r.file for r in results]
    assert any(str(d / "a.yaml") in f for f in files)
    assert any(str(d / "b.yaml") in f for f in files)
    # b.yaml should have a C001 error
    b_result = next(r for r in results if str(d / "b.yaml") in r.file)
    assert any(i.check_id == "C001" and i.severity == Severity.ERROR for i in b_result.issues)


def test_diagnose_directory_skips_non_yaml(tmp_path: Path):
    d = tmp_path / "jobs"
    d.mkdir()
    (d / "ok.yaml").write_text("- name: a\n  schedule: '0 * * * *'\n  prompt: x\n")
    (d / "readme.txt").write_text("not a yaml file")
    (d / "data.json").write_text("{}")
    results = diagnose(d)
    # Only ok.yaml should be processed
    assert len(results) == 1
    assert "ok.yaml" in results[0].file


def test_diagnose_directory_skips_hidden_dirs(tmp_path: Path):
    d = tmp_path / "jobs"
    d.mkdir()
    (d / "ok.yaml").write_text("- name: a\n  schedule: '0 * * * *'\n  prompt: x\n")
    (d / ".git").mkdir()
    (d / ".git" / "config.yaml").write_text("- name: x\n  schedule: '60 * * * *'\n  prompt: x\n")
    results = diagnose(d)
    # .git/config.yaml should NOT be in results
    files = " ".join(r.file for r in results)
    assert ".git" not in files


# --- Checks filter ---

def test_diagnose_checks_filter_only_runs_specified(tmp_path: Path):
    f = tmp_path / "x.yaml"
    f.write_text("- name: a\n  schedule: '60 * * * *'\n  prompt: x\n")
    c001 = next(c for c in default_checks() if c.check_id == "C001")
    results = diagnose(f, checks=[c001])
    # All issues should be from C001
    assert all(i.check_id == "C001" for i in results[0].issues)


def test_default_checks_has_8():
    """5 v0.1.0 checks (Y001/C001/C002/D001/S001) + 3 v0.2.0 (T001/P001/M001)."""
    assert len(default_checks()) == 8


def test_default_checks_returns_fresh_list():
    """Mutating the returned list must not affect subsequent calls."""
    a = default_checks()
    a.clear()
    b = default_checks()
    assert len(b) == 8
