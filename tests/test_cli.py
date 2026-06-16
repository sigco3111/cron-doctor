"""Tests for cron_doctor.cli — uses subprocess to test the actual CLI."""
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest


REPO = Path("/Users/hjshin/Desktop/project/work/ai-driven-dev/cron-doctor")


def run_cli(*args, cwd=None):
    """Run `python -m cron_doctor <args>` and return the completed process."""
    return subprocess.run(
        [sys.executable, "-m", "cron_doctor", *args],
        capture_output=True,
        text=True,
        cwd=cwd or str(REPO),
    )


# --- Version ---

def test_version_flag():
    r = run_cli("--version")
    assert r.returncode == 0
    assert "0.1.0" in r.stdout


# --- list-checks ---

def test_list_checks_lists_all_5():
    r = run_cli("list-checks")
    assert r.returncode == 0
    for cid in ("Y001", "C001", "C002", "D001", "S001"):
        assert cid in r.stdout, f"missing {cid} in {r.stdout!r}"


# --- check subcommand: valid file ---

def test_check_valid_file_exit_0(tmp_path: Path):
    f = tmp_path / "ok.yaml"
    f.write_text("- name: a\n  schedule: '0 * * * *'\n  prompt: x\n")
    r = run_cli("check", str(f))
    assert r.returncode == 0, f"stdout={r.stdout!r} stderr={r.stderr!r}"
    assert "no issues" in r.stdout.lower() or "0 issues" in r.stdout.lower()


# --- check subcommand: invalid file ---

def test_check_invalid_cron_exit_1(tmp_path: Path):
    f = tmp_path / "bad.yaml"
    f.write_text("- name: a\n  schedule: '60 * * * *'\n  prompt: x\n")
    r = run_cli("check", str(f))
    assert r.returncode == 1, f"expected 1, got {r.returncode}; stderr={r.stderr!r}"
    assert "C001" in r.stdout


def test_check_broken_ref_exit_1(tmp_path: Path):
    f = tmp_path / "broken.yaml"
    f.write_text(textwrap.dedent("""\
        - name: a
          schedule: '0 * * * *'
          prompt: x
          context_from: [nonexistent]
    """))
    r = run_cli("check", str(f))
    assert r.returncode == 1
    assert "D001" in r.stdout
    assert "nonexistent" in r.stdout


# --- User errors ---

def test_check_nonexistent_file_exit_2(tmp_path: Path):
    f = tmp_path / "nonexistent.yaml"
    r = run_cli("check", str(f))
    assert r.returncode == 2, f"expected 2, got {r.returncode}"
    assert "not found" in r.stderr.lower() or "no such" in r.stderr.lower()


def test_check_unknown_check_id_exit_2(tmp_path: Path):
    f = tmp_path / "ok.yaml"
    f.write_text("- name: a\n  schedule: '0 * * * *'\n  prompt: x\n")
    r = run_cli("check", str(f), "--checks", "Z999")
    assert r.returncode == 2
    assert "Z999" in r.stderr


# --- Format: json ---

def test_format_json_valid(tmp_path: Path):
    f = tmp_path / "bad.yaml"
    f.write_text("- name: a\n  schedule: '60 * * * *'\n  prompt: x\n")
    r = run_cli("check", str(f), "--format", "json")
    assert r.returncode == 1
    data = json.loads(r.stdout)
    assert "files" in data
    assert "summary" in data
    assert data["summary"]["errors"] >= 1


def test_format_json_no_issues(tmp_path: Path):
    f = tmp_path / "ok.yaml"
    f.write_text("- name: a\n  schedule: '0 * * * *'\n  prompt: x\n")
    r = run_cli("check", str(f), "--format", "json")
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["summary"]["errors"] == 0
    assert data["summary"]["warnings"] == 0


# --- Format: github ---

def test_format_github_starts_with_colon_colon(tmp_path: Path):
    f = tmp_path / "bad.yaml"
    f.write_text("- name: a\n  schedule: '60 * * * *'\n  prompt: x\n")
    r = run_cli("check", str(f), "--format", "github")
    assert "::error" in r.stdout


def test_format_github_warning_for_semantic(tmp_path: Path):
    f = tmp_path / "warn.yaml"
    f.write_text("- name: a\n  schedule: '* * * * *'\n  prompt: x\n")
    r = run_cli("check", str(f), "--format", "github")
    assert "::warning" in r.stdout


# --- --min-severity filter ---

def test_min_severity_error_filters_warnings(tmp_path: Path):
    f = tmp_path / "warn.yaml"
    f.write_text("- name: a\n  schedule: '* * * * *'\n  prompt: x\n")
    # Default fail-on is error, so C002 WARNING → exit 0
    r = run_cli("check", str(f))
    assert r.returncode == 0


def test_fail_on_warning_treats_warning_as_error(tmp_path: Path):
    f = tmp_path / "warn.yaml"
    f.write_text("- name: a\n  schedule: '* * * * *'\n  prompt: x\n")
    r = run_cli("check", str(f), "--fail-on", "warning")
    assert r.returncode == 1


def test_min_severity_warning_filters_info(tmp_path: Path):
    f = tmp_path / "info.yaml"
    f.write_text("- name: a\n  schedule: '0 0 29 2 *'\n  prompt: x\n")
    r = run_cli("check", str(f), "--min-severity", "warning", "--format", "json")
    assert r.returncode == 0  # no warnings/errors, just INFO
    data = json.loads(r.stdout)
    # C002 INFO on Feb 29 should be filtered out
    assert data["summary"]["info"] == 0


# --- --checks filter ---

def test_checks_filter_only_runs_specified(tmp_path: Path):
    f = tmp_path / "x.yaml"
    f.write_text("- name: a\n  schedule: '60 * * * *'\n  prompt: x\n")
    r = run_cli("check", str(f), "--checks", "C001", "--format", "json")
    assert r.returncode == 1
    data = json.loads(r.stdout)
    for f_data in data["files"]:
        for issue in f_data["issues"]:
            assert issue["check_id"] == "C001"


# --- Directory recursion ---

def test_check_directory_recurses(tmp_path: Path):
    d = tmp_path / "jobs"
    d.mkdir()
    (d / "a.yaml").write_text("- name: a\n  schedule: '0 * * * *'\n  prompt: x\n")
    (d / "b.yaml").write_text("- name: b\n  schedule: '60 * * * *'\n  prompt: x\n")
    r = run_cli("check", str(d))
    assert r.returncode == 1
    assert "b.yaml" in r.stdout


# --- No subcommand ---

def test_no_subcommand_shows_help():
    r = run_cli()
    assert r.returncode == 2
    assert "usage" in r.stdout.lower() or "usage" in r.stderr.lower()
