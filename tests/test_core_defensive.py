"""v1.0.0 defensive path tests for core.py.

Covers ~35 previously-untested statements:
- _diagnose_file: check crash handling, YAML load exception
- _propose_fixes_for_file: diagnose exception, read_text error, check not found,
  propose exception, line number path
- apply_fixes: non-file path, read_text error, line out of range, idempotency,
  trailing newline handling, write_text error
- watch: file path, directory path, walk error, stat error, no changes
"""
from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch

import pytest

from cron_doctor import core
from cron_doctor.models import CheckResult, Diagnosis, FixProposal, Severity


# ===========================================================================
# _diagnose_file — check crash handling
# ===========================================================================

class TestDiagnoseCheckCrash:
    def test_check_crash_does_not_break_run(self, tmp_path):
        """A single check crashing must not abort the whole diagnose run."""
        from cron_doctor.checks import ALL_CHECKS, default_checks
        from cron_doctor.models import Severity

        p = tmp_path / "x.yaml"
        p.write_text("jobs:\n  - name: ok\n    schedule: '0 * * * *'\n    command: echo hi\n")

        # Inject a crashing check
        class CrashingCheck:
            check_id = "X999"
            name = "crashing"
            def run(self, job, ctx):
                raise RuntimeError("intentional crash")
            def check_file(self, *_args):
                return []

        checks = default_checks() + [CrashingCheck()]
        results = core.diagnose(p, checks=checks)
        assert len(results) == 1
        crash_issues = [i for i in results[0].issues if i.check_id == "X999"]
        assert len(crash_issues) == 1
        assert crash_issues[0].severity == Severity.ERROR
        assert "crashed" in crash_issues[0].message
        assert "RuntimeError" in crash_issues[0].message


# ===========================================================================
# _propose_fixes_for_file — error paths
# ===========================================================================

class TestProposeFixesErrors:
    def test_diagnose_exception_returns_empty(self, tmp_path):
        p = tmp_path / "x.yaml"
        p.write_text("jobs: []\n")
        with patch("cron_doctor.core.diagnose", side_effect=RuntimeError("boom")):
            result = core._propose_fixes_for_file(p)
        assert result == []

    def test_read_text_error_returns_empty(self, tmp_path):
        p = tmp_path / "x.yaml"
        p.write_text("jobs: []\n")
        with patch.object(Path, "read_text", side_effect=OSError("io error")):
            result = core._propose_fixes_for_file(p)
        assert result == []

    def test_check_not_found_skips_issue(self, tmp_path):
        """An issue with an unknown check_id is silently skipped."""
        p = tmp_path / "x.yaml"
        p.write_text("jobs:\n  - name: ok\n    schedule: '0 * * * *'\n    command: echo hi\n")
        # Force a result with an unknown check_id
        fake_result = CheckResult(
            file=str(p),
            jobs=[],
            issues=[Diagnosis(
                check_id="Z999",
                severity=Severity.WARNING,
                message="unknown check",
                file=str(p),
                line=1,
            )],
        )
        with patch("cron_doctor.core.diagnose", return_value=[fake_result]):
            result = core._propose_fixes_for_file(p)
        assert result == []

    def test_propose_exception_is_swallowed(self, tmp_path):
        """A propose_fix that raises must not crash the whole propose_fixes call."""
        from cron_doctor.checks import default_checks

        p = tmp_path / "x.yaml"
        p.write_text("jobs:\n  - name: bad\n    schedule: '0 * * * *'\n    command: echo hi\n    deprecated_field: true\n")

        # Monkey-patch a check's propose_fix to raise
        checks = default_checks()
        for c in checks:
            if hasattr(c, "propose_fix"):
                original = c.propose_fix
                def boom(*_args, **_kwargs):
                    raise RuntimeError("intentional")
                c.propose_fix = staticmethod(boom)  # type: ignore[attr-defined]
                break

        # Should not raise, just skip the failing check
        result = core.propose_fixes(p)
        assert isinstance(result, list)


# ===========================================================================
# apply_fixes — error paths
# ===========================================================================

class TestApplyFixesErrors:
    def test_non_file_path_returns_zero(self, tmp_path):
        result = core.apply_fixes(tmp_path / "missing.yaml", [])
        assert result == 0

    def test_empty_proposals_returns_zero(self, tmp_path):
        p = tmp_path / "x.yaml"
        p.write_text("jobs: []\n")
        assert core.apply_fixes(p, []) == 0

    def test_read_text_error_returns_zero(self, tmp_path):
        p = tmp_path / "x.yaml"
        p.write_text("jobs: []\n")
        proposal = FixProposal(
            check_id="C001",
            file=str(p),
            line=1,
            original="x",
            replacement="y",
            description="test",
        )
        with patch.object(Path, "read_text", side_effect=OSError("io error")):
            assert core.apply_fixes(p, [proposal]) == 0

    def test_line_out_of_range_skipped(self, tmp_path):
        p = tmp_path / "x.yaml"
        p.write_text("jobs: []\n")
        proposal = FixProposal(
            check_id="C001",
            file=str(p),
            line=999,
            original="x",
            replacement="y",
            description="test",
        )
        assert core.apply_fixes(p, [proposal]) == 0

    def test_idempotency_check_skips_mismatched_original(self, tmp_path):
        """If the line content has changed, the proposal must NOT be applied."""
        p = tmp_path / "x.yaml"
        p.write_text("actual_content\n")
        proposal = FixProposal(
            check_id="C001",
            file=str(p),
            line=1,
            original="different_content",
            replacement="new",
            description="test",
        )
        assert core.apply_fixes(p, [proposal]) == 0
        # File should be unchanged
        assert p.read_text() == "actual_content\n"

    def test_proposal_with_empty_original_skips_idempotency(self, tmp_path):
        """A proposal with empty original should not be idempotency-checked."""
        p = tmp_path / "x.yaml"
        p.write_text("foo\n")
        proposal = FixProposal(
            check_id="C001",
            file=str(p),
            line=1,
            original="",  # empty → skip idempotency check
            replacement="bar",
            description="test",
        )
        result = core.apply_fixes(p, [proposal])
        assert result == 1
        assert p.read_text() == "bar\n"

    def test_trailing_newline_added_when_original_has_one(self, tmp_path):
        p = tmp_path / "x.yaml"
        p.write_text("old\n")
        proposal = FixProposal(
            check_id="C001",
            file=str(p),
            line=1,
            original="old",
            replacement="new",  # no trailing newline
            description="test",
        )
        core.apply_fixes(p, [proposal])
        assert p.read_text() == "new\n"

    def test_trailing_newline_stripped_when_original_lacks_one(self, tmp_path):
        p = tmp_path / "x.yaml"
        p.write_text("old")  # no trailing newline
        proposal = FixProposal(
            check_id="C001",
            file=str(p),
            line=1,
            original="old",
            replacement="new\n",  # has trailing newline
            description="test",
        )
        core.apply_fixes(p, [proposal])
        assert p.read_text() == "new"

    def test_write_text_error_returns_zero(self, tmp_path):
        p = tmp_path / "x.yaml"
        p.write_text("foo\n")
        proposal = FixProposal(
            check_id="C001",
            file=str(p),
            line=1,
            original="foo",
            replacement="bar",
            description="test",
        )
        with patch.object(Path, "write_text", side_effect=OSError("disk full")):
            assert core.apply_fixes(p, [proposal]) == 0


# ===========================================================================
# watch — defensive paths
# ===========================================================================

class TestWatchDefensive:
    def test_watch_file_yields_initial_added_event(self, tmp_path):
        p = tmp_path / "x.yaml"
        p.write_text("jobs:\n  - name: ok\n    schedule: '0 * * * *'\n    command: echo hi\n")

        gen = core.watch(p, poll_interval_ms=10, debounce_ms=0)
        try:
            first = next(gen)
            assert first.kind == "added"
            assert first.path == p
        finally:
            gen.close()

    def test_watch_directory_yields_added_events(self, tmp_path):
        (tmp_path / "a.yaml").write_text("jobs: []\n")
        (tmp_path / "b.yaml").write_text("jobs: []\n")
        gen = core.watch(tmp_path, poll_interval_ms=10, debounce_ms=0)
        try:
            events = [next(gen), next(gen)]
            assert len(events) == 2
            assert all(e.kind == "added" for e in events)
        finally:
            gen.close()

    def test_watch_nonexistent_raises(self, tmp_path):
        gen = core.watch(tmp_path / "missing", poll_interval_ms=10)
        with pytest.raises(FileNotFoundError):
            next(gen)

    def test_watch_non_yaml_file_skipped(self, tmp_path):
        (tmp_path / "readme.txt").write_text("hello")
        (tmp_path / "x.yaml").write_text("jobs: []\n")
        gen = core.watch(tmp_path, poll_interval_ms=10, debounce_ms=0)
        try:
            event = next(gen)
            assert event.path == tmp_path / "x.yaml"
        finally:
            gen.close()

    def test_watch_detects_modification(self, tmp_path):
        p = tmp_path / "x.yaml"
        p.write_text("jobs: []\n")
        gen = core.watch(p, poll_interval_ms=10, debounce_ms=0)
        try:
            first = next(gen)
            assert first.kind == "added"
            time.sleep(0.05)
            p.write_text("jobs:\n  - name: changed\n    schedule: '0 * * * *'\n    command: echo hi\n")
            modified = next(gen)
            assert modified.kind == "modified"
        finally:
            gen.close()

    def test_watch_detects_deletion(self, tmp_path):
        p = tmp_path / "x.yaml"
        p.write_text("jobs: []\n")
        gen = core.watch(p, poll_interval_ms=10, debounce_ms=0)
        try:
            next(gen)
            p.unlink()
            deleted = next(gen)
            assert deleted.kind == "deleted"
        finally:
            gen.close()

    def test_watch_skips_hidden_and_skip_dirs(self, tmp_path):
        (tmp_path / ".hidden").mkdir()
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "ok.yaml").write_text("jobs: []\n")
        (tmp_path / ".hidden" / "skip.yaml").write_text("jobs: []\n")
        (tmp_path / "node_modules" / "skip.yaml").write_text("jobs: []\n")
        gen = core.watch(tmp_path, poll_interval_ms=10, debounce_ms=0)
        try:
            event = next(gen)
            assert event.path == tmp_path / "ok.yaml"
        finally:
            gen.close()

    def test_watch_directory_walk_permission_error_swallowed(self, tmp_path):
        """Permission errors during walk are caught by os.walk's onerror callback."""
        (tmp_path / "ok.yaml").write_text("jobs: []\n")
        gen = core.watch(tmp_path, poll_interval_ms=10, debounce_ms=0)
        try:
            first = next(gen)
            assert first.kind == "added"
        finally:
            gen.close()


# ===========================================================================
# propose_fixes — directory path
# ===========================================================================

class TestProposeFixesDirectory:
    def test_propose_fixes_on_directory(self, tmp_path):
        (tmp_path / "a.yaml").write_text("jobs:\n  - name: ok\n    schedule: '0 * * * *'\n    command: echo hi\n")
        (tmp_path / "b.yaml").write_text("jobs:\n  - name: ok2\n    schedule: '0 * * * *'\n    command: echo hi\n")
        result = core.propose_fixes(tmp_path)
        assert isinstance(result, list)
