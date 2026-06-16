"""C001: cron expression syntax validation.

This check validates that a job's `schedule` is a valid 5- or 6-field
cron expression using the parser in cron_doctor.parsers.cron_expr.
If parsing raises InvalidCronExpression a Diagnosis with Severity.ERROR
is returned.
"""
from cron_doctor.exceptions import InvalidCronExpression
from cron_doctor.models import Diagnosis, Severity
from cron_doctor.parsers.cron_expr import parse


class CronSyntaxCheck:
    check_id = "C001"
    name = "cron syntax"

    def run(self, job: dict, context: dict) -> list[Diagnosis]:
        issues: list[Diagnosis] = []
        schedule = job.get("schedule")
        if not isinstance(schedule, str) or not schedule.strip():
            # C001 only validates non-empty string schedules
            # (S001 catches missing schedule field)
            return issues

        try:
            parse(schedule)
        except InvalidCronExpression as e:
            file = context.get("file", "<unknown>")
            suggestion = None
            if getattr(e, "field_name", None):
                suggestion = f"Fix the {e.field_name} field (index {e.field_index})"
            issues.append(Diagnosis(
                check_id=self.check_id,
                severity=Severity.ERROR,
                message=f"Invalid cron expression {e.expression!r}: {e.message}",
                suggestion=suggestion,
                file=file,
            ))
        return issues
