"""v1.0.0 edge case tests for C002 (cron semantics) check.

Covers 30 previously-untested statements:
- 6-field cron (with seconds) for every-minute detection
- _explicit_month_values with non-* field
- propose_fix for weekday 0-and-7 normalization
- Impossible DOM (day 31)
- Leap DOM (day 29 in February)
- Weekday both 0 and 7 detection
"""
from __future__ import annotations

from pathlib import Path

import pytest

from cron_doctor.checks.C002_cron_semantics import CronSemanticsCheck
from cron_doctor.models import Diagnosis, Severity


def _ctx(file="/tmp/x.yaml", all_jobs=None, job_index=0):
    return {"file": file, "all_jobs": all_jobs or [], "job_index": job_index}


# ===========================================================================
# _is_every_minute — 6-field variants
# ===========================================================================

class TestIsEveryMinute:
    def setup_method(self):
        self.check = CronSemanticsCheck()

    def test_5_field_every_minute(self):
        """5-field cron with '* * * * *' is every minute."""
        from cron_doctor.parsers.cron_expr import parse
        expr = parse("* * * * *")
        assert self.check._is_every_minute(expr) is True

    def test_6_field_every_minute_with_seconds(self):
        """6-field cron with '* * * * * *' is every minute."""
        from cron_doctor.parsers.cron_expr import parse
        expr = parse("* * * * * *")
        assert self.check._is_every_minute(expr) is True

    def test_6_field_with_restricted_seconds_not_every_minute(self):
        """6-field cron with */30 seconds is NOT every minute."""
        from cron_doctor.parsers.cron_expr import parse
        expr = parse("*/30 * * * * *")
        assert self.check._is_every_minute(expr) is False

    def test_minute_not_full(self):
        """*/5 minute is NOT every minute."""
        from cron_doctor.parsers.cron_expr import parse
        expr = parse("*/5 * * * *")
        assert self.check._is_every_minute(expr) is False

    def test_hour_not_full(self):
        """*/2 hour is NOT every minute."""
        from cron_doctor.parsers.cron_expr import parse
        expr = parse("* */2 * * *")
        assert self.check._is_every_minute(expr) is False


# ===========================================================================
# _explicit_month_values
# ===========================================================================

class TestExplicitMonthValues:
    def test_wildcard_returns_empty(self):
        assert CronSemanticsCheck._explicit_month_values("*") == set()

    def test_specific_months(self):
        result = CronSemanticsCheck._explicit_month_values("1,3,5")
        assert result == {"1", "3", "5"}

    def test_filters_non_digits(self):
        """Non-digit values (like JAN) are filtered out."""
        result = CronSemanticsCheck._explicit_month_values("1,JAN,3")
        assert result == {"1", "3"}


# ===========================================================================
# _has_impossible_dom / _has_leap_dom
# ===========================================================================

class TestImpossibleLeapDom:
    def setup_method(self):
        self.check = CronSemanticsCheck()

    def test_day_31_in_february_detected(self):
        assert self.check._has_impossible_dom("31", "2") is True

    def test_day_30_in_february_detected(self):
        assert self.check._has_impossible_dom("30", "2") is True

    def test_day_30_in_january_ok(self):
        assert self.check._has_impossible_dom("30", "1") is False

    def test_wildcard_day_not_flagged(self):
        """'*' for day expands to include 31 but should NOT trigger."""
        assert self.check._has_impossible_dom("*", "2") is False

    def test_leap_day_29_in_february(self):
        assert self.check._has_leap_dom("29", "2") is True

    def test_leap_day_29_in_january_not_flagged(self):
        assert self.check._has_leap_dom("29", "1") is False

    def test_no_leap_day(self):
        assert self.check._has_leap_dom("15", "2") is False


# ===========================================================================
# _has_dow_0_and_7
# ===========================================================================

class TestDow0And7:
    def setup_method(self):
        self.check = CronSemanticsCheck()

    def test_both_0_and_7(self):
        assert self.check._has_dow_0_and_7("0 5 * * 0,7") is True

    def test_only_0(self):
        assert self.check._has_dow_0_and_7("0 5 * * 0") is False

    def test_only_7(self):
        assert self.check._has_dow_0_and_7("0 5 * * 7") is False

    def test_neither(self):
        assert self.check._has_dow_0_and_7("0 5 * * 1,2") is False

    def test_0_as_range(self):
        assert self.check._has_dow_0_and_7("0 5 * * 0-3,7") is True

    def test_6_field_both(self):
        assert self.check._has_dow_0_and_7("0 0 5 * * 0,7") is True


# ===========================================================================
# propose_fix — weekday 0-and-7 normalization
# ===========================================================================

class TestProposeFixDow:
    def setup_method(self):
        self.check = CronSemanticsCheck()

    def test_propose_fix_dedups_0_and_7(self):
        diagnosis = Diagnosis(
            check_id="C002",
            severity=Severity.WARNING,
            message="Weekday field contains both 0 and 7",
            file="/tmp/x.yaml",
            line=1,
        )
        original = "    schedule: '0 0 * * 0,7'\n"
        proposal = CronSemanticsCheck.propose_fix(diagnosis, original)
        assert proposal is not None
        assert "0,7" not in proposal.replacement
        assert "0" in proposal.replacement

    def test_propose_fix_normalizes_7_to_0_in_range(self):
        diagnosis = Diagnosis(
            check_id="C002",
            severity=Severity.WARNING,
            message="Weekday field contains both 0 and 7",
            file="/tmp/x.yaml",
            line=1,
        )
        original = "    schedule: '0 0 * * 0,7-5'\n"
        proposal = CronSemanticsCheck.propose_fix(diagnosis, original)
        assert proposal is not None
        assert "7-5" not in proposal.replacement

    def test_propose_fix_returns_none_for_unrelated_diagnosis(self):
        diagnosis = Diagnosis(
            check_id="C002",
            severity=Severity.WARNING,
            message="Some other issue",
            file="/tmp/x.yaml",
            line=1,
        )
        result = CronSemanticsCheck.propose_fix(diagnosis, "    schedule: '0 * * * *'\n")
        assert result is None

    def test_propose_fix_returns_none_without_schedule_keyword(self):
        diagnosis = Diagnosis(
            check_id="C002",
            severity=Severity.WARNING,
            message="Weekday field contains both 0 and 7",
            file="/tmp/x.yaml",
            line=1,
        )
        result = CronSemanticsCheck.propose_fix(diagnosis, "not a schedule line\n")
        assert result is None

    def test_propose_fix_returns_none_for_short_schedule(self):
        diagnosis = Diagnosis(
            check_id="C002",
            severity=Severity.WARNING,
            message="Weekday field contains both 0 and 7",
            file="/tmp/x.yaml",
            line=1,
        )
        result = CronSemanticsCheck.propose_fix(diagnosis, "    schedule: 'bad'\n")
        assert result is None

    def test_propose_fix_dedups_repeated_values(self):
        diagnosis = Diagnosis(
            check_id="C002",
            severity=Severity.WARNING,
            message="Weekday field contains both 0 and 7",
            file="/tmp/x.yaml",
            line=1,
        )
        original = "    schedule: '0 0 * * 0,0,7,7'\n"
        proposal = CronSemanticsCheck.propose_fix(diagnosis, original)
        assert proposal is not None
        replacement_dow = proposal.replacement.split("'")[1].split()[-1]
        assert replacement_dow.count("0") == 1
        assert "7" not in replacement_dow

    def test_propose_fix_unquoted_schedule(self):
        diagnosis = Diagnosis(
            check_id="C002",
            severity=Severity.WARNING,
            message="Weekday field contains both 0 and 7",
            file="/tmp/x.yaml",
            line=1,
        )
        original = "    schedule: 0 0 * * 0,7\n"
        proposal = CronSemanticsCheck.propose_fix(diagnosis, original)
        assert proposal is not None


# ===========================================================================
# run() — end-to-end through diagnose pipeline
# ===========================================================================

class TestC002Run:
    def test_every_minute_warning(self, tmp_path):
        p = tmp_path / "x.yaml"
        p.write_text("jobs:\n  - name: spam\n    schedule: '* * * * *'\n    command: echo hi\n")
        from cron_doctor import core
        results = core.diagnose(p)
        msgs = [i.message for i in results[0].issues]
        assert any("every minute" in m.lower() for m in msgs)

    def test_dom_31_in_february(self, tmp_path):
        p = tmp_path / "x.yaml"
        p.write_text("jobs:\n  - name: bad\n    schedule: '0 0 31 2 *'\n    command: echo hi\n")
        from cron_doctor import core
        results = core.diagnose(p)
        msgs = [i.message for i in results[0].issues]
        assert any("31" in m for m in msgs)

    def test_dow_0_and_7(self, tmp_path):
        p = tmp_path / "x.yaml"
        p.write_text("jobs:\n  - name: bad\n    schedule: '0 0 * * 0,7'\n    command: echo hi\n")
        from cron_doctor import core
        results = core.diagnose(p)
        msgs = [i.message for i in results[0].issues]
        assert any("0 and 7" in m for m in msgs)
