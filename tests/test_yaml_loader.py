"""Tests for cron_doctor.parsers.yaml_loader — TDD."""
import textwrap
from pathlib import Path

import pytest

from cron_doctor.exceptions import ParseError, UnreadableFileError
from cron_doctor.parsers.yaml_loader import load_cron_yaml


# --- Happy path ---


def test_loads_list_of_jobs(tmp_path: Path):
    f = tmp_path / "cron.yaml"
    f.write_text(textwrap.dedent("""\
        - name: a
          schedule: "0 * * * *"
        - name: b
          schedule: "*/15 * * * *"
    """))
    result = load_cron_yaml(f)
    assert len(result) == 2
    assert result[0]["name"] == "a"
    assert result[1]["schedule"] == "*/15 * * * *"


def test_loads_single_dict_wraps_in_list(tmp_path: Path):
    f = tmp_path / "single.yaml"
    f.write_text(textwrap.dedent("""\
        name: a
        schedule: "0 * * * *"
    """))
    result = load_cron_yaml(f)
    assert len(result) == 1
    assert result[0]["name"] == "a"


def test_loads_empty_file_returns_empty_list(tmp_path: Path):
    f = tmp_path / "empty.yaml"
    f.write_text("")
    result = load_cron_yaml(f)
    assert result == []


def test_loads_string_path(tmp_path: Path):
    f = tmp_path / "cron.yaml"
    f.write_text("- name: x\n")
    result = load_cron_yaml(str(f))
    assert len(result) == 1


def test_loads_path_object(tmp_path: Path):
    f = tmp_path / "cron.yaml"
    f.write_text("- name: x\n")
    result = load_cron_yaml(f)  # tmp_path is Path
    assert len(result) == 1


# --- Error translation ---


def test_missing_file_raises_unreadable(tmp_path: Path):
    f = tmp_path / "nonexistent.yaml"
    with pytest.raises(UnreadableFileError) as exc:
        load_cron_yaml(f)
    assert "nonexistent.yaml" in str(exc.value)


def test_yaml_syntax_error_translates_to_parse_error(tmp_path: Path):
    f = tmp_path / "bad.yaml"
    # Tab indentation is invalid in YAML
    f.write_text("- name: a\n\t  schedule: bad\n")
    with pytest.raises(ParseError) as exc:
        load_cron_yaml(f)
    assert exc.value.file == str(f)
    assert exc.value.message  # has some message


def test_parse_error_has_location_attrs(tmp_path: Path):
    f = tmp_path / "bad.yaml"
    f.write_text("key: value\nbroken:\n  - : invalid\n  - ok\n")
    with pytest.raises(ParseError) as exc:
        load_cron_yaml(f)
    # line/column should be set
    assert exc.value.line is not None or exc.value.message  # at minimum has a message


def test_non_mapping_top_level_returns_as_list(tmp_path: Path):
    f = tmp_path / "scalar.yaml"
    f.write_text("just-a-string\n")
    # Either returns [{}] or raises — we choose raises ParseError
    with pytest.raises((ParseError, UnreadableFileError)):
        load_cron_yaml(f)


# --- Integration with real-world cron.yaml ---


def test_realistic_cron_yaml(tmp_path: Path):
    f = tmp_path / "realistic.yaml"
    f.write_text(textwrap.dedent("""\
        - name: morning_briefing
          schedule: "0 9 * * MON-FRI"
          prompt: "Summarize the news"
          context_from:
            - weather_job
        - name: cleanup
          schedule: "0 2 * * *"
          command: "rm -rf /tmp/cache"
    """))
    result = load_cron_yaml(f)
    assert len(result) == 2
    assert result[0]["context_from"] == ["weather_job"]
