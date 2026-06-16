"""RED tests for cron_doctor.models — must FAIL until models.py is implemented."""
import pytest
from cron_doctor.models import (
    Severity,
    Diagnosis,
    CheckResult,
    BaseCheck,
)


def test_severity_is_str_enum():
    assert Severity.INFO == "info"
    assert Severity.WARNING == "warning"
    assert Severity.ERROR == "error"
    assert isinstance(Severity.INFO, str)
    assert isinstance(Severity.INFO, Severity)


def test_severity_members():
    assert {s.value for s in Severity} == {"info", "warning", "error"}


def test_diagnosis_creation_minimal():
    d = Diagnosis(check_id="C001", severity=Severity.ERROR, message="bad cron")
    assert d.check_id == "C001"
    assert d.severity == Severity.ERROR
    assert d.message == "bad cron"
    assert d.suggestion is None
    assert d.file is None
    assert d.line is None


def test_diagnosis_creation_full():
    d = Diagnosis(
        check_id="Y001",
        severity=Severity.WARNING,
        message="unknown key",
        suggestion="remove the key",
        file="cron.yaml",
        line=5,
    )
    assert d.suggestion == "remove the key"
    assert d.file == "cron.yaml"
    assert d.line == 5


def test_diagnosis_is_frozen():
    d = Diagnosis(check_id="C001", severity=Severity.ERROR, message="x")
    with pytest.raises(Exception):
        d.message = "new"


def test_diagnosis_is_hashable():
    d1 = Diagnosis(check_id="C001", severity=Severity.ERROR, message="x")
    d2 = Diagnosis(check_id="C001", severity=Severity.ERROR, message="x")
    assert hash(d1) == hash(d2)
    assert d1 == d2
    assert {d1, d2} == {d1}


def test_check_result_defaults():
    r = CheckResult(file="x.yaml", jobs=[{"name": "a"}])
    assert r.file == "x.yaml"
    assert r.jobs == [{"name": "a"}]
    assert r.issues == []


def test_check_result_has_errors_true():
    r = CheckResult(
        file="x.yaml",
        jobs=[],
        issues=[Diagnosis(check_id="C001", severity=Severity.ERROR, message="e")],
    )
    assert r.has_errors is True
    assert r.has_warnings is False


def test_check_result_has_warnings_true():
    r = CheckResult(
        file="x.yaml",
        jobs=[],
        issues=[Diagnosis(check_id="C002", severity=Severity.WARNING, message="w")],
    )
    assert r.has_errors is False
    assert r.has_warnings is True


def test_check_result_no_issues():
    r = CheckResult(file="x.yaml", jobs=[])
    assert r.has_errors is False
    assert r.has_warnings is False


def test_base_check_is_protocol():
    class MyCheck:
        check_id = "X001"
        name = "X"
        def run(self, job, context):
            return []

    assert isinstance(MyCheck(), BaseCheck)


def test_base_check_non_conforming_not_instance():
    class NotA:
        pass
    assert not isinstance(NotA(), BaseCheck)
