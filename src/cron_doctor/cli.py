"""argparse 기반 CLI.

Subcommands:
    cron-doctor check PATH [--format text|json|github] [--min-severity ...]
                          [--fail-on ...] [--checks Y001,C001,...] [--recursive]
                          [-o OUTPUT]
    cron-doctor list-checks

Exit codes:
    0  no issues / clean exit
    1  issues found (severity >= --fail-on threshold)
    2  user error (missing file, bad args)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional, Sequence

from cron_doctor import __version__
from cron_doctor.checks import ALL_CHECKS, default_checks
from cron_doctor.core import diagnose
from cron_doctor.models import CheckResult, Diagnosis, Severity


# --- Severity ordering (for --min-severity / --fail-on filters) ---

_SEVERITY_RANK = {Severity.INFO: 0, Severity.WARNING: 1, Severity.ERROR: 2}


def _severity_at_or_above(sev: Severity, threshold: str) -> bool:
    """Return True if `sev` meets or exceeds the threshold (e.g. 'warning')."""
    threshold_enum = Severity(threshold)
    return _SEVERITY_RANK[sev] >= _SEVERITY_RANK[threshold_enum]


# --- Formatters ---

# ANSI codes (only used when stdout is a TTY)
_ANSI = {
    "reset": "\033[0m",
    "red": "\033[31m",
    "yellow": "\033[33m",
    "cyan": "\033[36m",
    "bold": "\033[1m",
    "dim": "\033[2m",
}

_SEV_COLOR = {
    Severity.ERROR: "red",
    Severity.WARNING: "yellow",
    Severity.INFO: "cyan",
}


def _format_text(results: List[CheckResult], *, use_color: bool, min_severity: str) -> str:
    lines: list[str] = []
    total_err = total_warn = total_info = 0

    for r in results:
        if not r.jobs and not r.issues:
            continue
        lines.append(f"{_c('bold', use_color)}{r.file}{_c('reset', use_color)}")
        if not r.issues:
            lines.append(f"  {_c('green', use_color)}✓{_c('reset', use_color)} no issues")
            continue
        for issue in r.issues:
            if not _severity_at_or_above(issue.severity, min_severity):
                continue
            color = _SEV_COLOR.get(issue.severity, "reset")
            loc = f"line {issue.line}" if issue.line else ""
            lines.append(
                f"  {_c(color, use_color)}{issue.severity.value.upper():>7}{_c('reset', use_color)} "
                f"{_c('bold', use_color)}{issue.check_id}{_c('reset', use_color)}"
                + (f" {_c('dim', use_color)}{loc}{_c('reset', use_color)}" if loc else "")
                + f": {issue.message}"
            )
            if issue.suggestion:
                lines.append(f"    {_c('dim', use_color)}💡 {issue.suggestion}{_c('reset', use_color)}")
            if issue.severity == Severity.ERROR:
                total_err += 1
            elif issue.severity == Severity.WARNING:
                total_warn += 1
            else:
                total_info += 1

    # Summary
    parts = []
    if total_err:
        parts.append(f"{_c('red', use_color)}{total_err} error(s){_c('reset', use_color)}")
    if total_warn:
        parts.append(f"{_c('yellow', use_color)}{total_warn} warning(s){_c('reset', use_color)}")
    if total_info:
        parts.append(f"{_c('cyan', use_color)}{total_info} info{_c('reset', use_color)}")
    summary = ", ".join(parts) if parts else f"{_c('green', use_color)}no issues{_c('reset', use_color)}"
    lines.append("")
    lines.append(f"Summary: {summary} across {len(results)} file(s)")

    return "\n".join(lines)


def _format_json(results: List[CheckResult], *, min_severity: str) -> str:
    out = {
        "version": __version__,
        "files": [],
        "summary": {"errors": 0, "warnings": 0, "info": 0, "files": len(results)},
    }
    for r in results:
        issues_out = []
        for i in r.issues:
            if not _severity_at_or_above(i.severity, min_severity):
                continue
            issues_out.append({
                "check_id": i.check_id,
                "severity": i.severity.value,
                "message": i.message,
                "suggestion": i.suggestion,
                "file": i.file,
                "line": i.line,
            })
            if i.severity == Severity.ERROR:
                out["summary"]["errors"] += 1
            elif i.severity == Severity.WARNING:
                out["summary"]["warnings"] += 1
            else:
                out["summary"]["info"] += 1
        out["files"].append({
            "file": r.file,
            "jobs": len(r.jobs),
            "issues": issues_out,
        })
    return json.dumps(out, indent=2, ensure_ascii=False)


def _format_github(results: List[CheckResult], *, min_severity: str) -> str:
    """GitHub Actions workflow command format.

    ::error file=F,line=L::message%0Asuggestion
    ::warning file=F,line=L::message
    ::notice file=F,line=L::message
    """
    lines: list[str] = []
    sev_to_cmd = {
        Severity.ERROR: "error",
        Severity.WARNING: "warning",
        Severity.INFO: "notice",
    }
    for r in results:
        for i in r.issues:
            if not _severity_at_or_above(i.severity, min_severity):
                continue
            cmd = sev_to_cmd.get(i.severity, "notice")
            file_part = f"file={i.file or r.file}"
            line_part = f",line={i.line}" if i.line else ""
            msg = i.message
            if i.suggestion:
                msg = f"{msg}%0A💡 {i.suggestion}"
            # Replace newlines in the raw message with %0A
            msg_encoded = msg.replace("\n", "%0A")
            lines.append(f"::{cmd} {file_part}{line_part}::{msg_encoded}")
    return "\n".join(lines)


def _c(code: str, use_color: bool) -> str:
    """Return ANSI escape code if use_color else empty string."""
    if not use_color:
        return ""
    return _ANSI.get(code, "")


# --- Subcommand handlers ---

def _run_check(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if not path.exists():
        print(f"cron-doctor: error: path not found: {path}", file=sys.stderr)
        return 2

    # Filter checks if --checks given
    if args.checks:
        wanted = {c.strip() for c in args.checks.split(",") if c.strip()}
        checks = [c for c in default_checks() if c.check_id in wanted]
        unknown = wanted - {c.check_id for c in checks}
        if unknown:
            print(f"cron-doctor: error: unknown check ID(s): {sorted(unknown)}", file=sys.stderr)
            print(f"  available: {sorted(c.check_id for c in ALL_CHECKS)}", file=sys.stderr)
            return 2
    else:
        checks = None  # core will use defaults

    try:
        results = diagnose(path, checks=checks)
    except Exception as e:
        print(f"cron-doctor: internal error: {type(e).__name__}: {e}", file=sys.stderr)
        return 2

    # Apply --min-severity filter when formatting
    fmt = args.format
    if fmt == "text":
        out = _format_text(results, use_color=sys.stdout.isatty(), min_severity=args.min_severity)
    elif fmt == "json":
        out = _format_json(results, min_severity=args.min_severity)
    elif fmt == "github":
        out = _format_github(results, min_severity=args.min_severity)
    else:
        print(f"cron-doctor: error: unknown format: {fmt}", file=sys.stderr)
        return 2

    print(out)

    # Determine exit code from --fail-on
    threshold = args.fail_on
    for r in results:
        for issue in r.issues:
            if _severity_at_or_above(issue.severity, threshold):
                return 1
    return 0


def _run_list_checks(args: argparse.Namespace) -> int:
    print(f"cron-doctor {__version__} — available checks:")
    for c in ALL_CHECKS:
        print(f"  {c.check_id}  {c.name}")
    return 0


# --- Argparse setup ---

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cron-doctor",
        description="Diagnose cron.yaml files — syntax, semantics, dependencies, schema.",
    )
    parser.add_argument("--version", action="version", version=f"cron-doctor {__version__}")

    sub = parser.add_subparsers(dest="command", required=False)

    # check
    p_check = sub.add_parser("check", help="Validate a cron.yaml file or directory")
    p_check.add_argument("path", help="Path to a .yaml file or a directory of .yaml files")
    p_check.add_argument(
        "-r", "--recursive", action="store_true",
        help="(deprecated: directories are always recursed)",
    )
    p_check.add_argument(
        "--format", choices=["text", "json", "github"], default="text",
        help="Output format (default: text)",
    )
    p_check.add_argument(
        "-o", "--output", default=None,
        help="Write output to file (default: stdout)",
    )
    p_check.add_argument(
        "--min-severity", choices=["info", "warning", "error"], default="info",
        help="Minimum severity to show (default: info)",
    )
    p_check.add_argument(
        "--fail-on", choices=["info", "warning", "error"], default="error",
        help="Exit 1 if any issue meets this severity (default: error)",
    )
    p_check.add_argument(
        "--checks", default=None,
        help="Comma-separated list of check IDs to run (e.g. Y001,C001)",
    )

    # list-checks
    sub.add_parser("list-checks", help="List all available checks")

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry point. Returns the process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "check":
        return _run_check(args)
    if args.command == "list-checks":
        return _run_list_checks(args)

    # No subcommand → show help
    parser.print_help()
    return 2
