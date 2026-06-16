"""Domain types for cron-doctor.

This module is the single point of truth for shared data structures and is the
ONLY module that both `core.py` and `checks/` import directly. This breaks
circular import cycles (see CONTRIBUTING.md).
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import List, Optional, Protocol, runtime_checkable


class Severity(str, enum.Enum):
    """Issue severity. Str-Enum so it serializes naturally to JSON."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class Diagnosis:
    """A single diagnostic finding produced by a check.

    Attributes:
        check_id: Stable check identifier, e.g. "Y001", "C001".
        severity: One of Severity.INFO / WARNING / ERROR.
        message: Short human-readable description of the issue.
        suggestion: Optional fix-it suggestion.
        file: Optional file path the issue refers to.
        line: Optional 1-based line number.
    """

    check_id: str
    severity: Severity
    message: str
    suggestion: Optional[str] = None
    file: Optional[str] = None
    line: Optional[int] = None


@dataclass
class CheckResult:
    """Aggregated result of running all checks on a single file.

    Attributes:
        file: Path of the file that was checked.
        jobs: List of job dicts that were checked.
        issues: List of Diagnosis produced by all checks.
    """

    file: str
    jobs: list
    issues: list = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(d.severity == Severity.ERROR for d in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(d.severity == Severity.WARNING for d in self.issues)


@dataclass(frozen=True)
class FixProposal:
    """A single proposed text fix for a Diagnosis.

    Produced by a check's `propose_fix(diagnosis, original_line)` method and
    later applied (after user confirmation) by the fixer in Wave 2.

    Attributes:
        file: Path of the file to modify.
        line: 1-based line number the fix targets.
        check_id: The check that produced the original Diagnosis (e.g. "T001").
        description: Short human-readable description of the fix.
        original: The exact original line text (including indentation).
        replacement: The exact replacement line text (including indentation).
    """

    file: str
    line: int
    check_id: str
    description: str
    original: str
    replacement: str


@runtime_checkable
class BaseCheck(Protocol):
    """Protocol every check must satisfy.

    Concrete checks provide a class attribute `check_id` (e.g. "Y001") and
    `name` (e.g. "YAML syntax"), and implement `run(job, context)`.
    """

    check_id: str
    name: str

    def run(self, job: dict, context: dict) -> List[Diagnosis]:
        """Run this check on one job. Return a list of Diagnosis (possibly empty)."""
        ...
