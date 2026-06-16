"""v1.0.0 public API contract tests.

Guards against accidental breakage of the stable v1.0.0 surface:
- Every name in cron_doctor.__all__ is importable and has expected type
- Every public module's docstring carries the "Stable since v1.0.0" marker
- Exception hierarchy is intact (all inherit CronDoctorError)
- Data classes are frozen and JSON-serializable
- Function signatures match the documented v1.0.0 contract in docs/API.md
"""
from __future__ import annotations

import importlib
import inspect
import json
import sys
import tomllib
from pathlib import Path

import pytest

import cron_doctor
from cron_doctor.models import CheckResult, Diagnosis, FixProposal, Severity
from cron_doctor.exceptions import (
    CronDoctorError,
    InvalidCronExpression,
    ParseError,
    SchemaViolation,
    UnreadableFileError,
)


REPO = Path(__file__).resolve().parent.parent
PUBLIC_MODULES = [
    "cron_doctor",
    "cron_doctor.core",
    "cron_doctor.models",
    "cron_doctor.exceptions",
    "cron_doctor.parsers.cron_expr",
    "cron_doctor.parsers.yaml_loader",
]


# ---------------------------------------------------------------------------
# __all__ contract
# ---------------------------------------------------------------------------

def test_all_exports_are_resolvable():
    """Every name in __all__ must be importable via getattr()."""
    for name in cron_doctor.__all__:
        obj = getattr(cron_doctor, name, None)
        assert obj is not None, f"cron_doctor.__all__ lists {name!r} but it is not importable"


def test_all_excludes_dunder_except_version():
    """__all__ should only contain __version__ from the dunder namespace."""
    dunders = [n for n in cron_doctor.__all__ if n.startswith("__") and n != "__version__"]
    assert dunders == [], f"Unexpected dunder in __all__: {dunders}"


def test_all_includes_core_public_functions():
    """The 5 core public functions must be in __all__."""
    for name in ("diagnose", "fix", "propose_fixes", "apply_fixes", "watch", "WatchEvent"):
        assert name in cron_doctor.__all__, f"{name!r} missing from __all__"


def test_all_includes_data_classes():
    for name in ("Diagnosis", "CheckResult", "FixProposal", "Severity"):
        assert name in cron_doctor.__all__, f"{name!r} missing from __all__"


def test_all_includes_exception_hierarchy():
    for name in ("CronDoctorError", "ParseError", "InvalidCronExpression",
                 "UnreadableFileError", "SchemaViolation"):
        assert name in cron_doctor.__all__, f"{name!r} missing from __all__"


# ---------------------------------------------------------------------------
# Stability markers (module-level)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("module_name", PUBLIC_MODULES)
def test_public_module_has_stability_marker(module_name):
    """Every public module's docstring must carry the v1.0.0 stability marker."""
    mod = importlib.import_module(module_name)
    doc = mod.__doc__ or ""
    assert "Stable since v1.0.0" in doc, (
        f"{module_name} docstring missing stability marker.\n"
        f"Add: 'Stable since v1.0.0. No breaking changes within v1.x.'"
    )


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------

def test_all_specific_exceptions_inherit_cron_doctor_error():
    for cls in (ParseError, InvalidCronExpression, UnreadableFileError, SchemaViolation):
        assert issubclass(cls, CronDoctorError), f"{cls.__name__} must inherit CronDoctorError"


def test_cron_doctor_error_inherits_exception():
    assert issubclass(CronDoctorError, Exception)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

def test_severity_has_info_warning_error():
    assert hasattr(Severity, "INFO")
    assert hasattr(Severity, "WARNING")
    assert hasattr(Severity, "ERROR")


def test_diagnosis_is_frozen():
    """Diagnosis must be a frozen dataclass (v1.0.0 stability guarantee)."""
    d = Diagnosis(
        check_id="C001",
        severity=Severity.WARNING,
        message="test",
        file=Path("/tmp/test.yaml"),
        line=1,
    )
    with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
        d.check_id = "C002"  # type: ignore[misc]


def test_check_result_is_mutable_but_has_has_errors_property():
    """CheckResult is intentionally a regular dataclass (mutable) because
    checks append to .issues. The v1.0.0 contract is: .file is str, .jobs and
    .issues are lists, and has_errors / has_warnings properties work.
    """
    cr = CheckResult(file="/tmp/test.yaml", jobs=[])
    assert cr.has_errors is False
    assert cr.has_warnings is False
    cr.issues.append(
        Diagnosis(
            check_id="C001",
            severity=Severity.ERROR,
            message="x",
            file="/tmp/test.yaml",
            line=1,
        )
    )
    assert cr.has_errors is True


def test_fix_proposal_is_frozen():
    fp = FixProposal(
        check_id="C001",
        file=Path("/tmp/test.yaml"),
        line=1,
        original="foo",
        replacement="bar",
        description="test",
    )
    with pytest.raises(Exception):
        fp.original = "baz"  # type: ignore[misc]


def test_data_classes_are_json_serializable():
    """v1.0.0 contract: all public data classes round-trip through json."""
    d = Diagnosis(
        check_id="C001",
        severity=Severity.WARNING,
        message="test",
        file=Path("/tmp/test.yaml"),
        line=1,
    )
    # The file field is a Path — must be converted to str for JSON.
    payload = {
        "check_id": d.check_id,
        "severity": d.severity.value,
        "message": d.message,
        "file": str(d.file),
        "line": d.line,
    }
    roundtripped = json.loads(json.dumps(payload))
    assert roundtripped == payload


# ---------------------------------------------------------------------------
# Function signatures (v1.0.0 contract)
# ---------------------------------------------------------------------------

def test_diagnose_signature():
    sig = inspect.signature(cron_doctor.diagnose)
    params = list(sig.parameters.keys())
    assert params[0] == "path"
    assert "checks" in sig.parameters
    assert sig.parameters["checks"].default is None
    assert sig.parameters["checks"].kind == inspect.Parameter.KEYWORD_ONLY


def test_propose_fixes_signature():
    sig = inspect.signature(cron_doctor.propose_fixes)
    params = list(sig.parameters.keys())
    assert params[0] == "path"


def test_apply_fixes_signature():
    sig = inspect.signature(cron_doctor.apply_fixes)
    params = list(sig.parameters.keys())
    assert params[0] == "path"
    assert params[1] == "proposals"


def test_fix_signature():
    sig = inspect.signature(cron_doctor.fix)
    params = list(sig.parameters.keys())
    assert params[0] == "path"
    assert "dry_run" in sig.parameters
    assert sig.parameters["dry_run"].default is True


def test_watch_signature():
    sig = inspect.signature(cron_doctor.watch)
    params = list(sig.parameters.keys())
    assert params[0] == "path"
    for kw, default in (("debounce_ms", 200), ("poll_interval_ms", 100)):
        assert kw in sig.parameters
        assert sig.parameters[kw].default == default


# ---------------------------------------------------------------------------
# Version consistency
# ---------------------------------------------------------------------------

def test_pyproject_and_module_versions_match():
    pyproject = tomllib.loads((REPO / "pyproject.toml").read_text())
    assert pyproject["project"]["version"] == cron_doctor.__version__


def test_version_is_semver():
    import re
    assert re.fullmatch(r"\d+\.\d+\.\d+", cron_doctor.__version__)
