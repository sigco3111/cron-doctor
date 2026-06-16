# cron-doctor Public API Contract (v1.0.0)

This document defines the **stable public API** of cron-doctor. Anything in
`cron_doctor.__all__` is guaranteed to remain backward-compatible within
the v1.x series. Breaking changes require a major version bump.

## Stability promise

- **v1.0.0 is the first stable release.** All public symbols are frozen.
- **No breaking changes within v1.x.** Deprecations are announced in
  `CHANGELOG.md` and remain functional for at least one minor release.
- **New symbols may be added** in minor releases; they are not breaking.

## Versioning

cron-doctor follows [Semantic Versioning](https://semver.org/).
The canonical version lives in `src/cron_doctor/__init__.py::__version__`.
`pyproject.toml` is kept in lock-step via the `tests/test_version.py` guard.

## Public API

### Core functions

| Name | Signature | Purpose |
|------|-----------|---------|
| `diagnose` | `(path, *, checks=None) → list[CheckResult]` | Validate a file or directory |
| `propose_fixes` | `(path) → list[FixProposal]` | Propose auto-fixes (no side effects) |
| `apply_fixes` | `(path, proposals) → int` | Apply proposals in-place (explicit opt-in) |
| `fix` | `(path, *, dry_run=True) → dict` | High-level fix API |

### Watch functions

| Name | Signature | Purpose |
|------|-----------|---------|
| `watch` | `(path, *, debounce_ms=200, poll_interval_ms=100) → Iterator[WatchEvent]` | Poll for file changes |

### Data classes

| Name | Purpose |
|------|---------|
| `Severity` | `INFO` / `WARNING` / `ERROR` (str-enum, JSON-serializable) |
| `Diagnosis` | Single check finding (frozen dataclass) |
| `CheckResult` | Aggregated result for one file |
| `FixProposal` | Concrete edit proposal (frozen dataclass) |
| `WatchEvent` | Change event yielded by `watch()` |

### Exceptions (all inherit `CronDoctorError`)

| Name | When |
|------|------|
| `CronDoctorError` | Base class; catch this to handle any project error |
| `ParseError` | YAML syntax error (carries file/line/column) |
| `InvalidCronExpression` | Malformed cron string |
| `UnreadableFileError` | File missing / permission denied |
| `SchemaViolation` | YAML document does not match Hermes cron.yaml schema |

## CLI surface (v1.0.0)

```
cron-doctor check PATH [--format text|json|github] [--min-severity ...]
                       [--fail-on ...] [--checks C001,C002] [-o OUTPUT]
cron-doctor list-checks
cron-doctor fix PATH [--dry-run|--apply] [--format text|json]
cron-doctor watch PATH [--debounce 200] [--poll-interval 100]
                       [--format text|json|github] [--checks C001,C002]
cron-doctor --version
```

Exit codes: `0` = clean, `1` = issues found (≥ `--fail-on` threshold), `2` = user error.

## Performance budgets (v1.0.0)

| Operation | Budget (typical CI) | Test gate |
|-----------|---------------------|-----------|
| `python -m cron_doctor --version` startup | < 200 ms (2× spec) | `test_benchmarks.py::test_startup_time_under_budget` |
| `diagnose()` on 10 small YAML files | < 100 ms (2× spec) | `test_benchmarks.py::test_diagnose_10_files_under_budget` |
| `watch()` per-iteration latency | < 2 × `poll_interval_ms` | `test_benchmarks.py::test_watch_latency_under_poll_interval` |

## Deprecation policy

When a public symbol must change incompatibly:

1. Announce in `CHANGELOG.md` under `### Deprecated`.
2. Add a `warnings.warn(DeprecationWarning, stacklevel=2)` at the call site.
3. Keep the old symbol functional for at least one minor release (e.g.,
   v1.0 → v1.1).
4. Remove in the next major release (v2.0).

## Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) for development setup, TDD
workflow, and the process for proposing new public API symbols.
