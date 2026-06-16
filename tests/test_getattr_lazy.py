"""v1.0.0 lazy __getattr__ contract tests.

Verifies that:
- All 6 lazy-loaded symbols (diagnose, fix, propose_fixes, apply_fixes,
  watch, WatchEvent) resolve to the correct core.py objects
- Importing cron_doctor does NOT eagerly import cron_doctor.core
  (critical for fast `cron-doctor --version` startup)
- Unknown attribute access raises AttributeError (not silent fallback)
"""
from __future__ import annotations

import importlib
import subprocess
import sys

import pytest

import cron_doctor
import cron_doctor.core as core_mod
from cron_doctor.core import WatchEvent as CoreWatchEvent


LAZY_SYMBOLS = ["diagnose", "fix", "propose_fixes", "apply_fixes", "watch", "WatchEvent"]


# ---------------------------------------------------------------------------
# __getattr__ resolution
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", LAZY_SYMBOLS)
def test_getattr_resolves_to_core_symbol(name):
    """Each lazy symbol in __init__ must resolve to the same object as core.py."""
    init_attr = getattr(cron_doctor, name)
    core_attr = getattr(core_mod, name)
    assert init_attr is core_attr, f"cron_doctor.{name} is not cron_doctor.core.{name}"


def test_getattr_diagnose_is_callable():
    assert callable(cron_doctor.diagnose)


def test_getattr_watch_event_is_class():
    assert isinstance(cron_doctor.WatchEvent, type)
    assert issubclass(cron_doctor.WatchEvent, CoreWatchEvent)


# ---------------------------------------------------------------------------
# __getattr__ error handling
# ---------------------------------------------------------------------------

def test_getattr_unknown_raises_attribute_error():
    with pytest.raises(AttributeError) as excinfo:
        cron_doctor.does_not_exist  # type: ignore[attr-defined]
    msg = str(excinfo.value)
    assert "cron_doctor" in msg
    assert "does_not_exist" in msg


def test_getattr_does_not_silently_return_none():
    """A typo must raise, not silently produce None."""
    with pytest.raises(AttributeError):
        _ = cron_doctor.diagnos  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Lazy import behavior (no eager core import)
# ---------------------------------------------------------------------------

def test_importing_cron_doctor_does_not_load_core():
    """Importing cron_doctor must NOT trigger core.py to be loaded.

    This is a v1.0.0 performance contract: `cron-doctor --version` should
    start in < 200ms. If core.py is loaded eagerly, YAML loaders, checks,
    and the watcher all get pulled in.
    """
    # Use a fresh subprocess to get a clean import state.
    result = subprocess.run(
        [sys.executable, "-c",
         "import cron_doctor; "
         "import sys; "
         "print('core_loaded' if 'cron_doctor.core' in sys.modules else 'core_not_loaded')"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0
    assert "core_not_loaded" in result.stdout, (
        f"cron_doctor.core was eagerly loaded on import.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_eager_attribute_access_triggers_core_load():
    """Accessing cron_doctor.diagnose (or any lazy symbol) MUST load core.py."""
    result = subprocess.run(
        [sys.executable, "-c",
         "import cron_doctor; "
         "import sys; "
         "cron_doctor.diagnose; "
         "print('core_loaded' if 'cron_doctor.core' in sys.modules else 'core_not_loaded')"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0
    assert "core_loaded" in result.stdout
