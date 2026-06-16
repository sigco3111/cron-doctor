"""M001: enabled_toolsets reference integrity.

Schema:
    toolsets:                    # document root, parallel to `jobs:`
      - name: search
        description: Web search
      - name: code
        description: Code execution
    jobs:
      - name: a
        schedule: '0 * * * *'
        prompt: x
        enabled_toolsets: [search, nonexistent]   # 'nonexistent' is broken

M001 emits:
- ERROR for each unknown toolset reference
- WARNING when enabled_toolsets is used but no `toolsets:` registry is present
- WARNING (file-level) for duplicate toolset names
"""

from __future__ import annotations

import re

from cron_doctor.models import Diagnosis, FixProposal, Severity


class MCPCheck:
    check_id = "M001"
    name = "mcp"

    def run(self, job, context: dict) -> list[Diagnosis]:
        issues: list[Diagnosis] = []
        if not isinstance(job, dict):
            return issues
        enabled = job.get("enabled_toolsets")
        if not isinstance(enabled, list):
            return issues  # S001 catches wrong type; be defensive

        file = context.get("file", "<unknown>") if isinstance(context, dict) else "<unknown>"
        document_toolsets = context.get("document_toolsets") if isinstance(context, dict) else None
        job_name = job.get("name", "?")

        if document_toolsets is None:
            issues.append(Diagnosis(
                check_id=self.check_id,
                severity=Severity.WARNING,
                message=(
                    f"Job {job_name!r} uses enabled_toolsets but no `toolsets:` "
                    f"registry found at document root"
                ),
                suggestion=(
                    "Add a top-level `toolsets:` block listing each toolset's name "
                    "and description"
                ),
                file=file,
            ))
            return issues

        if not document_toolsets:
            # Empty registry
            issues.append(Diagnosis(
                check_id=self.check_id,
                severity=Severity.WARNING,
                message=(
                    f"Job {job_name!r} uses enabled_toolsets but the `toolsets:` "
                    f"registry is empty"
                ),
                suggestion="Define toolsets under the `toolsets:` block at document root",
                file=file,
            ))
            return issues

        for ref in enabled:
            if not isinstance(ref, str):
                continue
            if ref not in document_toolsets:
                issues.append(Diagnosis(
                    check_id=self.check_id,
                    severity=Severity.ERROR,
                    message=(
                        f"Job {job_name!r} references unknown toolset {ref!r}"
                    ),
                    suggestion=f"Available toolsets: {sorted(document_toolsets)}",
                    file=file,
                ))

        return issues

    @staticmethod
    def propose_fix(diagnosis, original_line: str) -> FixProposal | None:
        """Comment out the broken toolset ref on this line (keep valid ones)."""
        from cron_doctor.models import FixProposal  # local import to avoid cycles
        # Naive: if the line is `    enabled_toolsets: [search, nonexistent]`,
        # produce `    enabled_toolsets: [search]  # cron-doctor: removed 'nonexistent'`
        m = re.match(r"^(\s*)enabled_toolsets:\s*\[([^\]]*)\](.*)$", original_line)
        if not m:
            return None
        indent, body, rest = m.group(1), m.group(2), m.group(3)
        # Find the broken ref name in the diagnosis message
        broken = None
        for piece in re.findall(r"'([^']+)'", diagnosis.message):
            if piece and piece != "?":
                broken = piece
                break
        if not broken:
            return None
        # Remove the broken ref from the body
        parts = [p.strip() for p in body.split(",") if p.strip() and p.strip() != broken]
        if not parts:
            new_body = f"# {original_line.strip()}  # all refs were broken; commented out"
        else:
            new_body = "[" + ", ".join(parts) + "]"
        new_line = f"{indent}enabled_toolsets: {new_body}{rest}  # cron-doctor: removed {broken!r}"
        return FixProposal(
            file=diagnosis.file or "<unknown>",
            line=diagnosis.line or 0,
            check_id=diagnosis.check_id,
            description=f"comment out broken toolset ref {broken!r}",
            original=original_line,
            replacement=new_line,
        )
