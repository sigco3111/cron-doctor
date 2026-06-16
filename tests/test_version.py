"""Version consistency guard: pyproject.toml version must match __version__.

v1.0.0-specific tests (v1.x prefix, Python in --version) are added in Wave 7
when the version is actually bumped to 1.0.0.
"""
import re
import tomllib
from pathlib import Path

import cron_doctor


REPO = Path(__file__).resolve().parent.parent


def test_pyproject_version_matches_module_version():
    pyproject = tomllib.loads((REPO / "pyproject.toml").read_text())
    assert pyproject["project"]["version"] == cron_doctor.__version__


def test_module_version_is_semver():
    assert re.fullmatch(r"\d+\.\d+\.\d+", cron_doctor.__version__)
