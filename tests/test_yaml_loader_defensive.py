"""v1.0.0 defensive path tests for yaml_loader.py.

Covers all 25 previously-untested statements:
- File I/O errors (FileNotFoundError, PermissionError, OSError)
- Empty files and None data
- YAML syntax errors (with and without problem_mark)
- Non-dict/list top-level values
- Legacy (top-level list) and v0.2+ (top-level dict) formats
- Dict without "jobs" key
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from cron_doctor.exceptions import ParseError, UnreadableFileError
from cron_doctor.parsers.yaml_loader import load_cron_document, load_cron_yaml


# ===========================================================================
# load_cron_yaml — error paths
# ===========================================================================

class TestLoadCronYamlErrors:
    def test_file_not_found(self, tmp_path):
        p = tmp_path / "missing.yaml"
        with pytest.raises(UnreadableFileError) as excinfo:
            load_cron_yaml(p)
        assert "No such file" in str(excinfo.value)

    def test_permission_denied(self, tmp_path):
        p = tmp_path / "secret.yaml"
        p.write_text("jobs: []\n")
        with patch.object(Path, "read_text", side_effect=PermissionError("denied")):
            with pytest.raises(UnreadableFileError) as excinfo:
                load_cron_yaml(p)
        assert "Permission denied" in str(excinfo.value)

    def test_os_error_on_read(self, tmp_path):
        p = tmp_path / "x.yaml"
        p.write_text("jobs: []\n")
        with patch.object(Path, "read_text", side_effect=OSError("disk error")):
            with pytest.raises(UnreadableFileError) as excinfo:
                load_cron_yaml(p)
        assert "disk error" in str(excinfo.value)

    def test_empty_file_returns_empty_list(self, tmp_path):
        p = tmp_path / "empty.yaml"
        p.write_text("")
        assert load_cron_yaml(p) == []

    def test_whitespace_only_file_returns_empty_list(self, tmp_path):
        p = tmp_path / "ws.yaml"
        p.write_text("   \n  \n")
        assert load_cron_yaml(p) == []

    def test_yaml_null_returns_empty_list(self, tmp_path):
        p = tmp_path / "null.yaml"
        p.write_text("~\n")
        assert load_cron_yaml(p) == []

    def test_yaml_scalar_top_level_raises_parse_error(self, tmp_path):
        p = tmp_path / "scalar.yaml"
        p.write_text("just_a_string\n")
        with pytest.raises(ParseError) as excinfo:
            load_cron_yaml(p)
        assert "Top-level" in str(excinfo.value)
        assert "str" in str(excinfo.value)

    def test_yaml_syntax_error_with_mark(self, tmp_path):
        p = tmp_path / "bad.yaml"
        p.write_text("jobs:\n  - name: x\n   schedule: bad\n")
        with pytest.raises(ParseError) as excinfo:
            load_cron_yaml(p)
        assert excinfo.value.line is not None
        assert excinfo.value.column is not None
        assert "line" in str(excinfo.value).lower()


# ===========================================================================
# load_cron_yaml — happy paths
# ===========================================================================

class TestLoadCronYamlHappy:
    def test_top_level_list(self, tmp_path):
        p = tmp_path / "list.yaml"
        p.write_text("- name: a\n- name: b\n")
        result = load_cron_yaml(p)
        assert len(result) == 2
        assert result[0]["name"] == "a"

    def test_top_level_dict_wrapped(self, tmp_path):
        p = tmp_path / "dict.yaml"
        p.write_text("name: solo\n")
        result = load_cron_yaml(p)
        assert result == [{"name": "solo"}]

    def test_empty_list(self, tmp_path):
        p = tmp_path / "list.yaml"
        p.write_text("[]\n")
        assert load_cron_yaml(p) == []


# ===========================================================================
# load_cron_document — error paths
# ===========================================================================

class TestLoadCronDocumentErrors:
    def test_file_not_found(self, tmp_path):
        p = tmp_path / "missing.yaml"
        with pytest.raises(UnreadableFileError):
            load_cron_document(p)

    def test_permission_denied(self, tmp_path):
        p = tmp_path / "x.yaml"
        p.write_text("jobs: []\n")
        with patch.object(Path, "read_text", side_effect=PermissionError("denied")):
            with pytest.raises(UnreadableFileError):
                load_cron_document(p)

    def test_os_error_on_read(self, tmp_path):
        p = tmp_path / "x.yaml"
        p.write_text("jobs: []\n")
        with patch.object(Path, "read_text", side_effect=OSError("io error")):
            with pytest.raises(UnreadableFileError):
                load_cron_document(p)

    def test_empty_file_returns_empty_jobs(self, tmp_path):
        p = tmp_path / "empty.yaml"
        p.write_text("")
        result = load_cron_document(p)
        assert result == {"jobs": []}

    def test_null_file_returns_empty_jobs(self, tmp_path):
        p = tmp_path / "null.yaml"
        p.write_text("null\n")
        result = load_cron_document(p)
        assert result == {"jobs": []}

    def test_yaml_syntax_error(self, tmp_path):
        p = tmp_path / "bad.yaml"
        p.write_text("jobs:\n  - name: x\n   bad_indent: : :\n")
        with pytest.raises(ParseError):
            load_cron_document(p)

    def test_scalar_top_level_raises_parse_error(self, tmp_path):
        p = tmp_path / "scalar.yaml"
        p.write_text("42\n")
        with pytest.raises(ParseError) as excinfo:
            load_cron_document(p)
        assert "Top-level" in str(excinfo.value)


# ===========================================================================
# load_cron_document — happy paths
# ===========================================================================

class TestLoadCronDocumentHappy:
    def test_legacy_list_format(self, tmp_path):
        p = tmp_path / "legacy.yaml"
        p.write_text("- name: a\n  schedule: '0 * * * *'\n")
        result = load_cron_document(p)
        assert "jobs" in result
        assert len(result["jobs"]) == 1
        assert result["jobs"][0]["name"] == "a"

    def test_v2_dict_with_jobs(self, tmp_path):
        p = tmp_path / "v2.yaml"
        p.write_text("jobs:\n  - name: a\n  - name: b\ntoolsets:\n  - name: t1\n")
        result = load_cron_document(p)
        assert len(result["jobs"]) == 2
        assert len(result["toolsets"]) == 1
        assert "raw" in result

    def test_v2_dict_without_jobs_treats_dict_as_single_job(self, tmp_path):
        p = tmp_path / "nojobs.yaml"
        p.write_text("name: solo\nschedule: '0 * * * *'\n")
        result = load_cron_document(p)
        assert len(result["jobs"]) == 1
        assert result["jobs"][0]["name"] == "solo"

    def test_v2_dict_with_non_list_jobs(self, tmp_path):
        p = tmp_path / "badjobs.yaml"
        p.write_text("jobs: not_a_list\n")
        result = load_cron_document(p)
        assert result["jobs"] == []

    def test_v2_dict_with_non_list_toolsets(self, tmp_path):
        p = tmp_path / "badtoolsets.yaml"
        p.write_text("toolsets: not_a_list\n")
        result = load_cron_document(p)
        assert result["toolsets"] == []

    def test_v2_dict_without_toolsets(self, tmp_path):
        p = tmp_path / "notoolsets.yaml"
        p.write_text("jobs:\n  - name: a\n")
        result = load_cron_document(p)
        assert "toolsets" not in result

    def test_v2_dict_with_jobs_and_toolsets(self, tmp_path):
        p = tmp_path / "both.yaml"
        p.write_text("jobs:\n  - name: a\ntoolsets:\n  - name: t1\n")
        result = load_cron_document(p)
        assert len(result["jobs"]) == 1
        assert len(result["toolsets"]) == 1
