"""S001: Hermes cron.yaml 스키마 검증.

Validates each job dict against the Hermes cron.yaml schema:
- Required keys: name (str), schedule (str), and one of prompt/script/command.
- Optional allowed keys: timezone, context_from, enabled_toolsets, workdir,
  skills, model, deliver, repeat, no_agent, profile, env.
- Unknown keys → WARNING (to allow forward-compatible extensions).
- Type errors on required fields → ERROR.
- Type errors on optional fields (e.g. timezone) → WARNING.
"""

from __future__ import annotations

from cron_doctor.models import Diagnosis, Severity


_ALLOWED_KEYS = {
    # Required
    "name", "schedule",
    # Required one-of
    "prompt", "script", "command",
    # Optional
    "timezone", "context_from", "enabled_toolsets", "workdir", "skills",
    "model", "deliver", "repeat", "no_agent", "profile", "env",
}

_REQUIRED_KEYS = ("name", "schedule")
_REQUIRED_ONE_OF = ("prompt", "script", "command")


class SchemaCheck:
    check_id = "S001"
    name = "schema"

    def run(self, job, context: dict) -> list[Diagnosis]:
        issues: list[Diagnosis] = []
        file = context.get("file", "<unknown>") if isinstance(context, dict) else "<unknown>"

        if not isinstance(job, dict):
            issues.append(Diagnosis(
                check_id=self.check_id,
                severity=Severity.ERROR,
                message=f"Job must be a dict, got {type(job).__name__}",
                file=file,
            ))
            return issues

        # Required keys
        for key in _REQUIRED_KEYS:
            if key not in job:
                issues.append(Diagnosis(
                    check_id=self.check_id,
                    severity=Severity.ERROR,
                    message=f"Missing required key {key!r}",
                    suggestion=f"Add {key!r} to the job",
                    file=file,
                ))

        # Required one-of
        if not any(k in job for k in _REQUIRED_ONE_OF):
            issues.append(Diagnosis(
                check_id=self.check_id,
                severity=Severity.ERROR,
                message=f"Job must have one of {list(_REQUIRED_ONE_OF)} (got none)",
                suggestion=f"Add one of these keys to define what the job does",
                file=file,
            ))

        # Type checks (only if key is present)
        if "name" in job and not isinstance(job["name"], str):
            issues.append(Diagnosis(
                check_id=self.check_id,
                severity=Severity.ERROR,
                message=f"'name' must be a string, got {type(job['name']).__name__}",
                file=file,
            ))

        if "schedule" in job and not isinstance(job["schedule"], str):
            issues.append(Diagnosis(
                check_id=self.check_id,
                severity=Severity.ERROR,
                message=f"'schedule' must be a string, got {type(job['schedule']).__name__}",
                file=file,
            ))

        if "context_from" in job and not isinstance(job["context_from"], list):
            issues.append(Diagnosis(
                check_id=self.check_id,
                severity=Severity.ERROR,
                message=f"'context_from' must be a list, got {type(job['context_from']).__name__}",
                file=file,
            ))

        # repeat must be int and not bool (bool is a subclass of int in Python)
        if "repeat" in job:
            val = job["repeat"]
            if not isinstance(val, int) or isinstance(val, bool):
                issues.append(Diagnosis(
                    check_id=self.check_id,
                    severity=Severity.ERROR,
                    message=f"'repeat' must be an int, got {type(val).__name__}",
                    file=file,
                ))

        # Unknown keys (WARNING to allow extensions)
        for key in job.keys():
            if key not in _ALLOWED_KEYS:
                issues.append(Diagnosis(
                    check_id=self.check_id,
                    severity=Severity.WARNING,
                    message=f"Unknown key {key!r} — not in Hermes cron.yaml schema",
                    suggestion=f"Allowed keys: {sorted(_ALLOWED_KEYS)}",
                    file=file,
                ))

        # Optional type checks (WARNING)
        if "timezone" in job and not isinstance(job["timezone"], str):
            issues.append(Diagnosis(
                check_id=self.check_id,
                severity=Severity.WARNING,
                message=f"'timezone' should be a string, got {type(job['timezone']).__name__}",
                file=file,
            ))

        return issues
