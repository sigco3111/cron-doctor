"""v1.0.0 __main__.py direct import test.

Covers the 4 previously-untested statements in __main__.py (import sys, import
main, __name__ == "__main__" guard, sys.exit(main())).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent


def test_main_module_imports_without_error():
    """__main__.py must be importable without side effects (other than
    importing cli). Verify by running it with no args — it should print
    help and exit 2 (argparse default for missing subcommand).
    """
    result = subprocess.run(
        [sys.executable, "-m", "cron_doctor"],
        capture_output=True, text=True, timeout=10,
        cwd=str(REPO),
    )
    # No subcommand → argparse exits 2
    assert result.returncode == 2


def test_main_module_exits_with_provided_code():
    """__main__.py must call sys.exit(main()) — the exit code from main()
    must propagate to the process exit code.
    """
    result = subprocess.run(
        [sys.executable, "-m", "cron_doctor", "list-checks"],
        capture_output=True, text=True, timeout=10,
        cwd=str(REPO),
    )
    assert result.returncode == 0
    assert "C001" in result.stdout


def test_main_module_runs_check_subcommand():
    """__main__.py must delegate to main() for the check subcommand."""
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("jobs:\n  - name: ok\n    schedule: '0 * * * *'\n    command: echo hi\n")
        f.flush()
        result = subprocess.run(
            [sys.executable, "-m", "cron_doctor", "check", f.name],
            capture_output=True, text=True, timeout=10,
            cwd=str(REPO),
        )
    assert result.returncode == 0
