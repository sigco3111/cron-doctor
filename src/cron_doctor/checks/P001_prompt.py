"""P001: Prompt self-validation.

Validates the optional `prompt` field of a cron job:
- Length rule: prompts over ``_PROMPT_MAX`` chars (10000) emit a WARNING
  suggesting the user split or summarize the prompt.
- Sensitive info: regex-based detection of common secret patterns emits an
  ERROR. Conservative placeholders (CHANGEME, XXX, <template>, etc.) are
  excluded from the generic-password rule to avoid false positives.

Implements :class:`cron_doctor.models.BaseCheck` and exposes a
``propose_fix`` static helper that redacts any matched secret pattern with
``[REDACTED]`` for autofix support.
"""

from __future__ import annotations

import re
from typing import Optional

from cron_doctor.models import Diagnosis, FixProposal, Severity


# --- Constants -------------------------------------------------------------

_PROMPT_MAX = 10000


# --- Sensitive pattern catalogue ------------------------------------------
#
# Order matters only for the "one issue per prompt" behaviour in :meth:`run`;
# we report the first match only, so patterns are listed in the order the
# reviewer should see them.

_SENSITIVE_PATTERNS = [
    # OpenAI / Anthropic / generic API keys (sk-/pk- prefix, 20+ body chars)
    (
        re.compile(r"\b(?:sk|pk)[-_][A-Za-z0-9]{20,}"),
        "API key (sk-/pk- prefix)",
    ),
    # AWS access key IDs
    (
        re.compile(r"\bAKIA[0-9A-Z]{16,}"),
        "AWS access key",
    ),
    # GitHub personal access tokens
    (
        re.compile(r"\bghp_[A-Za-z0-9]{20,}"),
        "GitHub personal access token",
    ),
    # Bearer tokens (Authorization: Bearer <token>)
    (
        re.compile(r"\bBearer\s+[A-Za-z0-9_-]{20,}"),
        "Bearer token",
    ),
    # Generic password / pwd assignment. ``(?P<val>...)`` is consumed by the
    # placeholder filter below.
    (
        re.compile(
            r"(?i)\b(?:password|pwd)\s*[=:]\s*"
            r"(?P<val>[^\s<>\"'`,;]{6,})"
        ),
        "literal password assignment",
    ),
]


# Placeholder values to exclude from the password match. Conservative: only
# obvious non-secret tokens are listed so legitimate real passwords still
# trip the rule.
_PLACEHOLDER_VALUES = {
    "CHANGEME", "CHANGEME!", "CHANGEME123",
    "XXX", "XXXX", "XXXXX",
    "***", "********",
    "your_password", "yourpassword", "mypassword", "my_password",
    "example", "EXAMPLE", "placeholder", "PLACEHOLDER",
    "test", "TEST", "1234", "12345", "123456",
    "secret", "SECRET", "fixme", "FIXME", "todo", "TODO",
    "<password>", "<PASSWORD>", "<your-password>",
}


# --- Check -----------------------------------------------------------------


class PromptCheck:
    """P001: prompt self-validation (length + sensitive info)."""

    check_id = "P001"
    name = "prompt"

    # --- run --------------------------------------------------------------

    def run(self, job, context) -> list:
        """Run the check on one job. See module docstring for the rules."""
        if not isinstance(context, dict):
            context = {}
        file = context.get("file", "<unknown>")
        issues: list = []

        if not isinstance(job, dict):
            return issues

        prompt = job.get("prompt")
        if prompt is None:
            return issues  # job uses script/command instead
        if not isinstance(prompt, str):
            # S001 already type-checks; be defensive and skip non-strings.
            return issues

        # Length rule
        if len(prompt) > _PROMPT_MAX:
            issues.append(Diagnosis(
                check_id=self.check_id,
                severity=Severity.WARNING,
                message=(
                    f"Prompt is {len(prompt)} chars (>{_PROMPT_MAX}) "
                    "- consider trimming"
                ),
                suggestion="Split into multiple jobs or summarize the prompt",
                file=file,
            ))

        # Sensitive patterns
        for pattern, label in _SENSITIVE_PATTERNS:
            match = pattern.search(prompt)
            if match is None:
                continue
            if "password" in label.lower():
                groups = match.groupdict()
                val = groups.get("val") if groups else match.group(0)
                if self._is_placeholder(val):
                    continue
            issues.append(Diagnosis(
                check_id=self.check_id,
                severity=Severity.ERROR,
                message=f"Possible secret in prompt: {label}",
                suggestion=(
                    "Remove the secret or move it to an env var "
                    "/ secrets manager"
                ),
                file=file,
            ))
            # Don't double-report: one issue per prompt is enough.
            break

        return issues

    # --- helpers -----------------------------------------------------------

    @staticmethod
    def _is_placeholder(value) -> bool:
        """Return True if ``value`` looks like a non-secret placeholder."""
        if not isinstance(value, str):
            return False
        if value in _PLACEHOLDER_VALUES:
            return True
        if value.startswith(("<", "$", "{{")):
            return True
        return False

    # --- propose_fix -------------------------------------------------------

    @staticmethod
    def propose_fix(diagnosis, original_line: str) -> Optional[FixProposal]:
        """Redact any matched secret pattern with ``[REDACTED]``.

        Returns ``None`` if no pattern matched (nothing to change).
        """
        new_line = original_line
        for pattern, _label in _SENSITIVE_PATTERNS:
            new_line = pattern.sub("[REDACTED]", new_line)

        if new_line == original_line:
            return None

        return FixProposal(
            file=(diagnosis.file if diagnosis is not None else None) or "<unknown>",
            line=(diagnosis.line if diagnosis is not None else None) or 0,
            check_id=(diagnosis.check_id if diagnosis is not None else None) or "P001",
            description="redact detected secret pattern",
            original=original_line,
            replacement=new_line,
        )
