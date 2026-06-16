# Changelog

All notable changes to `cron-doctor` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
