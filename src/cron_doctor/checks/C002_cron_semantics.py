"""C002: cron 표현식 의미 검사 (의심 패턴).

Applies SEMANTIC rules to detect suspicious schedules. These produce
WARNING or INFO — not ERROR — because the schedule is technically
valid; the rule is just flagging a likely authoring mistake.

Rules:
    1. Every-minute: minute covers 0-59 AND hour is unrestricted
       (and second is unrestricted / N/A). WARNING.
    2. dom=31 with any month → INFO (silent skip in short months).
    3. dom=30 with month=2 → INFO (Feb never has 30 days).
    4. dom=29 with month=2 → INFO (only leap years).
    5. Weekday field contains both 0 and 7 → WARNING (ambiguous).
"""

from __future__ import annotations

from cron_doctor.exceptions import InvalidCronExpression
from cron_doctor.models import Diagnosis, Severity
from cron_doctor.parsers.cron_expr import CronExpression, parse


class CronSemanticsCheck:
    check_id = "C002"
    name = "cron semantics"

    def run(self, job: dict, context: dict) -> list[Diagnosis]:
        issues: list[Diagnosis] = []
        schedule = job.get("schedule")
        if not isinstance(schedule, str) or not schedule.strip():
            return issues  # C001 / S001 territory

        try:
            expr = parse(schedule)
        except InvalidCronExpression:
            return issues  # C001 already covers parse errors

        file = context.get("file", "<unknown>")

        # Rule 1 & 2: every-minute detection
        if self._is_every_minute(expr):
            issues.append(Diagnosis(
                check_id=self.check_id,
                severity=Severity.WARNING,
                message=f"Schedule {schedule!r} runs every minute — high system load risk",
                suggestion="Consider a less frequent schedule (e.g., */5 or */15)",
                file=file,
            ))

        # Rule 3: dom=31 in any-month context, or dom=30 in Feb
        day_field, month_field = self._day_month_fields(schedule)
        if self._has_impossible_dom(day_field, month_field):
            issues.append(Diagnosis(
                check_id=self.check_id,
                severity=Severity.INFO,
                message=f"Schedule {schedule!r} uses day-of-month that doesn't exist in all months",
                suggestion="Verify the schedule fires as expected in short months",
                file=file,
            ))

        # Rule 4: dom=29 in February (leap year)
        if self._has_leap_dom(day_field, month_field):
            issues.append(Diagnosis(
                check_id=self.check_id,
                severity=Severity.INFO,
                message=f"Schedule {schedule!r} only fires on leap years (Feb 29)",
                file=file,
            ))

        # Rule 5: weekday 0 and 7 duplication (check raw string since parse() dedupes)
        if self._has_dow_0_and_7(schedule):
            issues.append(Diagnosis(
                check_id=self.check_id,
                severity=Severity.WARNING,
                message=f"Schedule {schedule!r} uses both 0 and 7 for Sunday — pick one",
                suggestion="Use 0 (or SUN) consistently",
                file=file,
            ))

        return issues

    def _is_every_minute(self, expr: CronExpression) -> bool:
        # If minute covers full 0-59 AND hour is unrestricted AND
        # (6-field: second is None or full 0-59)
        if len(expr.minute) != 60:
            return False
        if len(expr.hour) != 24:
            return False
        if expr.second is not None and len(expr.second) != 60:
            return False
        return True

    def _has_impossible_dom(self, day_field: str, month_field: str) -> bool:
        # Raw-string check: '*' expands to include 31 but should NOT warn.
        if "31" in self._explicit_day_values(day_field):
            return True
        if (
            "30" in self._explicit_day_values(day_field)
            and "2" in self._explicit_month_values(month_field)
        ):
            return True
        return False

    def _has_leap_dom(self, day_field: str, month_field: str) -> bool:
        if (
            "29" in self._explicit_day_values(day_field)
            and "2" in self._explicit_month_values(month_field)
        ):
            return True
        return False

    @staticmethod
    def _explicit_day_values(day_field: str) -> set[str]:
        if day_field.strip() == "*":
            return set()
        return {
            p.strip()
            for p in day_field.split(",")
            if p.strip().isdigit()
        }

    @staticmethod
    def _explicit_month_values(month_field: str) -> set[str]:
        if month_field.strip() == "*":
            return set()
        return {
            p.strip()
            for p in month_field.split(",")
            if p.strip().isdigit()
        }

    @staticmethod
    def _day_month_fields(schedule: str) -> tuple[str, str]:
        fields = schedule.split()
        if len(fields) == 6:
            # sec min hour dom mon dow
            return fields[3], fields[4]
        # min hour dom mon dow
        return fields[2], fields[3]

    def _has_dow_0_and_7(self, schedule: str) -> bool:
        fields = schedule.split()
        dow_field = fields[-1]  # weekday is always the LAST field
        parts = [p.strip() for p in dow_field.split(",")]
        has_zero = any(
            p in ("0", "*") or p.startswith("0-") or p == "0/1"
            for p in parts
        )
        has_seven = any(p == "7" or p.startswith("7-") for p in parts)
        return has_zero and has_seven
