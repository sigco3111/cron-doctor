"""Tests for cron_doctor.core.propose_fixes / apply_fixes / fix — TDD."""
import textwrap

import pytest

from cron_doctor.core import apply_fixes, fix, propose_fixes
from cron_doctor.models import FixProposal


# --- propose_fixes ---

def test_propose_fixes_on_valid_file_empty(tmp_path):
    f = tmp_path / "ok.yaml"
    f.write_text("- name: a\n  schedule: '0 9 * * MON-FRI'\n  prompt: x\n")
    proposals = propose_fixes(f)
    assert proposals == []


def test_propose_fixes_on_t001_broken_file(tmp_path):
    f = tmp_path / "bad.yaml"
    f.write_text(textwrap.dedent("""\
        - name: a
          schedule: '0 * * * *'
          prompt: x
          timezone: Foo/Bar
    """))
    proposals = propose_fixes(f)
    assert len(proposals) == 1
    assert proposals[0].check_id == "T001"
    assert "UTC" in proposals[0].replacement
    assert "Foo/Bar" in proposals[0].original


def test_propose_fixes_on_p001_broken_file(tmp_path):
    f = tmp_path / "secret.yaml"
    f.write_text(textwrap.dedent("""\
        - name: a
          schedule: '0 * * * *'
          prompt: "Use this key sk-abcdefghijklmnopqrstuvwxyz"
    """))
    proposals = propose_fixes(f)
    p001_proposals = [p for p in proposals if p.check_id == "P001"]
    assert len(p001_proposals) >= 1
    assert "[REDACTED]" in p001_proposals[0].replacement


def test_propose_fixes_on_m001_broken_file(tmp_path):
    f = tmp_path / "mcp.yaml"
    f.write_text(textwrap.dedent("""\
        toolsets:
          - name: search
            description: Web search
        jobs:
          - name: a
            schedule: '0 * * * *'
            prompt: x
            enabled_toolsets: [search, nonexistent]
    """))
    proposals = propose_fixes(f)
    m001_proposals = [p for p in proposals if p.check_id == "M001"]
    assert len(m001_proposals) >= 1
    assert "nonexistent" in m001_proposals[0].original


def test_propose_fixes_on_c001_broken_file_no_proposals(tmp_path):
    """C001 (invalid cron) has no auto-fix — should yield 0 proposals."""
    f = tmp_path / "badcron.yaml"
    f.write_text("- name: a\n  schedule: '60 * * * *'\n  prompt: x\n")
    proposals = propose_fixes(f)
    c001_proposals = [p for p in proposals if p.check_id == "C001"]
    assert c001_proposals == []


def test_propose_fixes_on_s001_unknown_key(tmp_path):
    f = tmp_path / "unknown.yaml"
    f.write_text(textwrap.dedent("""\
        - name: a
          schedule: '0 * * * *'
          prompt: x
          totally_made_up: true
    """))
    proposals = propose_fixes(f)
    s001 = [p for p in proposals if p.check_id == "S001"]
    assert len(s001) >= 1
    assert "totally_made_up" in s001[0].original
    # The fix should comment out the unknown key
    assert s001[0].replacement.strip().startswith("#")


# --- apply_fixes ---

def test_apply_fixes_writes_changes(tmp_path):
    f = tmp_path / "bad.yaml"
    f.write_text(textwrap.dedent("""\
        - name: a
          schedule: '0 * * * *'
          prompt: x
          timezone: Foo/Bar
    """))
    proposals = propose_fixes(f)
    assert len(proposals) >= 1
    applied = apply_fixes(f, proposals)
    assert applied >= 1
    new_text = f.read_text()
    assert "UTC" in new_text
    assert "Foo/Bar" not in new_text


def test_apply_fixes_is_idempotent(tmp_path):
    """After applying once, running propose_fixes again should return 0 (or fewer) proposals."""
    f = tmp_path / "bad.yaml"
    f.write_text(textwrap.dedent("""\
        - name: a
          schedule: '0 * * * *'
          prompt: x
          timezone: Foo/Bar
    """))
    proposals1 = propose_fixes(f)
    apply_fixes(f, proposals1)
    proposals2 = propose_fixes(f)
    assert len(proposals2) == 0  # file is now clean


def test_apply_fixes_empty_proposals_noop(tmp_path):
    f = tmp_path / "ok.yaml"
    f.write_text("- name: a\n  schedule: '0 * * * *'\n  prompt: x\n")
    original = f.read_text()
    applied = apply_fixes(f, [])
    assert applied == 0
    assert f.read_text() == original


def test_apply_fixes_nonexistent_file():
    applied = apply_fixes("/nonexistent/path.yaml", [])
    assert applied == 0


# --- fix (high-level API) ---

def test_fix_dry_run_does_not_modify(tmp_path):
    f = tmp_path / "bad.yaml"
    f.write_text(textwrap.dedent("""\
        - name: a
          schedule: '0 * * * *'
          prompt: x
          timezone: Foo/Bar
    """))
    original = f.read_text()
    result = fix(f, dry_run=True)
    assert result["applied"] == 0
    assert result["would_apply"] >= 1
    assert len(result["proposals"]) >= 1
    assert f.read_text() == original  # file unchanged


def test_fix_apply_modifies_file(tmp_path):
    f = tmp_path / "bad.yaml"
    f.write_text(textwrap.dedent("""\
        - name: a
          schedule: '0 * * * *'
          prompt: x
          timezone: Foo/Bar
    """))
    result = fix(f, dry_run=False)
    assert result["applied"] >= 1
    assert "UTC" in f.read_text()


def test_fix_default_is_dry_run(tmp_path):
    """Default behavior must be safe (no modification)."""
    f = tmp_path / "bad.yaml"
    f.write_text("- name: a\n  schedule: '0 * * * *'\n  prompt: x\n  timezone: Foo/Bar\n")
    original = f.read_text()
    result = fix(f)  # no dry_run arg
    assert result["applied"] == 0
    assert f.read_text() == original


def test_fix_returns_proposals_list(tmp_path):
    f = tmp_path / "ok.yaml"
    f.write_text("- name: a\n  schedule: '0 * * * *'\n  prompt: x\n")
    result = fix(f, dry_run=True)
    assert "proposals" in result
    assert "applied" in result
    assert "would_apply" in result
    assert result["proposals"] == []
    assert result["would_apply"] == 0


def test_fix_on_directory_recurses(tmp_path):
    d = tmp_path / "jobs"
    d.mkdir()
    (d / "ok.yaml").write_text("- name: a\n  schedule: '0 * * * *'\n  prompt: x\n")
    (d / "bad.yaml").write_text("- name: b\n  schedule: '0 * * * *'\n  prompt: x\n  timezone: Foo/Bar\n")
    result = fix(d, dry_run=True)
    assert result["would_apply"] >= 1
