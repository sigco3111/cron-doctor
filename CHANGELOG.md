# Changelog

All notable changes to `cron-doctor` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-06-16

### Added
- **Watch mode** (`watch` subcommand + `core.watch()`):
  - Polling-based real-time file change detection (stdlib only, no new deps)
  - `core.WatchEvent` frozen dataclass (path, kind, results, timestamp)
  - `core.watch(path, *, debounce_ms=200, poll_interval_ms=100)` generator yielding `WatchEvent` for added/modified/deleted
  - `(mtime_ns, size)` as change signal (cross-platform, works on macOS/Linux/Windows)
  - Debounce coalesces rapid writes (default 200ms window)
  - Skips `_SKIP_DIRS` (`.git`, `__pycache__`, etc.) and hidden directories
  - `os.walk(followlinks=False)` prevents symlink loops
  - `os.walk(onerror=...)` logs permission errors to stderr and continues
- **CLI `watch` subcommand**:
  - `cron-doctor watch PATH [--debounce N] [--poll-interval N] [--format text|json|github] [--checks C001,C002]`
  - Registers SIGTERM handler for graceful shutdown (Ctrl+C / SIGTERM → exit 0)
  - Per-event output with timestamp header
  - `--format json` outputs one JSON object per line
  - `--format github` uses GitHub Actions workflow command syntax
- **Test suite**: 265 tests (247 v0.2.0 + 18 new), 100% passing
- **2 new golden fixtures** in `tests/fixtures/watch-test/` for end-to-end watch testing

### Changed
- Version bumped to 0.3.0 (pyproject.toml, `__init__.py`)
- `test_directory_mode_processes_all_yaml_fixtures` count: 9 → 11 (added watch-test fixtures)
- `test_version_flag` now asserts "0.3.0"

### Notes
- **Polling trade-off**: watch uses polling (default 100ms interval), not inotify/FSEvents. Higher CPU on large trees, but zero new deps. Future v0.4+ may add `watchdog` as optional dep.
- **mtime resolution**: uses `st_mtime_ns` (nanosecond precision on ext4/APFS/NTFS). On FAT32 (2s resolution), use `--debounce 2000` or higher to coalesce.
- **Race condition**: between `os.stat` and `diagnose()`, a write may complete. The emitted event reflects the post-write state, not the triggering mtime. Benign.
- **File in write-progress**: debounce coalesces — events are emitted only after `debounce_ms` of no further change.
- **Windows**: `--format xml` and other invalid formats are rejected by argparse with exit 2.

## [0.2.0] - 2026-06-16

### Added
- **3 new checks** (full implementations):
  - `T001` (TimezoneCheck) — validates IANA timezone strings via `zoneinfo` (stdlib). WARNING for invalid/empty.
  - `P001` (PromptCheck) — detects long prompts (>10000 chars, WARNING) and embedded secrets (sk-/pk-/AKIA/ghp_/Bearer/password=, ERROR) with conservative FP avoidance (CHANGEME, XXX, `<...>`, etc. are skipped).
  - `M001` (MCPCheck) — validates `enabled_toolsets` references against the document-root `toolsets:` registry. ERROR for broken refs, WARNING for duplicate toolset names and missing registry.
- **Auto-fix engine** (`core.propose_fixes` / `core.apply_fixes` / `core.fix`):
  - Per-check `propose_fix(diagnosis, original_line)` static method
  - Line-level text edits (preserves YAML formatting)
  - `apply_fixes` is opt-in (safe by default)
  - C001 is intentionally not auto-fixable (no safe rewrite for invalid cron)
- **`fix` CLI subcommand** with safe `--dry-run` (default) / `--apply` (explicit opt-in):
  - `cron-doctor fix PATH` — show proposals
  - `cron-doctor fix PATH --apply` — write changes
  - `--format text|json` output
- **Public Python API enhancements**:
  - `from cron_doctor import fix, FixProposal`
  - `fix(path, dry_run=True)` returns `{proposals, applied, would_apply}`
- **New YAML format support** (`load_cron_document`):
  - Legacy format: top-level list of jobs
  - v0.2+ format: top-level dict with `toolsets:` and `jobs:` keys
- **4 new golden fixture YAMLs**: `t001_timezone.yaml`, `p001_prompt.yaml`, `m001_mcp.yaml`, `fix-dryrun.yaml`
- **Test suite**: 247 tests (168 v0.1.0 + 79 new), 100% passing

### Changed
- **Default check count: 5 → 8** (added T001, P001, M001)
- **`list-checks` test** updated from "all 5" to "all 8"
- **`default_checks` test** updated from "has 5" to "has 8"

### Notes
- `timezone:` field is now checked — invalid values emit WARNING (not ERROR, since custom TZs may be valid in some contexts).
- `enabled_toolsets:` requires a top-level `toolsets:` registry; using it without one emits WARNING.
- P001 secret detection is intentionally conservative — false positives are worse than false negatives for a linter.
- `fix --apply` writes in-place; back up your YAML before applying.

## [0.1.0] - 2026-06-16

### Added
- Initial project skeleton: README (한/영 병기), CHANGELOG, CONTRIBUTING, LICENSE
- Directory structure for `src/cron_doctor/` (parser, checks, CLI)
- 5 core check module stubs planned: Y001 (YAML), C001 (cron syntax), C002 (cron semantics), D001 (dependencies), S001 (schema)
- Test fixture directory placeholder

### Notes
- **Status: Skeleton only.** Full source code is being developed on a different machine.
- This is a **Phase 0 release** — documentation and repo structure only.
- The repository is public on GitHub at `sigco3111/cron-doctor`.

## [0.1.0] - 2026-06-16 (full release)

### Added
- **5 core checks** (full implementations):
  - `Y001` (YAMLCheck) — file-level YAML syntax validation with line/column reporting
  - `C001` (CronSyntaxCheck) — 5/6-field cron expression validation
  - `C002` (CronSemanticsCheck) — every-minute, leap-day, weekday 0/7 duplication
  - `D001` (DependenciesCheck) — broken refs + DFS cycle detection + depth ≥5 warning
  - `S001` (SchemaCheck) — Hermes cron.yaml schema (required keys, types, unknown-key warning)
- **Zero-deps-ish Python parser** (`parsers/cron_expr.py`) — 5/6-field, `*`/`N`/`N-M`/`*/S`/`N-M/S`/`A,B,C`/JAN-DEC/SUN-SAT, weekday 7→0 normalization
- **PyYAML wrapper** (`parsers/yaml_loader.py`) — translates `YAMLError` to `ParseError` with line/column
- **CLI** (`cli.py`) — `check` + `list-checks` subcommands; `--format text|json|github`; `--min-severity` / `--fail-on`; `--checks` filter; exit codes 0/1/2
- **Public Python API** (`__init__.py`) — `diagnose`, `Diagnosis`, `CheckResult`, `Severity`, exception hierarchy
- **5 golden fixture YAMLs** — valid, invalid-cron, circular-dep, broken-context, semantic-warnings
- **CI workflow** — GitHub Actions matrix (Python 3.9–3.12) with `pytest --cov` + 70% coverage gate
- **Test suite** — 168 tests, 100% passing (~73% coverage, cli/__main__ covered via subprocess)

### Changed
- **PyYAML is now a runtime dependency** (justified by line/column reporting). Earlier "Zero Dependencies" badge replaced with "Minimal: PyYAML only".
- **Directory layout** in README updated to match actual filenames (Y001_yaml.py etc., not the older yaml_check.py).
- **Roadmap** updated: v0.1.0 milestone marked done; "공식 GitHub Action 마켓플레이스 등록" removed from v1.0.0.

### Notes
- v0.1.0 includes the full v0.1.0 milestone (5 checks + CLI + golden tests).
- `action.yml` for GitHub Marketplace is deferred to a later release.
- Coverage is 73% (cli.py and __main__.py are 0% in-process; covered via subprocess tests). CI gate is set to 70% to avoid CI flakes.

[Unreleased]: https://github.com/sigco3111/cron-doctor/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/sigco3111/cron-doctor/releases/tag/v0.1.0
