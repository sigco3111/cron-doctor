"""Tests for cron_doctor.checks.S001_schema — TDD."""
from cron_doctor.checks.S001_schema import SchemaCheck
from cron_doctor.models import Diagnosis, Severity


def test_check_id_and_name():
    check = SchemaCheck()
    assert check.check_id == "S001"
    assert check.name == "schema"


# --- Happy path ---

def test_valid_minimal_job():
    check = SchemaCheck()
    job = {"name": "a", "schedule": "0 * * * *", "prompt": "do thing"}
    issues = check.run(job, {"file": "f.yaml"})
    assert issues == []


def test_valid_with_all_optional_keys():
    check = SchemaCheck()
    job = {
        "name": "a", "schedule": "0 * * * *", "prompt": "x",
        "timezone": "UTC", "context_from": ["b"], "enabled_toolsets": ["search"],
        "workdir": "/tmp", "skills": ["python"], "model": "haiku",
        "deliver": "json", "repeat": 3, "no_agent": False, "profile": "default",
        "env": {"KEY": "val"},
    }
    issues = check.run(job, {"file": "f.yaml"})
    assert issues == []


def test_valid_with_command_instead_of_prompt():
    check = SchemaCheck()
    job = {"name": "a", "schedule": "0 * * * *", "command": "rm -rf /"}
    issues = check.run(job, {"file": "f.yaml"})
    assert issues == []


def test_valid_with_script_instead_of_prompt():
    check = SchemaCheck()
    job = {"name": "a", "schedule": "0 * * * *", "script": "echo hi"}
    issues = check.run(job, {"file": "f.yaml"})
    assert issues == []


# --- Missing required ---

def test_missing_name_errors():
    check = SchemaCheck()
    job = {"schedule": "0 * * * *", "prompt": "x"}
    issues = check.run(job, {"file": "f.yaml"})
    assert any(i.severity == Severity.ERROR and "name" in i.message for i in issues)


def test_missing_schedule_errors():
    check = SchemaCheck()
    job = {"name": "a", "prompt": "x"}
    issues = check.run(job, {"file": "f.yaml"})
    assert any(i.severity == Severity.ERROR and "schedule" in i.message for i in issues)


def test_missing_prompt_script_command_errors():
    check = SchemaCheck()
    job = {"name": "a", "schedule": "0 * * * *"}
    issues = check.run(job, {"file": "f.yaml"})
    assert any(i.severity == Severity.ERROR and ("prompt" in i.message or "command" in i.message or "script" in i.message) for i in issues)


# --- Type errors ---

def test_name_not_string_errors():
    check = SchemaCheck()
    job = {"name": 123, "schedule": "0 * * * *", "prompt": "x"}
    issues = check.run(job, {"file": "f.yaml"})
    assert any(i.severity == Severity.ERROR and "name" in i.message for i in issues)


def test_schedule_not_string_errors():
    check = SchemaCheck()
    job = {"name": "a", "schedule": 42, "prompt": "x"}
    issues = check.run(job, {"file": "f.yaml"})
    assert any(i.severity == Severity.ERROR and "schedule" in i.message for i in issues)


def test_context_from_not_list_errors():
    check = SchemaCheck()
    job = {"name": "a", "schedule": "0 * * * *", "prompt": "x", "context_from": "b"}
    issues = check.run(job, {"file": "f.yaml"})
    assert any(i.severity == Severity.ERROR and "context_from" in i.message for i in issues)


def test_repeat_not_int_errors():
    check = SchemaCheck()
    job = {"name": "a", "schedule": "0 * * * *", "prompt": "x", "repeat": "5"}
    issues = check.run(job, {"file": "f.yaml"})
    assert any(i.severity == Severity.ERROR and "repeat" in i.message for i in issues)


# --- Unknown keys (WARNING) ---

def test_unknown_key_warns():
    check = SchemaCheck()
    job = {"name": "a", "schedule": "0 * * * *", "prompt": "x", "totally_made_up": True}
    issues = check.run(job, {"file": "f.yaml"})
    assert any(i.severity == Severity.WARNING and "totally_made_up" in i.message for i in issues)


# --- Optional type checks (WARNING) ---

def test_timezone_not_string_warns():
    check = SchemaCheck()
    job = {"name": "a", "schedule": "0 * * * *", "prompt": "x", "timezone": 123}
    issues = check.run(job, {"file": "f.yaml"})
    assert any(i.severity == Severity.WARNING and "timezone" in i.message for i in issues)


# --- Non-dict job ---

def test_non_dict_job_errors():
    check = SchemaCheck()
    issues = check.run("not a dict", {"file": "f.yaml"})
    assert any(i.severity == Severity.ERROR for i in issues)


def test_repeat_bool_is_invalid():
    # bool is a subclass of int; ensure booleans are rejected for repeat
    check = SchemaCheck()
    job = {"name": "a", "schedule": "0 * * * *", "prompt": "x", "repeat": True}
    issues = check.run(job, {"file": "f.yaml"})
    assert any(i.severity == Severity.ERROR and "repeat" in i.message for i in issues)
