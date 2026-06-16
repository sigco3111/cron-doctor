"""cron-doctor: cron.yaml 검증 CLI.

Zero-deps-ish Python CLI that diagnoses cron.yaml files for syntax, semantics,
dependencies, and schema. PyYAML is the only runtime dependency (used to get
line/column info for actionable YAML error messages).

Public API (v0.1.0):
    from cron_doctor import diagnose
    from cron_doctor.models import Diagnosis, CheckResult, Severity
"""
from __future__ import annotations

__version__ = "0.1.0"

from cron_doctor.exceptions import (
    CronDoctorError,
    InvalidCronExpression,
    ParseError,
    SchemaViolation,
    UnreadableFileError,
)
from cron_doctor.models import CheckResult, Diagnosis, Severity

# Re-exported for convenience
__all__ = [
    "__version__",
    "diagnose",
    "Diagnosis",
    "CheckResult",
    "Severity",
    "CronDoctorError",
    "InvalidCronExpression",
    "ParseError",
    "UnreadableFileError",
    "SchemaViolation",
]


# Lazy import for `diagnose` to avoid loading core.py at import time
# (helps with `cron-doctor --version` startup time)
def __getattr__(name):
    if name == "diagnose":
        from cron_doctor.core import diagnose
        return diagnose
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
