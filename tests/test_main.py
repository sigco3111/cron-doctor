"""v1.0.0 __main__.py direct invocation tests.

Verifies that `python -m cron_doctor` works as a drop-in for the `cron-doctor`
console script. This guards against drift between pyproject.toml's [project.scripts]
entry point and the __main__ module.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent


def _run_cli(*args, timeout=15):
    return subprocess.run(
        [sys.executable, "-m", "cron_doctor", *args],
        capture_output=True, text=True, timeout=timeout,
        cwd=str(REPO),
    )


def test_main_module_runs_with_no_args():
    """`python -m cron_doctor` (no args) should print help and exit non-zero (2)."""
    result = _run_cli()
    assert result.returncode == 2, (
        f"Expected exit code 2 (argparse error), got {result.returncode}.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    # argparse prints usage to stderr
    assert "usage" in result.stderr.lower() or "usage" in result.stdout.lower()


def test_main_module_help():
    result = _run_cli("--help")
    assert result.returncode == 0
    out = result.stdout.lower()
    assert "usage" in out
    assert "check" in out
    assert "fix" in out
    assert "watch" in out
    assert "list-checks" in out


def test_main_module_version():
    result = _run_cli("--version")
    assert result.returncode == 0
    out = (result.stdout + result.stderr).strip()
    # argparse's default --version prints "cron-doctor X.Y.Z"
    import cron_doctor
    assert cron_doctor.__version__ in out


def test_main_module_list_checks():
    result = _run_cli("list-checks")
    assert result.returncode == 0
    # C001 should appear in the list of check IDs
    assert "C001" in result.stdout


def test_main_module_check_subcommand_help():
    result = _run_cli("check", "--help")
    assert result.returncode == 0
    out = result.stdout.lower()
    assert "--format" in out
    assert "--min-severity" in out


def test_main_module_runs_check_on_valid_file(tmp_path):
    p = tmp_path / "good.yaml"
    p.write_text("jobs:\n  - name: ok\n    schedule: '0 * * * *'\n    command: echo hi\n")
    result = _run_cli("check", str(p), "--format", "text")
    assert result.returncode == 0, (
        f"check failed unexpectedly.\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_main_module_exit_code_on_issues(tmp_path):
    p = tmp_path / "bad.yaml"
    # Malformed cron expression → should produce a finding
    p.write_text("jobs:\n  - name: bad\n    schedule: 'not-a-cron'\n    command: echo hi\n")
    result = _run_cli("check", str(p), "--format", "text")
    # Issues found → exit 1
    assert result.returncode == 1, (
        f"Expected exit 1 for issues, got {result.returncode}.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
