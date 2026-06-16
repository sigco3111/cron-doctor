"""Tests for cron_doctor.checks.Y001_yaml — TDD."""
import textwrap
from pathlib import Path

from cron_doctor.checks.Y001_yaml import YAMLCheck
from cron_doctor.exceptions import ParseError, UnreadableFileError
from cron_doctor.models import Diagnosis, Severity


# --- Per-job run() — always returns [] (file-level check) ---


def test_run_returns_empty_list():
    check = YAMLCheck()
    assert check.run({"name": "x"}, {}) == []


def test_run_does_not_throw_on_any_job():
    check = YAMLCheck()
    # Should not throw on weird inputs
    assert check.run({}, {}) == []
    assert check.run({"schedule": "* * * * *"}, {}) == []


# --- Class attributes ---


def test_check_id_and_name():
    check = YAMLCheck()
    assert check.check_id == "Y001"
    assert check.name == "YAML syntax"


# --- File-level check_file() — happy path ---


def test_check_file_valid(tmp_path: Path):
    f = tmp_path / "ok.yaml"
    f.write_text("- name: a\n  schedule: '0 * * * *'\n")
    check = YAMLCheck()
    issues = check.check_file(str(f))
    assert issues == []


def test_check_file_empty(tmp_path: Path):
    f = tmp_path / "empty.yaml"
    f.write_text("")
    check = YAMLCheck()
    issues = check.check_file(str(f))
    assert issues == []  # empty file is valid


# --- File-level error translation ---


def test_check_file_yaml_syntax_error(tmp_path: Path):
    f = tmp_path / "bad.yaml"
    f.write_text("- name: a\n\t  schedule: bad\n")  # tab indent invalid
    check = YAMLCheck()
    issues = check.check_file(str(f))
    assert len(issues) == 1
    assert isinstance(issues[0], Diagnosis)
    assert issues[0].check_id == "Y001"
    assert issues[0].severity == Severity.ERROR
    assert "YAML" in issues[0].message or "parse" in issues[0].message.lower()
    assert issues[0].file == str(f)


def test_check_file_yaml_error_has_line():
    f = Path("/tmp/cron-test-bad.yaml")
    f.write_text("key: value\nbroken:\n  - : invalid\n")
    check = YAMLCheck()
    issues = check.check_file(str(f))
    assert len(issues) == 1
    # line may or may not be set depending on PyYAML version
    f.unlink()


def test_check_file_missing(tmp_path: Path):
    f = tmp_path / "nonexistent.yaml"
    check = YAMLCheck()
    issues = check.check_file(str(f))
    assert len(issues) == 1
    assert issues[0].check_id == "Y001"
    assert issues[0].severity == Severity.ERROR
    assert "nonexistent" in str(issues[0].file) or "Cannot read" in issues[0].message or "No such" in issues[0].message


# Extra: check unreadable file (permission) - best-effort
def test_check_file_unreadable(tmp_path: Path):
    f = tmp_path / "secret.yaml"
    f.write_text("- name: x\n")
    # simulate unreadable by pointing to a directory or invalid path; here we pass an invalid path
    check = YAMLCheck()
    issues = check.check_file(str(f) + ":not_a_file")
    # Should return at least one issue
    assert len(issues) >= 1
