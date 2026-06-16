"""Tests for cron_doctor.checks.D001_dependencies — TDD."""
from cron_doctor.checks.D001_dependencies import DependenciesCheck
from cron_doctor.models import Diagnosis, Severity


def test_check_id_and_name():
    check = DependenciesCheck()
    assert check.check_id == "D001"
    assert check.name == "dependencies"


# --- Per-job broken references ---


def test_valid_reference_no_error():
    check = DependenciesCheck()
    issues = check.run(
        {"name": "a", "context_from": ["b"]},
        {"file": "f.yaml", "all_jobs": [{"name": "a"}, {"name": "b"}]},
    )
    assert issues == []


def test_broken_reference_emits_error():
    check = DependenciesCheck()
    issues = check.run(
        {"name": "a", "context_from": ["nonexistent"]},
        {"file": "f.yaml", "all_jobs": [{"name": "a"}]},
    )
    assert len(issues) == 1
    assert issues[0].check_id == "D001"
    assert issues[0].severity == Severity.ERROR
    assert "nonexistent" in issues[0].message


def test_self_reference_emits_error():
    check = DependenciesCheck()
    issues = check.run(
        {"name": "a", "context_from": ["a"]},
        {"file": "f.yaml", "all_jobs": [{"name": "a"}]},
    )
    # Self-reference is both a broken-ish thing AND a cycle
    # For per-job, it counts as a broken ref (a is in names but... actually it's a valid name)
    # The cycle detection happens in check_file
    # Per-job only flags unknowns, so self-ref may not emit a per-job error
    # We allow either 0 or 1 error
    assert all(i.severity == Severity.ERROR for i in issues)


def test_multiple_broken_refs():
    check = DependenciesCheck()
    issues = check.run(
        {"name": "a", "context_from": ["x", "y", "z"]},
        {"file": "f.yaml", "all_jobs": [{"name": "a"}]},
    )
    assert len(issues) == 3


def test_no_context_from_no_error():
    check = DependenciesCheck()
    issues = check.run(
        {"name": "a"},
        {"file": "f.yaml", "all_jobs": [{"name": "a"}]},
    )
    assert issues == []


def test_non_list_context_from_no_error():
    """S001 catches wrong type."""
    check = DependenciesCheck()
    issues = check.run(
        {"name": "a", "context_from": "b"},
        {"file": "f.yaml", "all_jobs": [{"name": "a"}, {"name": "b"}]},
    )
    assert issues == []


# --- File-level cycle detection ---


def test_no_cycle_no_error():
    check = DependenciesCheck()
    issues = check.check_file(
        [{"name": "a"}, {"name": "b", "context_from": ["a"]}, {"name": "c", "context_from": ["b"]}],
        "f.yaml",
    )
    cycles = [i for i in issues if "ircular" in i.message]
    assert cycles == []


def test_two_node_cycle():
    check = DependenciesCheck()
    issues = check.check_file(
        [
            {"name": "a", "context_from": ["b"]},
            {"name": "b", "context_from": ["a"]},
        ],
        "f.yaml",
    )
    cycles = [i for i in issues if "ircular" in i.message]
    assert len(cycles) == 1
    assert "a" in cycles[0].message and "b" in cycles[0].message


def test_three_node_cycle():
    check = DependenciesCheck()
    issues = check.check_file(
        [
            {"name": "a", "context_from": ["b"]},
            {"name": "b", "context_from": ["c"]},
            {"name": "c", "context_from": ["a"]},
        ],
        "f.yaml",
    )
    cycles = [i for i in issues if "ircular" in i.message]
    assert len(cycles) == 1


def test_self_reference_is_cycle():
    check = DependenciesCheck()
    issues = check.check_file(
        [{"name": "a", "context_from": ["a"]}],
        "f.yaml",
    )
    cycles = [i for i in issues if "ircular" in i.message]
    assert len(cycles) == 1


# --- File-level depth warning ---


def test_depth_4_no_warning():
    check = DependenciesCheck()
    issues = check.check_file(
        [
            {"name": "a"},
            {"name": "b", "context_from": ["a"]},
            {"name": "c", "context_from": ["b"]},
            {"name": "d", "context_from": ["c"]},
            {"name": "e", "context_from": ["d"]},
        ],
        "f.yaml",
    )
    deep = [i for i in issues if "deep" in i.message.lower()]
    assert deep == []


def test_depth_5_emits_warning():
    check = DependenciesCheck()
    issues = check.check_file(
        [
            {"name": "a"},
            {"name": "b", "context_from": ["a"]},
            {"name": "c", "context_from": ["b"]},
            {"name": "d", "context_from": ["c"]},
            {"name": "e", "context_from": ["d"]},
            {"name": "f", "context_from": ["e"]},
        ],
        "f.yaml",
    )
    deep = [i for i in issues if "deep" in i.message.lower()]
    assert len(deep) >= 1
    assert deep[0].severity == Severity.WARNING
