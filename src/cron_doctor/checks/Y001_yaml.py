"""Y001 - YAML syntax file-level check.

Implements YAMLCheck used by core.py to validate the whole cron YAML file
before running per-job checks. It attempts to load the YAML using the
project's YAML loader and converts loader exceptions into Diagnosis objects.
"""

from __future__ import annotations

from cron_doctor.models import Diagnosis, Severity
from cron_doctor.exceptions import ParseError, UnreadableFileError
from cron_doctor.parsers.yaml_loader import load_cron_yaml


class YAMLCheck:
    check_id = "Y001"
    name = "YAML syntax"

    def run(self, job, context):
        """Per-job check: YAML is a file-level check so return no issues."""
        return []

    def check_file(self, path: str) -> list[Diagnosis]:
        """Try loading YAML at `path`. Convert known loader exceptions to
        Diagnosis objects as specified by the project.
        """
        issues: list[Diagnosis] = []
        try:
            load_cron_yaml(path)
        except ParseError as e:
            issues.append(
                Diagnosis(
                    check_id=self.check_id,
                    severity=Severity.ERROR,
                    message=f"YAML parse error: {getattr(e, 'message', str(e))}",
                    suggestion="Fix the YAML syntax at the indicated line/column",
                    file=getattr(e, 'file', path),
                    line=getattr(e, 'line', None),
                )
            )
        except UnreadableFileError as e:
            issues.append(
                Diagnosis(
                    check_id=self.check_id,
                    severity=Severity.ERROR,
                    message=f"Cannot read file: {getattr(e, 'reason', str(e))}",
                    file=str(getattr(e, 'path', path)),
                )
            )

        return issues
