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

    watch(path, *, checks=None, debounce_ms=200, poll_interval_ms=100) -> Iterator[WatchEvent]
        Poll a file or directory for changes. Yields WatchEvent for each
        added/modified/deleted .yaml/.yml file. Uses (mtime_ns, size)
        as the change signal. Coalesces rapid writes via debounce.

    _default_registry() uses a lazy import to break the core <-> checks
    circular dependency (see CONTRIBUTING.md).
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterator, List, Literal, Optional, Tuple, Union

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


@dataclass(frozen=True)
class WatchEvent:
    """A change event emitted by `watch()`.

    Attributes:
        path: The file that changed.
        kind: "added" (new file), "modified" (mtime or size changed), or "deleted".
        results: Diagnose results for the changed file. Empty list for "deleted".
        timestamp: Unix time (seconds, float) when the change was detected.
    """

    path: Path
    kind: Literal["added", "modified", "deleted"]
    results: List[CheckResult]
    timestamp: float


def watch(
    path: Union[str, Path],
    *,
    checks: Optional[List] = None,
    debounce_ms: int = 200,
    poll_interval_ms: int = 100,
) -> Iterator[WatchEvent]:
    """Watch a file or directory for changes. Yields WatchEvent for each change.

    Polling implementation: tracks (mtime_ns, size) of all .yaml/.yml files
    in the tree. Detects added/modified/deleted by diffing successive scans.
    Coalesces rapid bursts of writes via debounce.

    Args:
        path: File or directory to watch.
        checks: Optional list of check instances. If None, uses default registry.
        debounce_ms: After detecting a change, wait this long before emitting
                     (to coalesce rapid writes).
        poll_interval_ms: How often to check mtimes.

    Yields:
        WatchEvent for each change. The generator runs indefinitely; close
        it with `gen.close()` or send KeyboardInterrupt (Ctrl+C) to stop.

    Raises:
        FileNotFoundError: if path does not exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"cron-doctor watch: path not found: {path}")

    if checks is None:
        checks = _default_registry()

    def _on_walk_error(err: OSError) -> None:
        import sys as _sys
        print(f"cron-doctor watch: {err}", file=_sys.stderr)

    def _scan() -> Dict[Path, Tuple[int, int]]:
        result: Dict[Path, Tuple[int, int]] = {}
        if path.is_file():
            if path.suffix in (".yaml", ".yml"):
                try:
                    st = path.stat()
                    result[path] = (st.st_mtime_ns, st.st_size)
                except OSError:
                    pass
            return result
        for root, dirs, files in os.walk(path, followlinks=False, onerror=_on_walk_error):
            dirs[:] = [d for d in dirs if d not in _SKIP_DIRS and not d.startswith(".")]
            for fname in files:
                if not (fname.endswith(".yaml") or fname.endswith(".yml")):
                    continue
                fp = Path(root) / fname
                try:
                    st = fp.stat()
                    result[fp] = (st.st_mtime_ns, st.st_size)
                except OSError:
                    pass
        return result

    def _diagnose_one(p: Path) -> CheckResult:
        return _diagnose_file(p, checks=checks)

    snapshot = _scan()
    for p in sorted(snapshot.keys()):
        yield WatchEvent(
            path=p,
            kind="added",
            results=[_diagnose_one(p)],
            timestamp=time.time(),
        )

    while True:
        time.sleep(poll_interval_ms / 1000.0)
        current = _scan()

        new_paths = sorted(set(current.keys()) - set(snapshot.keys()))
        missing_paths = sorted(set(snapshot.keys()) - set(current.keys()))
        changed_paths = sorted(
            p for p in current if p in snapshot and current[p] != snapshot[p]
        )

        if not (new_paths or missing_paths or changed_paths):
            snapshot = current
            continue

        time.sleep(debounce_ms / 1000.0)
        current = _scan()

        new_paths = sorted(set(current.keys()) - set(snapshot.keys()))
        missing_paths = sorted(set(snapshot.keys()) - set(current.keys()))
        changed_paths = sorted(
            p for p in current if p in snapshot and current[p] != snapshot[p]
        )

        ts = time.time()
        for p in new_paths:
            yield WatchEvent(path=p, kind="added", results=[_diagnose_one(p)], timestamp=ts)
        for p in missing_paths:
            yield WatchEvent(path=p, kind="deleted", results=[], timestamp=ts)
        for p in changed_paths:
            yield WatchEvent(path=p, kind="modified", results=[_diagnose_one(p)], timestamp=ts)

        snapshot = current
