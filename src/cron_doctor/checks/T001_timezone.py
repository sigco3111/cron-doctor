"""T001: Validate the `timezone` field of a cron job.

The `timezone` field is optional in the Hermes cron.yaml schema. When present,
it must be a non-empty string that names a valid IANA timezone (e.g.
`America/New_York`, `Asia/Seoul`, `UTC`). We use the stdlib `zoneinfo.ZoneInfo`
(Python 3.9+) so this check has zero external dependencies.

Severity is WARNING (not ERROR): a missing timezone is fine, and an unknown
timezone is usually a typo, not a hard failure. Operators can still treat
warnings as errors via the global `--fail-on` flag.
"""

from __future__ import annotations

import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from cron_doctor.models import Diagnosis, FixProposal, Severity


class TimezoneCheck:
    check_id = "T001"
    name = "timezone"

    def run(self, job, context: dict) -> list[Diagnosis]:
        issues: list[Diagnosis] = []
        file = context.get("file", "<unknown>") if isinstance(context, dict) else "<unknown>"

        if not isinstance(job, dict):
            return issues

        tz = job.get("timezone")
        if tz is None:
            return issues  # timezone is optional

        if not isinstance(tz, str) or not tz.strip():
            issues.append(Diagnosis(
                check_id=self.check_id,
                severity=Severity.WARNING,
                message=f"Invalid timezone {tz!r} (empty or non-string)",
                file=file,
            ))
            return issues

        try:
            ZoneInfo(tz)
        except (ZoneInfoNotFoundError, ValueError, NotImplementedError):
            issues.append(Diagnosis(
                check_id=self.check_id,
                severity=Severity.WARNING,
                message=f"Invalid timezone {tz!r} — not a recognized IANA timezone",
                suggestion="Use a valid IANA name like 'UTC' or 'America/New_York'",
                file=file,
            ))
        return issues

    @staticmethod
    def propose_fix(diagnosis, original_line: str) -> FixProposal | None:
        """Replace an invalid `timezone: <value>` line with `timezone: UTC`."""
        new_line = re.sub(
            r"^(\s*)timezone:\s*\S+",
            r"\1timezone: UTC",
            original_line,
        )
        return FixProposal(
            file=diagnosis.file or "<unknown>",
            line=diagnosis.line or 0,
            check_id=diagnosis.check_id,
            description="replace invalid timezone with 'UTC'",
            original=original_line,
            replacement=new_line,
        )
