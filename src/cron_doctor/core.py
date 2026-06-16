"""Core orchestration: file walking, check execution, result aggregation.

Public API:
    diagnose(path) -> list[CheckResult]
        Validate a single YAML file OR recursively validate all *.yaml/*.yml
        files in a directory. Returns a list of CheckResult (one per file).

    propose_fixes(path) -> list[FixProposal]
        Run diagnose() and return concrete edit proposals from any check that
        implements a `propose_fix(diagnosis, original_line)` static method.
        Files are NOT modified.

    apply_fixes(path, proposals) -> int
        Apply the given proposals in-memory and write the file back. Returns
        the number of proposals applied. Caller must explicitly opt-in (e.g.
        `fix --apply`).

    _default_registry() uses a lazy import to break the core <-> checks
    circular dependency (see CONTRIBUTING.md).
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Union

from cron_doctor.models import CheckResult, Diagnosis, FixProposal, Severity


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
    from cron_doctor.parsers.yaml_loader import load_cron_document
    try:
        doc = load_cron_document(path)
    except Exception:  # defensive — Y001 should have caught
        return result

    jobs = doc.get("jobs", [])
    if not jobs:
        return result

    result.jobs = jobs

    # Step 2.5: build toolset registry and check for duplicates
    toolsets_raw = doc.get("toolsets", [])
    toolset_names: set = set()
    if isinstance(toolsets_raw, list):
        for t in toolsets_raw:
            if isinstance(t, dict) and isinstance(t.get("name"), str):
                toolset_names.add(t["name"])

    if isinstance(toolsets_raw, list):
        seen: set = set()
        duplicates: list = []
        for t in toolsets_raw:
            if isinstance(t, dict) and isinstance(t.get("name"), str):
                n = t["name"]
                if n in seen:
                    duplicates.append(n)
                seen.add(n)
        for dup in duplicates:
            result.issues.append(Diagnosis(
                check_id="M001",
                severity=Severity.WARNING,
                message=f"Duplicate toolset name {dup!r} in document root `toolsets:`",
                suggestion="Each toolset must have a unique name",
                file=str(path),
            ))

    document_toolsets = toolset_names if toolset_names else None

    # Step 3: per-job checks
    for job_idx, job in enumerate(jobs):
        ctx = {
            "file": str(path),
            "all_jobs": jobs,
            "job_index": job_idx,
            "document_toolsets": document_toolsets,
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


def propose_fixes(path: Union[str, Path]) -> List[FixProposal]:
    """Propose (but do NOT apply) auto-fixes for the given file or directory.

    Runs `diagnose(path)` first, then for each Diagnosis, dispatches to the
    producing check's `propose_fix(diagnosis, original_line)` static method
    to obtain a concrete FixProposal. Checks that don't implement
    propose_fix (e.g. C001) are silently skipped.

    The returned proposals are NOT applied. Use `apply_fixes(path, proposals)`
    with explicit user opt-in to write changes.
    """
    path = Path(path)

    if path.is_dir():
        results_proposals: List[FixProposal] = []
        for f in sorted(path.rglob("*")):
            if not f.is_file():
                continue
            if f.suffix not in (".yaml", ".yml"):
                continue
            if any(part in _SKIP_DIRS for part in f.parts):
                continue
            results_proposals.extend(_propose_fixes_for_file(f))
        return results_proposals

    return _propose_fixes_for_file(path)


def _propose_fixes_for_file(path: Path) -> List[FixProposal]:
    """For one file, return all auto-fix proposals from checks that support it."""
    try:
        results = diagnose(path)
    except Exception:
        return []
    if not results:
        return []

    result = results[0]
    if not result.issues:
        return []

    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    lines = text.splitlines(keepends=True)

    proposals: List[FixProposal] = []
    for issue in result.issues:
        check = _find_check(issue.check_id)
        if check is None:
            continue
        propose = getattr(check, "propose_fix", None)
        if propose is None:
            continue

        if issue.line is not None and 1 <= issue.line <= len(lines):
            try:
                proposal = propose(issue, lines[issue.line - 1])
            except Exception:
                proposal = None
            if proposal is not None:
                proposals.append(proposal)
            continue

        for idx, line in enumerate(lines, start=1):
            try:
                proposal = propose(issue, line)
            except Exception:
                continue
            if proposal is not None:
                from dataclasses import replace
                proposals.append(replace(proposal, line=idx))
                break

    return proposals


def _find_check(check_id: str):
    """Look up a check instance by its id from the default registry."""
    for c in _default_registry():
        if c.check_id == check_id:
            return c
    return None


def apply_fixes(path: Union[str, Path], proposals: List[FixProposal]) -> int:
    """Apply the given proposals to the file in-place.

    SAFETY: This function writes to disk. Callers MUST obtain explicit user
    opt-in (e.g. via `cron-doctor fix --apply`) before calling this.

    Returns the number of proposals successfully applied.

    Sorting: applied line-by-line in DESCENDING order to avoid index shift
    when multiple proposals target the same file.
    """
    if not proposals:
        return 0

    path = Path(path)
    if not path.is_file():
        return 0

    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return 0
    lines = text.splitlines(keepends=True)

    applied = 0
    sorted_proposals = sorted(proposals, key=lambda p: (p.line, p.check_id), reverse=True)
    for p in sorted_proposals:
        if p.line < 1 or p.line > len(lines):
            continue
        original = lines[p.line - 1]
        # Apply only if the line still matches the expected original (idempotency)
        if p.original and p.original.strip() and original.strip() != p.original.strip():
            continue
        # Preserve trailing newline behavior
        replacement = p.replacement
        if original.endswith("\n") and not replacement.endswith("\n"):
            replacement = replacement + "\n"
        elif not original.endswith("\n") and replacement.endswith("\n"):
            replacement = replacement.rstrip("\n")
        lines[p.line - 1] = replacement
        applied += 1

    if applied == 0:
        return 0

    new_text = "".join(lines)
    try:
        path.write_text(new_text, encoding="utf-8")
    except OSError:
        return 0
    return applied


def fix(path: Union[str, Path], *, dry_run: bool = True) -> dict:
    """High-level Python API: propose (and optionally apply) auto-fixes.

    Args:
        path: file or directory to fix.
        dry_run: if True (default), only propose. If False, apply changes.

    Returns:
        dict with keys:
            - "proposals": list[FixProposal]
            - "applied": int (number applied; 0 in dry-run mode)
            - "would_apply": int (number of proposals that would be applied)

    Safety: defaults to dry_run=True. To write changes, pass dry_run=False.
    """
    proposals = propose_fixes(path)
    if dry_run:
        return {
            "proposals": proposals,
            "applied": 0,
            "would_apply": len(proposals),
        }
    applied = apply_fixes(path, proposals)
    return {
        "proposals": proposals,
        "applied": applied,
        "would_apply": len(proposals),
    }
