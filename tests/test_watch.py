"""RED tests for cron_doctor.core.watch — must FAIL until implementation lands."""
import os
import time
from pathlib import Path

import pytest

from cron_doctor import WatchEvent, watch


# --- Smoke ---

def test_watch_is_importable():
    assert callable(watch)
    assert WatchEvent is not None


def test_watch_event_is_frozen():
    import dataclasses
    assert dataclasses.is_dataclass(WatchEvent)
    e = WatchEvent(path=Path("a.yaml"), kind="modified", results=[], timestamp=1.0)
    with pytest.raises(Exception):
        e.kind = "added"


# --- Path validation ---

def test_watch_nonexistent_path_raises():
    with pytest.raises((FileNotFoundError, OSError)):
        for _ in watch("/no/such/path.yaml"):
            pass


# --- Single-file modify ---

def test_watch_single_file_modify(tmp_path):
    f = tmp_path / "x.yaml"
    f.write_text("- name: a\n  schedule: '0 * * * *'\n  prompt: x\n")
    gen = watch(f, debounce_ms=50, poll_interval_ms=20)
    first = next(gen)
    assert first.kind == "added"
    assert first.path == f
    # Modify
    time.sleep(0.05)
    os.utime(f, None)  # touch
    f.write_text("- name: a\n  schedule: '5 * * * *'\n  prompt: x\n")
    second = next(gen, None)
    assert second is not None
    assert second.kind == "modified"
    gen.close()


# --- Directory add/delete ---

def test_watch_directory_add(tmp_path):
    (tmp_path / "a.yaml").write_text("- name: a\n  schedule: '0 * * * *'\n  prompt: x\n")
    gen = watch(tmp_path, debounce_ms=50, poll_interval_ms=20)
    first = next(gen)
    assert first.path.name == "a.yaml"
    assert first.kind == "added"
    # Add a new file
    time.sleep(0.05)
    new = tmp_path / "b.yaml"
    new.write_text("- name: b\n  schedule: '0 * * * *'\n  prompt: x\n")
    second = next(gen, None)
    assert second is not None
    assert second.kind == "added"
    assert second.path.name == "b.yaml"
    gen.close()


def test_watch_directory_delete(tmp_path):
    target = tmp_path / "a.yaml"
    target.write_text("- name: a\n  schedule: '0 * * * *'\n  prompt: x\n")
    gen = watch(tmp_path, debounce_ms=50, poll_interval_ms=20)
    first = next(gen)
    assert first.path.name == "a.yaml"
    # Delete
    time.sleep(0.05)
    target.unlink()
    second = next(gen, None)
    assert second is not None
    assert second.kind == "deleted"
    assert second.results == []
    gen.close()


# --- Debounce ---

def test_watch_debounce_coalesces_rapid_writes(tmp_path):
    f = tmp_path / "x.yaml"
    f.write_text("- name: a\n  schedule: '0 * * * *'\n  prompt: x\n")
    gen = watch(f, debounce_ms=150, poll_interval_ms=20)
    first = next(gen)
    assert first.kind == "added"
    for i in range(5):
        time.sleep(0.02)
        f.write_text(f"- name: a\n  schedule: '{i} * * * *'\n  prompt: x\n")
    time.sleep(0.3)
    second = next(gen, None)
    assert second is not None
    assert second.kind == "modified"
    gen.close()


# --- Skip non-yaml ---

def test_watch_skips_non_yaml_files(tmp_path):
    (tmp_path / "a.yaml").write_text("- name: a\n  schedule: '0 * * * *'\n  prompt: x\n")
    gen = watch(tmp_path, debounce_ms=50, poll_interval_ms=20)
    first = next(gen)
    assert first.path.suffix == ".yaml"
    # Create a non-yaml file
    time.sleep(0.05)
    (tmp_path / "b.txt").write_text("not yaml")
    # Create another yaml
    (tmp_path / "c.yaml").write_text("- name: c\n  schedule: '0 * * * *'\n  prompt: x\n")
    second = next(gen, None)
    # Should be c.yaml, not b.txt
    assert second is not None
    assert second.path.name == "c.yaml"
    gen.close()


# --- Hidden dirs ---

def test_watch_skips_hidden_dirs(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config.yaml").write_text("- name: x\n  schedule: '0 * * * *'\n  prompt: x\n")
    (tmp_path / "a.yaml").write_text("- name: a\n  schedule: '0 * * * *'\n  prompt: x\n")
    gen = watch(tmp_path, debounce_ms=50, poll_interval_ms=20)
    ev = next(gen)
    assert ev.path.name == "a.yaml"
    gen.close()


# --- Generator cleanup ---

def test_watch_generator_can_be_closed(tmp_path):
    f = tmp_path / "x.yaml"
    f.write_text("- name: a\n  schedule: '0 * * * *'\n  prompt: x\n")
    gen = watch(f, debounce_ms=50, poll_interval_ms=20)
    next(gen)
    gen.close()
    # Should be cleanly closed; calling next on a closed gen is a no-op


# --- results populated for added/modified ---

def test_watch_added_event_has_results(tmp_path):
    f = tmp_path / "x.yaml"
    f.write_text("- name: a\n  schedule: '0 * * * *'\n  prompt: x\n")
    gen = watch(f, debounce_ms=50, poll_interval_ms=20)
    first = next(gen)
    assert first.kind == "added"
    assert first.results  # non-empty list
    assert isinstance(first.results[0].jobs, list)
    gen.close()


# --- pollig_interval / debounce defaults ---

def test_watch_default_debounce_is_200ms():
    import inspect
    sig = inspect.signature(watch)
    assert sig.parameters["debounce_ms"].default == 200
    assert sig.parameters["poll_interval_ms"].default == 100
