"""cron-doctor: cron.yaml 검증 CLI.

Zero-deps-ish Python CLI that diagnoses cron.yaml files for syntax, semantics,
dependencies, and schema. PyYAML is the only runtime dependency (used to get
line/column info for actionable YAML error messages).

Public API (v0.3.0):
    from cron_doctor import diagnose, fix, watch, WatchEvent
    from cron_doctor.models import Diagnosis, CheckResult, FixProposal, Severity
    from cron_doctor.예외 import CronDoctorError, ParseError, ...
"""
from __future__ import annotations

__version__ = "0.3.0"

from cron_doctor.exceptions import (
    CronDoctorError,
    InvalidCronExpression,
    ParseError,
    SchemaViolation,
    UnreadableFileError,
)
from cron_doctor.models import CheckResult, Diagnosis, FixProposal, Severity

# Re-exported for convenience
__all__ = [
    "__version__",
    "diagnose",
    "fix",
    "watch",
    "WatchEvent",
    "Diagnosis",
    "CheckResult",
    "FixProposal",
    "Severity",
    "CronDoctorError",
    "InvalidCronExpression",
    "ParseError",
    "UnreadableFileError",
    "SchemaViolation",
]


# Lazy import for `diagnose`, `fix`, and `watch` to avoid loading core.py at import time
# (helps with `cron-doctor --version` startup time)
def __getattr__(name):
    if name == "diagnose":
        from cron_doctor.core import diagnose
        return diagnose
    if name == "fix":
        from cron_doctor.core import fix
        return fix
    if name == "watch":
        from cron_doctor.core import watch
        return watch
    if name == "WatchEvent":
        from cron_doctor.core import WatchEvent
        return WatchEvent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
