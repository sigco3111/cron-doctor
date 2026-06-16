"""Core orchestration: file walking, check execution, result aggregation.

Public API:
    diagnose(path) -> list[CheckResult]
        Validate a single YAML file OR recursively validate all *.yaml/*.yml
        files in a directory. Returns a list of CheckResult (one per file).

    _default_registry() uses a lazy import to break the core <-> checks
    circular dependency (see CONTRIBUTING.md).
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Union

from cron_doctor.models import CheckResult, Diagnosis, Severity


# Directories to skip when walking (e.g. .git, venv)
_SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".tox"}


def diagnose(path: Union[str, Path], *, checks: Optional[list] = None) -> List[CheckResult]:
    """Diagnose a cron.yaml file or a directory of YAML files.

    Args:
        path: A file path (.yaml/.yml) or a directory path.
        checks: Optional list of check instances to run. If None, runs all 5 default checks.

    Returns:
        list[CheckResult]: one CheckResult per file processed. For a single
        file input, the list has length 1.
    """
    path = Path(path)

    if path.is_dir():
        return _diagnose_directory(path, checks=checks)
    return [_diagnose_file(path, checks=checks)]


def _diagnose_directory(path: Path, *, checks: Optional[list] = None) -> List[CheckResult]:
    """Recursively diagnose all *.yaml/*.yml files in a directory."""
    results: List[CheckResult] = []
    for f in sorted(path.rglob("*")):
        if not f.is_file():
            continue
        if f.suffix not in (".yaml", ".yml"):
            continue
        if any(part in _SKIP_DIRS for part in f.parts):
            continue
        results.append(_diagnose_file(f, checks=checks))
    return results


def _diagnose_file(path: Path, *, checks: Optional[list] = None) -> CheckResult:
    """Run all checks on a single file."""
    if checks is None:
        checks = _default_registry()

    result = CheckResult(file=str(path), jobs=[])

    # Step 1: file-level YAML check (Y001)
    yaml_check = next((c for c in checks if c.check_id == "Y001"), None)
    if yaml_check is not None and hasattr(yaml_check, "check_file"):
        yaml_issues = yaml_check.check_file(str(path))
        result.issues.extend(yaml_issues)
        # If YAML failed, don't run per-job checks
        if any(i.severity == Severity.ERROR for i in yaml_issues):
            return result

    # Step 2: load the YAML (shouldn't fail since Y001 passed)
    from cron_doctor.parsers.yaml_loader import load_cron_yaml
    try:
        jobs = load_cron_yaml(path)
    except Exception:  # defensive — Y001 should have caught
        return result

    if not jobs:
        return result

    result.jobs = jobs

    # Step 3: per-job checks
    for job_idx, job in enumerate(jobs):
        ctx = {
            "file": str(path),
            "all_jobs": jobs,
            "job_index": job_idx,
        }
        for check in checks:
            if check.check_id == "Y001":
                continue  # already done
            if not hasattr(check, "run"):
                continue
            try:
                issues = check.run(job, ctx)
                result.issues.extend(issues)
            except Exception as e:  # defensive: one check shouldn't break the run
                result.issues.append(Diagnosis(
                    check_id=check.check_id,
                    severity=Severity.ERROR,
                    message=f"Check {check.check_id} crashed: {type(e).__name__}: {e}",
                    file=str(path),
                ))

    # Step 4: file-level checks (D001 cycle/depth)
    d001 = next((c for c in checks if c.check_id == "D001"), None)
    if d001 is not None and hasattr(d001, "check_file"):
        result.issues.extend(d001.check_file(jobs, str(path)))

    return result


def _default_registry() -> list:
    """Lazy import to avoid circular import between core.py and checks/."""
    from cron_doctor.checks import default_checks
    return default_checks()
