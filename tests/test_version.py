"""Version consistency + v1.0.0 contract guards.

These tests protect the v1.0.0 release from accidental drift between
pyproject.toml, the module __version__ attribute, and the CLI --version flag.
"""
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import cron_doctor


REPO = Path(__file__).resolve().parent.parent


def test_pyproject_version_matches_module_version():
    pyproject = tomllib.loads((REPO / "pyproject.toml").read_text())
    assert pyproject["project"]["version"] == cron_doctor.__version__


def test_module_version_is_semver():
    assert re.fullmatch(r"\d+\.\d+\.\d+", cron_doctor.__version__)


def test_module_version_is_v1():
    """v1.0.0 contract: version must start with '1.'."""
    assert cron_doctor.__version__.startswith("1."), (
        f"Expected v1.x version, got {cron_doctor.__version__!r}"
    )


def test_version_flag_includes_python_version():
    """v1.0.0 contract: --version output must include the Python version."""
    result = subprocess.run(
        [sys.executable, "-m", "cron_doctor", "--version"],
        capture_output=True, text=True, timeout=5,
        cwd=str(REPO),
    )
    assert result.returncode == 0
    out = (result.stdout + result.stderr).lower()
    assert "python" in out, f"--version output missing 'python': {result.stdout}{result.stderr}"
    assert cron_doctor.__version__ in out
