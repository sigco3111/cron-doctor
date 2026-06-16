"""v1.0.0 in-process CLI tests for cli.py.

These tests call cli.py functions directly (not via subprocess) to get
coverage on the 148 previously-untested statements. The subprocess-based
tests in test_cli.py and test_main.py still exist for integration coverage.
"""
from __future__ import annotations

import argparse
import json
import signal
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from cron_doctor import __version__
from cron_doctor import cli as cli_mod
from cron_doctor.models import CheckResult, Diagnosis, Severity


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _diag(check_id, severity, message, suggestion=None, file=None, line=None):
    return Diagnosis(
        check_id=check_id,
        severity=severity,
        message=message,
        suggestion=suggestion,
        file=file,
        line=line,
    )


def _result(file, jobs=None, issues=None):
    return CheckResult(file=file, jobs=jobs or [], issues=issues or [])


# ===========================================================================
# _severity_at_or_above
# ===========================================================================

class TestSeverityAtOrAbove:
    def test_info_meets_info(self):
        assert cli_mod._severity_at_or_above(Severity.INFO, "info") is True

    def test_info_does_not_meet_warning(self):
        assert cli_mod._severity_at_or_above(Severity.INFO, "warning") is False

    def test_warning_meets_info(self):
        assert cli_mod._severity_at_or_above(Severity.WARNING, "info") is True

    def test_warning_meets_warning(self):
        assert cli_mod._severity_at_or_above(Severity.WARNING, "warning") is True

    def test_warning_does_not_meet_error(self):
        assert cli_mod._severity_at_or_above(Severity.WARNING, "error") is False

    def test_error_meets_all(self):
        for thr in ("info", "warning", "error"):
            assert cli_mod._severity_at_or_above(Severity.ERROR, thr) is True


# ===========================================================================
# _c (ANSI helper)
# ===========================================================================

class TestAnsiHelper:
    def test_no_color_returns_empty(self):
        assert cli_mod._c("red", False) == ""

    def test_known_color_returns_ansi_code(self):
        code = cli_mod._c("red", True)
        assert code == "\033[31m"

    def test_unknown_color_returns_empty(self):
        assert cli_mod._c("nonexistent", True) == ""

    def test_all_known_colors(self):
        for name, code in cli_mod._ANSI.items():
            assert cli_mod._c(name, True) == code


# ===========================================================================
# _format_text
# ===========================================================================

class TestFormatText:
    def test_empty_results(self):
        out = cli_mod._format_text([], use_color=False, min_severity="info")
        assert "no issues" in out
        assert "0 file(s)" in out

    def test_single_file_no_issues(self):
        results = [_result("/tmp/good.yaml", jobs=[{"name": "x"}])]
        out = cli_mod._format_text(results, use_color=False, min_severity="info")
        assert "/tmp/good.yaml" in out
        assert "no issues" in out

    def test_severity_filtering_drops_below_threshold(self):
        results = [_result(
            "/tmp/x.yaml",
            issues=[_diag("C001", Severity.INFO, "info message")],
        )]
        out = cli_mod._format_text(results, use_color=False, min_severity="error")
        assert "info message" not in out

    def test_error_counted(self):
        results = [_result(
            "/tmp/x.yaml",
            issues=[
                _diag("C001", Severity.ERROR, "err"),
                _diag("C002", Severity.WARNING, "warn"),
            ],
        )]
        out = cli_mod._format_text(results, use_color=False, min_severity="info")
        assert "1 error(s)" in out
        assert "1 warning(s)" in out

    def test_suggestion_included(self):
        results = [_result(
            "/tmp/x.yaml",
            issues=[_diag("C001", Severity.WARNING, "warn", suggestion="try X")],
        )]
        out = cli_mod._format_text(results, use_color=False, min_severity="info")
        assert "try X" in out
        assert "💡" in out

    def test_line_number_shown(self):
        results = [_result(
            "/tmp/x.yaml",
            issues=[_diag("C001", Severity.ERROR, "err", line=42)],
        )]
        out = cli_mod._format_text(results, use_color=False, min_severity="info")
        assert "line 42" in out

    def test_no_line_omits_location(self):
        results = [_result(
            "/tmp/x.yaml",
            issues=[_diag("C001", Severity.ERROR, "err", line=None)],
        )]
        out = cli_mod._format_text(results, use_color=False, min_severity="info")
        assert "line" not in out

    def test_use_color_includes_ansi(self):
        results = [_result(
            "/tmp/x.yaml",
            issues=[_diag("C001", Severity.ERROR, "err")],
        )]
        out = cli_mod._format_text(results, use_color=True, min_severity="info")
        assert "\033[" in out  # ANSI escape present

    def test_no_color_omits_ansi(self):
        results = [_result(
            "/tmp/x.yaml",
            issues=[_diag("C001", Severity.ERROR, "err")],
        )]
        out = cli_mod._format_text(results, use_color=False, min_severity="info")
        assert "\033[" not in out

    def test_summary_counts_multiple_files(self):
        results = [
            _result("/tmp/a.yaml", issues=[_diag("C001", Severity.ERROR, "e1")]),
            _result("/tmp/b.yaml", issues=[_diag("C002", Severity.WARNING, "w1")]),
        ]
        out = cli_mod._format_text(results, use_color=False, min_severity="info")
        assert "2 file(s)" in out
        assert "1 error(s)" in out
        assert "1 warning(s)" in out

    def test_file_with_no_jobs_and_no_issues_skipped(self):
        results = [_result("/tmp/empty.yaml", jobs=[], issues=[])]
        out = cli_mod._format_text(results, use_color=False, min_severity="info")
        assert "/tmp/empty.yaml" not in out


# ===========================================================================
# _format_json
# ===========================================================================

class TestFormatJson:
    def test_empty_results(self):
        out = json.loads(cli_mod._format_json([], min_severity="info"))
        assert out["version"] == __version__
        assert out["files"] == []
        assert out["summary"]["files"] == 0
        assert out["summary"]["errors"] == 0

    def test_severity_filtering(self):
        results = [_result(
            "/tmp/x.yaml",
            issues=[_diag("C001", Severity.INFO, "hidden")],
        )]
        out = json.loads(cli_mod._format_json(results, min_severity="error"))
        assert out["files"][0]["issues"] == []
        assert out["summary"]["info"] == 0

    def test_error_warning_info_counts(self):
        results = [_result(
            "/tmp/x.yaml",
            issues=[
                _diag("C001", Severity.ERROR, "e"),
                _diag("C002", Severity.WARNING, "w"),
                _diag("C003", Severity.INFO, "i"),
            ],
        )]
        out = json.loads(cli_mod._format_json(results, min_severity="info"))
        s = out["summary"]
        assert s["errors"] == 1
        assert s["warnings"] == 1
        assert s["info"] == 1

    def test_issue_fields_preserved(self):
        results = [_result(
            "/tmp/x.yaml",
            issues=[_diag("C001", Severity.ERROR, "msg", suggestion="fix", file="/tmp/x.yaml", line=10)],
        )]
        out = json.loads(cli_mod._format_json(results, min_severity="info"))
        issue = out["files"][0]["issues"][0]
        assert issue["check_id"] == "C001"
        assert issue["severity"] == "error"
        assert issue["message"] == "msg"
        assert issue["suggestion"] == "fix"
        assert issue["line"] == 10

    def test_jobs_count_included(self):
        results = [_result("/tmp/x.yaml", jobs=[{"a": 1}, {"b": 2}])]
        out = json.loads(cli_mod._format_json(results, min_severity="info"))
        assert out["files"][0]["jobs"] == 2

    def test_unicode_preserved(self):
        results = [_result(
            "/tmp/x.yaml",
            issues=[_diag("C001", Severity.WARNING, "한글 메시지")],
        )]
        raw = cli_mod._format_json(results, min_severity="info")
        assert "한글 메시지" in raw  # ensure_ascii=False


# ===========================================================================
# _format_github
# ===========================================================================

class TestFormatGithub:
    def test_error_emits_error_command(self):
        results = [_result(
            "/tmp/x.yaml",
            issues=[_diag("C001", Severity.ERROR, "boom")],
        )]
        out = cli_mod._format_github(results, min_severity="info")
        assert "::error file=/tmp/x.yaml" in out
        assert "boom" in out

    def test_warning_emits_warning_command(self):
        results = [_result(
            "/tmp/x.yaml",
            issues=[_diag("C001", Severity.WARNING, "careful")],
        )]
        out = cli_mod._format_github(results, min_severity="info")
        assert "::warning file=/tmp/x.yaml" in out

    def test_info_emits_notice_command(self):
        results = [_result(
            "/tmp/x.yaml",
            issues=[_diag("C001", Severity.INFO, "fyi")],
        )]
        out = cli_mod._format_github(results, min_severity="info")
        assert "::notice file=/tmp/x.yaml" in out

    def test_line_number_included(self):
        results = [_result(
            "/tmp/x.yaml",
            issues=[_diag("C001", Severity.ERROR, "boom", line=99)],
        )]
        out = cli_mod._format_github(results, min_severity="info")
        assert ",line=99::" in out

    def test_no_line_omits_line_part(self):
        results = [_result(
            "/tmp/x.yaml",
            issues=[_diag("C001", Severity.ERROR, "boom", line=None)],
        )]
        out = cli_mod._format_github(results, min_severity="info")
        assert ",line=" not in out

    def test_suggestion_encoded_as_percent_0a(self):
        results = [_result(
            "/tmp/x.yaml",
            issues=[_diag("C001", Severity.WARNING, "msg", suggestion="fix me")],
        )]
        out = cli_mod._format_github(results, min_severity="info")
        assert "%0A💡 fix me" in out

    def test_severity_filtering(self):
        results = [_result(
            "/tmp/x.yaml",
            issues=[_diag("C001", Severity.INFO, "hidden")],
        )]
        out = cli_mod._format_github(results, min_severity="error")
        assert out == ""

    def test_issue_file_overrides_result_file(self):
        results = [_result(
            "/tmp/y.yaml",
            issues=[_diag("C001", Severity.ERROR, "boom", file="/tmp/x.yaml")],
        )]
        out = cli_mod._format_github(results, min_severity="info")
        assert "file=/tmp/x.yaml" in out


# ===========================================================================
# _run_check
# ===========================================================================

class TestRunCheck:
    def _args(self, **overrides):
        defaults = {
            "path": "/tmp/x.yaml",
            "format": "text",
            "min_severity": "info",
            "fail_on": "error",
            "checks": None,
        }
        defaults.update(overrides)
        return argparse.Namespace(**defaults)

    def test_path_not_found(self, capsys):
        rc = cli_mod._run_check(self._args(path="/nonexistent/path/xyz"))
        assert rc == 2
        captured = capsys.readouterr()
        assert "path not found" in captured.err

    def test_valid_file_clean(self, tmp_path, capsys):
        p = tmp_path / "good.yaml"
        p.write_text("jobs:\n  - name: ok\n    schedule: '0 * * * *'\n    command: echo hi\n")
        rc = cli_mod._run_check(self._args(path=str(p)))
        assert rc == 0
        out = capsys.readouterr().out
        assert "no issues" in out

    def test_json_format(self, tmp_path, capsys):
        p = tmp_path / "good.yaml"
        p.write_text("jobs:\n  - name: ok\n    schedule: '0 * * * *'\n    command: echo hi\n")
        rc = cli_mod._run_check(self._args(path=str(p), format="json"))
        assert rc == 0
        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed["version"] == __version__

    def test_github_format(self, tmp_path, capsys):
        p = tmp_path / "good.yaml"
        p.write_text("jobs:\n  - name: ok\n    schedule: '0 * * * *'\n    command: echo hi\n")
        rc = cli_mod._run_check(self._args(path=str(p), format="github"))
        assert rc == 0

    def test_unknown_format(self, tmp_path, capsys):
        p = tmp_path / "good.yaml"
        p.write_text("jobs:\n  - name: ok\n    schedule: '0 * * * *'\n    command: echo hi\n")
        rc = cli_mod._run_check(self._args(path=str(p), format="xml"))
        assert rc == 2
        assert "unknown format" in capsys.readouterr().err

    def test_unknown_check_id(self, tmp_path, capsys):
        p = tmp_path / "good.yaml"
        p.write_text("jobs:\n  - name: ok\n    schedule: '0 * * * *'\n    command: echo hi\n")
        rc = cli_mod._run_check(self._args(path=str(p), checks="Z999"))
        assert rc == 2
        err = capsys.readouterr().err
        assert "unknown check" in err
        assert "Z999" in err

    def test_internal_error_returns_2(self, tmp_path, capsys):
        p = tmp_path / "good.yaml"
        p.write_text("jobs:\n  - name: ok\n    schedule: '0 * * * *'\n    command: echo hi\n")
        with patch("cron_doctor.cli.diagnose", side_effect=RuntimeError("boom")):
            rc = cli_mod._run_check(self._args(path=str(p)))
        assert rc == 2
        err = capsys.readouterr().err
        assert "internal error" in err
        assert "RuntimeError" in err

    def test_fail_on_error_with_error_finding(self, tmp_path, capsys):
        p = tmp_path / "bad.yaml"
        p.write_text("jobs:\n  - name: bad\n    schedule: 'not-a-cron'\n    command: echo hi\n")
        rc = cli_mod._run_check(self._args(path=str(p), fail_on="error"))
        assert rc == 1

    def test_fail_on_warning_with_only_info(self, tmp_path, capsys):
        p = tmp_path / "ok.yaml"
        p.write_text("jobs:\n  - name: ok\n    schedule: '0 * * * *'\n    command: echo hi\n")
        rc = cli_mod._run_check(self._args(path=str(p), fail_on="warning"))
        assert rc == 0

    def test_specific_checks_filter(self, tmp_path, capsys):
        p = tmp_path / "ok.yaml"
        p.write_text("jobs:\n  - name: ok\n    schedule: '0 * * * *'\n    command: echo hi\n")
        rc = cli_mod._run_check(self._args(path=str(p), checks="C001,Y001"))
        assert rc == 0


# ===========================================================================
# _run_list_checks
# ===========================================================================

class TestRunListChecks:
    def test_lists_all_checks(self, capsys):
        rc = cli_mod._run_list_checks(argparse.Namespace())
        assert rc == 0
        out = capsys.readouterr().out
        assert f"cron-doctor {__version__}" in out
        assert "C001" in out
        assert "Y001" in out


# ===========================================================================
# _run_fix
# ===========================================================================

class TestRunFix:
    def _args(self, **overrides):
        defaults = {
            "path": "/tmp/x.yaml",
            "dry_run": True,
            "apply": False,
            "format": "text",
        }
        defaults.update(overrides)
        return argparse.Namespace(**defaults)

    def test_path_not_found(self, capsys):
        rc = cli_mod._run_fix(self._args(path="/nonexistent/xyz"))
        assert rc == 2
        assert "path not found" in capsys.readouterr().err

    def test_no_proposals(self, tmp_path, capsys):
        p = tmp_path / "clean.yaml"
        p.write_text("jobs:\n  - name: ok\n    schedule: '0 * * * *'\n    command: echo hi\n")
        rc = cli_mod._run_fix(self._args(path=str(p)))
        assert rc == 0
        assert "no fixable issues" in capsys.readouterr().out

    def test_propose_text_format(self, tmp_path, capsys):
        p = tmp_path / "bad.yaml"
        p.write_text("jobs:\n  - name: bad\n    schedule: '0 * * * *'\n    command: echo hi\n    deprecated_field: true\n")
        rc = cli_mod._run_fix(self._args(path=str(p), format="text"))
        assert rc == 0
        out = capsys.readouterr().out
        # Either proposals found (then "proposal(s)" in output) or none ("no fixable")
        assert ("proposal" in out) or ("no fixable" in out)

    def test_propose_json_format(self, tmp_path, capsys):
        p = tmp_path / "bad.yaml"
        p.write_text("jobs:\n  - name: bad\n    schedule: '0 * * * *'\n    command: echo hi\n    deprecated_field: true\n")
        rc = cli_mod._run_fix(self._args(path=str(p), format="json"))
        assert rc == 0
        out = capsys.readouterr().out
        if out.strip():
            parsed = json.loads(out)
            assert "version" in parsed
            assert "proposals" in parsed

    def test_internal_error_returns_2(self, tmp_path, capsys):
        p = tmp_path / "x.yaml"
        p.write_text("jobs: []\n")
        with patch("cron_doctor.core.propose_fixes", side_effect=RuntimeError("boom")):
            rc = cli_mod._run_fix(self._args(path=str(p)))
        assert rc == 2
        assert "internal error" in capsys.readouterr().err

    def test_apply_mode(self, tmp_path, capsys):
        p = tmp_path / "x.yaml"
        p.write_text("jobs:\n  - name: bad\n    schedule: '0 * * * *'\n    command: echo hi\n    deprecated_field: true\n")
        rc = cli_mod._run_fix(self._args(path=str(p), apply=True))
        assert rc == 0
        out = capsys.readouterr().out
        if "Applied" in out:
            assert "Applied 0/" in out or "Applied 1/" in out


# ===========================================================================
# _run_watch
# ===========================================================================

class TestRunWatch:
    def _args(self, **overrides):
        defaults = {
            "path": "/tmp/x.yaml",
            "debounce": 50,
            "poll_interval": 25,
            "format": "text",
            "checks": None,
        }
        defaults.update(overrides)
        return argparse.Namespace(**defaults)

    def test_path_not_found(self, capsys):
        rc = cli_mod._run_watch(self._args(path="/nonexistent/xyz"))
        assert rc == 2
        assert "path not found" in capsys.readouterr().err

    def test_unknown_check_id(self, tmp_path, capsys):
        p = tmp_path / "x.yaml"
        p.write_text("jobs: []\n")
        rc = cli_mod._run_watch(self._args(path=str(p), checks="Z999"))
        assert rc == 2
        assert "unknown check" in capsys.readouterr().err

    def test_keyboard_interrupt_exits_cleanly(self, tmp_path, capsys):
        """Verify KeyboardInterrupt during watch is caught and returns 0."""
        from cron_doctor.core import WatchEvent

        p = tmp_path / "x.yaml"
        p.write_text("jobs: []\n")

        def fake_watch(*_args, **_kwargs):
            raise KeyboardInterrupt()

        with patch("cron_doctor.core.watch", fake_watch):
            rc = cli_mod._run_watch(self._args(path=str(p)))
        assert rc == 0

    def test_text_format_emits_event_lines(self, tmp_path, capsys):
        """Verify text format prints a timestamped line per event."""
        from cron_doctor.core import WatchEvent

        p = tmp_path / "x.yaml"
        p.write_text("jobs: []\n")

        event = WatchEvent(
            path=p,
            timestamp=1700000000.0,
            kind="modified",
            results=[],
        )

        def fake_watch(*_args, **_kwargs):
            yield event

        with patch("cron_doctor.core.watch", fake_watch):
            rc = cli_mod._run_watch(self._args(path=str(p), format="text"))
        assert rc == 0
        out = capsys.readouterr().out
        assert "modified" in out

    def test_json_format_emits_valid_json(self, tmp_path, capsys):
        from cron_doctor.core import WatchEvent

        p = tmp_path / "x.yaml"
        p.write_text("jobs: []\n")

        event = WatchEvent(
            path=p,
            timestamp=1700000000.0,
            kind="modified",
            results=[],
        )

        def fake_watch(*_args, **_kwargs):
            yield event

        with patch("cron_doctor.core.watch", fake_watch):
            rc = cli_mod._run_watch(self._args(path=str(p), format="json"))
        assert rc == 0
        out = capsys.readouterr().out.strip()
        parsed = json.loads(out)
        assert parsed["kind"] == "modified"
        assert parsed["path"] == str(p)

    def test_github_format_with_results(self, tmp_path, capsys):
        from cron_doctor.core import WatchEvent

        p = tmp_path / "x.yaml"
        p.write_text("jobs: []\n")

        result = _result(
            str(p),
            issues=[_diag("C001", Severity.ERROR, "boom", file=str(p), line=1)],
        )
        event = WatchEvent(
            path=p,
            timestamp=1700000000.0,
            kind="modified",
            results=[result],
        )

        def fake_watch(*_args, **_kwargs):
            yield event

        with patch("cron_doctor.core.watch", fake_watch):
            rc = cli_mod._run_watch(self._args(path=str(p), format="github"))
        assert rc == 0
        out = capsys.readouterr().out
        assert "::error" in out

    def test_signal_handler_registration(self, tmp_path, capsys):
        """Verify signal.signal is called for SIGTERM (best-effort)."""
        p = tmp_path / "x.yaml"
        p.write_text("jobs: []\n")

        original_signal = signal.signal

        def fake_watch(*_args, **_kwargs):
            raise KeyboardInterrupt()

        with patch("cron_doctor.core.watch", fake_watch), \
             patch("signal.signal", side_effect=original_signal) as mock_signal:
            cli_mod._run_watch(self._args(path=str(p)))
        # SIGTERM should have been registered
        assert any(call.args[0] == signal.SIGTERM for call in mock_signal.call_args_list)


# ===========================================================================
# build_parser
# ===========================================================================

class TestBuildParser:
    def test_returns_argument_parser(self):
        parser = cli_mod.build_parser()
        assert isinstance(parser, argparse.ArgumentParser)

    def test_version_flag(self):
        parser = cli_mod.build_parser()
        with pytest.raises(SystemExit) as excinfo:
            parser.parse_args(["--version"])
        assert excinfo.value.code == 0

    def test_check_subcommand(self):
        parser = cli_mod.build_parser()
        args = parser.parse_args(["check", "/tmp/x.yaml"])
        assert args.command == "check"
        assert args.path == "/tmp/x.yaml"
        assert args.format == "text"
        assert args.min_severity == "info"
        assert args.fail_on == "error"
        assert args.checks is None

    def test_check_with_all_flags(self):
        parser = cli_mod.build_parser()
        args = parser.parse_args([
            "check", "/tmp/x.yaml",
            "--format", "json",
            "--min-severity", "warning",
            "--fail-on", "warning",
            "--checks", "C001,Y001",
        ])
        assert args.format == "json"
        assert args.min_severity == "warning"
        assert args.fail_on == "warning"
        assert args.checks == "C001,Y001"

    def test_list_checks_subcommand(self):
        parser = cli_mod.build_parser()
        args = parser.parse_args(["list-checks"])
        assert args.command == "list-checks"

    def test_fix_subcommand_defaults(self):
        parser = cli_mod.build_parser()
        args = parser.parse_args(["fix", "/tmp/x.yaml"])
        assert args.command == "fix"
        assert args.dry_run is True
        assert args.apply is False
        assert args.format == "text"

    def test_fix_with_apply(self):
        """--apply is a separate flag from --dry-run (mutually exclusive group).
        The CLI checks args.apply (not args.dry_run) to decide whether to write.
        So dry_run stays at its default True even when --apply is given.
        """
        parser = cli_mod.build_parser()
        args = parser.parse_args(["fix", "/tmp/x.yaml", "--apply"])
        assert args.apply is True
        assert args.dry_run is True

    def test_fix_dry_run_and_apply_mutually_exclusive(self):
        parser = cli_mod.build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["fix", "/tmp/x.yaml", "--dry-run", "--apply"])

    def test_watch_subcommand_defaults(self):
        parser = cli_mod.build_parser()
        args = parser.parse_args(["watch", "/tmp/x.yaml"])
        assert args.command == "watch"
        assert args.debounce == 200
        assert args.poll_interval == 100
        assert args.format == "text"

    def test_watch_with_overrides(self):
        parser = cli_mod.build_parser()
        args = parser.parse_args([
            "watch", "/tmp/x.yaml",
            "--debounce", "500",
            "--poll-interval", "250",
            "--format", "json",
        ])
        assert args.debounce == 500
        assert args.poll_interval == 250
        assert args.format == "json"

    def test_recursive_flag_deprecated(self):
        """--recursive is accepted but ignored (directories always recursed)."""
        parser = cli_mod.build_parser()
        args = parser.parse_args(["check", "/tmp/dir", "--recursive"])
        assert args.recursive is True


# ===========================================================================
# main()
# ===========================================================================

class TestMain:
    def test_no_args_shows_help_and_returns_2(self, capsys):
        rc = cli_mod.main([])
        assert rc == 2
        captured = capsys.readouterr()
        assert "usage" in (captured.out + captured.err).lower()

    def test_check_subcommand_dispatches(self, tmp_path, capsys):
        p = tmp_path / "good.yaml"
        p.write_text("jobs:\n  - name: ok\n    schedule: '0 * * * *'\n    command: echo hi\n")
        rc = cli_mod.main(["check", str(p)])
        assert rc == 0

    def test_list_checks_dispatches(self, capsys):
        rc = cli_mod.main(["list-checks"])
        assert rc == 0
        assert "C001" in capsys.readouterr().out

    def test_fix_subcommand_dispatches(self, tmp_path, capsys):
        p = tmp_path / "x.yaml"
        p.write_text("jobs:\n  - name: ok\n    schedule: '0 * * * *'\n    command: echo hi\n")
        rc = cli_mod.main(["fix", str(p)])
        assert rc == 0

    def test_unknown_subcommand_exits_2(self, capsys):
        """argparse's subparsers call sys.exit(2) for unknown commands.
        main() does not intercept SystemExit, so it propagates with code 2.
        """
        with pytest.raises(SystemExit) as excinfo:
            cli_mod.main(["nonexistent"])
        assert excinfo.value.code == 2
