"""Tests for cron_doctor.checks.P001_prompt — TDD.

P001 self-validates the `prompt` field of a cron job:
- Length: prompts over 10000 chars emit a WARNING.
- Sensitive info: regex-based detection of common secret patterns emits an
  ERROR. Conservative placeholders (CHANGEME, XXX, <template>, etc.) are
  excluded from the generic-password rule to avoid false positives.

RED: this file imports `PromptCheck`, which does not exist yet. The test must
fail before we write the implementation.
"""
from cron_doctor.checks.P001_prompt import PromptCheck
from cron_doctor.models import Diagnosis, Severity


def test_check_id_and_name():
    check = PromptCheck()
    assert check.check_id == "P001"
    assert check.name == "prompt"


# --- No issue ---

def test_no_prompt_key_no_issue():
    """Jobs can use script/command instead of prompt."""
    check = PromptCheck()
    issues = check.run({"name": "a", "schedule": "0 * * * *", "script": "echo"}, {"file": "f.yaml"})
    assert issues == []


def test_short_prompt_no_issue():
    check = PromptCheck()
    issues = check.run({"name": "a", "prompt": "Summarize the news today"}, {"file": "f.yaml"})
    assert issues == []


def test_prompt_exactly_10000_chars_no_warning():
    check = PromptCheck()
    issues = check.run({"name": "a", "prompt": "x" * 10000}, {"file": "f.yaml"})
    assert not any(i.severity == Severity.WARNING and "chars" in i.message for i in issues)


def test_non_string_prompt_no_crash():
    check = PromptCheck()
    issues = check.run({"name": "a", "prompt": 12345}, {"file": "f.yaml"})
    assert issues == []


def test_non_dict_job_no_crash():
    check = PromptCheck()
    issues = check.run("not a dict", {"file": "f.yaml"})
    assert issues == []


# --- Length warning ---

def test_very_long_prompt_warns():
    check = PromptCheck()
    issues = check.run({"name": "a", "prompt": "x" * 10001}, {"file": "f.yaml"})
    assert any(i.severity == Severity.WARNING and "10001" in i.message for i in issues)


# --- Sensitive info detection ---

def test_openai_key_detected():
    check = PromptCheck()
    issues = check.run({"name": "a", "prompt": "Use this key sk-abcdefghijklmnopqrstuvwxyz"}, {"file": "f.yaml"})
    assert any(i.severity == Severity.ERROR and "sk-" in i.message for i in issues)


def test_aws_key_detected():
    check = PromptCheck()
    issues = check.run({"name": "a", "prompt": "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE"}, {"file": "f.yaml"})
    assert any(i.severity == Severity.ERROR and "AWS" in i.message for i in issues)


def test_github_pat_detected():
    check = PromptCheck()
    issues = check.run({"name": "a", "prompt": "token: ghp_abcdefghijklmnopqrstuvwxyz1234567890"}, {"file": "f.yaml"})
    assert any(i.severity == Severity.ERROR and "GitHub" in i.message for i in issues)


def test_bearer_token_detected():
    check = PromptCheck()
    issues = check.run({"name": "a", "prompt": "Authorization: Bearer abcdefghijklmnopqrstuvwxyz1234567890"}, {"file": "f.yaml"})
    assert any(i.severity == Severity.ERROR and "Bearer" in i.message for i in issues)


def test_password_with_real_value_detected():
    check = PromptCheck()
    issues = check.run({"name": "a", "prompt": "Login with password=hunter2hunter2"}, {"file": "f.yaml"})
    assert any(i.severity == Severity.ERROR and "password" in i.message.lower() for i in issues)


# --- False positive avoidance ---

def test_password_placeholder_changeme_no_fp():
    check = PromptCheck()
    issues = check.run({"name": "a", "prompt": "Set password=CHANGEME in config"}, {"file": "f.yaml"})
    assert not any(i.severity == Severity.ERROR and "password" in i.message.lower() for i in issues)


def test_password_placeholder_xxx_no_fp():
    check = PromptCheck()
    issues = check.run({"name": "a", "prompt": "Set password=XXXXX here"}, {"file": "f.yaml"})
    assert not any(i.severity == Severity.ERROR and "password" in i.message.lower() for i in issues)


def test_password_placeholder_template_no_fp():
    check = PromptCheck()
    issues = check.run({"name": "a", "prompt": "Set password=<your-password> here"}, {"file": "f.yaml"})
    assert not any(i.severity == Severity.ERROR and "password" in i.message.lower() for i in issues)


def test_short_sk_prefix_no_fp():
    """A short 'sk-' followed by <20 chars is not a real key."""
    check = PromptCheck()
    issues = check.run({"name": "a", "prompt": "Use sk-shortkey or similar"}, {"file": "f.yaml"})
    assert not any(i.severity == Severity.ERROR and "sk-" in i.message for i in issues)


# --- propose_fix ---

def test_propose_fix_redacts_secret():
    check = PromptCheck()
    diag = Diagnosis(
        check_id="P001",
        severity=Severity.ERROR,
        message="Possible secret",
        file="f.yaml",
        line=2,
    )
    original = '  prompt: "Use sk-abcdefghijklmnopqrstuvwxyz here"'
    proposal = check.propose_fix(diag, original)
    assert proposal is not None
    assert "[REDACTED]" in proposal.replacement
    assert "sk-abcdef" not in proposal.replacement or "[REDACTED]" in proposal.replacement
