"""cron-doctor: cron.yaml 검증 CLI.

Zero-deps-ish Python CLI that diagnoses cron.yaml files for syntax, semantics,
dependencies, and schema. PyYAML is the only runtime dependency (used to get
line/column info for actionable YAML error messages).

Public API (v1.0.0):
    from cron_doctor import diagnose, fix, watch, WatchEvent
    from cron_doctor.models import Diagnosis, CheckResult, FixProposal, Severity
    from cron_doctor.exceptions import CronDoctorError, ParseError, ...

Stable since v1.0.0. No breaking changes within v1.x.
"""
from __future__ import annotations

__version__ = "1.0.0"

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
    "propose_fixes",
    "apply_fixes",
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


# Lazy import for `diagnose`, `fix`, `propose_fixes`, `apply_fixes`, `watch`, `WatchEvent`
# to avoid loading core.py at import time (helps with `cron-doctor --version` startup time)
def __getattr__(name):
    if name == "diagnose":
        from cron_doctor.core import diagnose
        return diagnose
    if name == "fix":
        from cron_doctor.core import fix
        return fix
    if name == "propose_fixes":
        from cron_doctor.core import propose_fixes
        return propose_fixes
    if name == "apply_fixes":
        from cron_doctor.core import apply_fixes
        return apply_fixes
    if name == "watch":
        from cron_doctor.core import watch
        return watch
    if name == "WatchEvent":
        from cron_doctor.core import WatchEvent
        return WatchEvent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
