"""Check module registry.

Imports all check classes and exposes:
- ALL_CHECKS: list of all check instances
- default_checks(): returns a fresh list (safe to mutate in tests)
"""

from __future__ import annotations

from cron_doctor.checks.Y001_yaml import YAMLCheck
from cron_doctor.checks.C001_cron_syntax import CronSyntaxCheck
from cron_doctor.checks.C002_cron_semantics import CronSemanticsCheck
from cron_doctor.checks.D001_dependencies import DependenciesCheck
from cron_doctor.checks.S001_schema import SchemaCheck
from cron_doctor.checks.T001_timezone import TimezoneCheck
from cron_doctor.checks.P001_prompt import PromptCheck
from cron_doctor.checks.M001_mcp import MCPCheck


ALL_CHECKS = [
    YAMLCheck(),
    CronSyntaxCheck(),
    CronSemanticsCheck(),
    DependenciesCheck(),
    SchemaCheck(),
    TimezoneCheck(),
    PromptCheck(),
    MCPCheck(),
]


def default_checks() -> list:
    """Return a fresh list of all check instances (safe for tests to mutate)."""
    return list(ALL_CHECKS)
