"""Tests for cron_doctor.checks.M001_mcp — TDD.

M001: enabled_toolsets reference integrity + toolsets registry check.

A job's `enabled_toolsets` list must reference names defined in the
top-level `toolsets:` registry. M001 emits:
- ERROR for each unknown reference
- WARNING when a job uses enabled_toolsets but no registry is present
- WARNING at file level for duplicate toolset names in the registry
"""
from cron_doctor.checks.M001_mcp import MCPCheck
from cron_doctor.models import Diagnosis, Severity


def test_check_id_and_name():
    check = MCPCheck()
    assert check.check_id == "M001"
    assert check.name == "mcp"


# --- Per-job broken references ---


def test_no_enabled_toolsets_no_issue():
    check = MCPCheck()
    issues = check.run({"name": "a"}, {"file": "f.yaml", "document_toolsets": {"search"}})
    assert issues == []


def test_valid_reference_no_issue():
    check = MCPCheck()
    issues = check.run(
        {"name": "a", "enabled_toolsets": ["search", "code"]},
        {"file": "f.yaml", "document_toolsets": {"search", "code"}},
    )
    assert issues == []


def test_broken_reference_emits_error():
    check = MCPCheck()
    issues = check.run(
        {"name": "a", "enabled_toolsets": ["nonexistent"]},
        {"file": "f.yaml", "document_toolsets": {"search"}},
    )
    assert len(issues) == 1
    assert issues[0].check_id == "M001"
    assert issues[0].severity == Severity.ERROR
    assert "nonexistent" in issues[0].message


def test_multiple_broken_refs():
    check = MCPCheck()
    issues = check.run(
        {"name": "a", "enabled_toolsets": ["x", "y", "z"]},
        {"file": "f.yaml", "document_toolsets": {"search"}},
    )
    assert len(issues) == 3


def test_partial_broken_refs():
    check = MCPCheck()
    issues = check.run(
        {"name": "a", "enabled_toolsets": ["search", "missing"]},
        {"file": "f.yaml", "document_toolsets": {"search", "code"}},
    )
    assert len(issues) == 1
    assert "missing" in issues[0].message


# --- Registry absent ---


def test_enabled_toolsets_but_no_registry_warns():
    """If job uses enabled_toolsets but document has no `toolsets:` block, warn."""
    check = MCPCheck()
    issues = check.run(
        {"name": "a", "enabled_toolsets": ["search"]},
        {"file": "f.yaml", "document_toolsets": None},
    )
    assert len(issues) == 1
    assert issues[0].severity == Severity.WARNING
    assert "toolsets" in issues[0].message.lower() or "registry" in issues[0].message.lower()


def test_empty_registry_warns():
    """If document has `toolsets: []` (empty), warn that ref cannot be resolved."""
    check = MCPCheck()
    issues = check.run(
        {"name": "a", "enabled_toolsets": ["search"]},
        {"file": "f.yaml", "document_toolsets": set()},
    )
    assert len(issues) == 1
    assert issues[0].severity == Severity.WARNING


# --- Defensive ---


def test_non_list_enabled_toolsets_no_crash():
    check = MCPCheck()
    issues = check.run(
        {"name": "a", "enabled_toolsets": "search"},
        {"file": "f.yaml", "document_toolsets": {"search"}},
    )
    assert issues == []  # S001 catches type


def test_non_string_ref_no_crash():
    check = MCPCheck()
    issues = check.run(
        {"name": "a", "enabled_toolsets": ["search", 123]},
        {"file": "f.yaml", "document_toolsets": {"search"}},
    )
    assert issues == []  # 123 is not str, skip silently


def test_non_dict_job_no_crash():
    check = MCPCheck()
    issues = check.run("not a dict", {"file": "f.yaml", "document_toolsets": {"search"}})
    assert issues == []


# --- propose_fix ---


def test_propose_fix_comments_out_broken_ref():
    check = MCPCheck()
    diag = Diagnosis(
        check_id="M001",
        severity=Severity.ERROR,
        message="references unknown toolset 'nonexistent'",
        file="f.yaml",
        line=5,
    )
    original = "    enabled_toolsets: [search, nonexistent]"
    proposal = check.propose_fix(diag, original)
    assert proposal is not None
    assert "nonexistent" in original
    # The fix should comment out the broken ref (keep the valid ones)
    assert "search" in proposal.replacement


# --- Integration with diagnose (file-level) ---


def test_diagnose_extracts_toolsets_registry(tmp_path):
    """core.diagnose() should populate context['document_toolsets'] from the doc."""
    from cron_doctor.core import diagnose
    f = tmp_path / "mcp.yaml"
    f.write_text(
        "toolsets:\n"
        "  - name: search\n"
        "    description: Web search\n"
        "  - name: code\n"
        "    description: Code execution\n"
        "jobs:\n"
        "  - name: a\n"
        "    schedule: '0 * * * *'\n"
        "    prompt: x\n"
        "    enabled_toolsets: [search, broken]\n"
    )
    results = diagnose(f)
    m001_errors = [i for i in results[0].issues if i.check_id == "M001" and i.severity == Severity.ERROR]
    assert len(m001_errors) == 1
    assert "broken" in m001_errors[0].message


def test_diagnose_warns_on_duplicate_toolsets(tmp_path):
    """Document with duplicate toolset names → M001 WARNING at file level."""
    from cron_doctor.core import diagnose
    f = tmp_path / "dup.yaml"
    f.write_text(
        "toolsets:\n"
        "  - name: search\n"
        "  - name: search\n"
        "jobs:\n"
        "  - name: a\n"
        "    schedule: '0 * * * *'\n"
        "    prompt: x\n"
        "    enabled_toolsets: [search]\n"
    )
    results = diagnose(f)
    dup_warnings = [i for i in results[0].issues if i.check_id == "M001" and "duplicate" in i.message.lower()]
    assert len(dup_warnings) >= 1
