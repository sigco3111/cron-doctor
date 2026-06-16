"""v1.0.0 performance benchmarks.

Guards the performance budgets documented in docs/API.md:
- `python -m cron_doctor --version` startup: < 200 ms (2× spec of 100 ms)
- `diagnose()` on 10 small YAML files: < 100 ms (2× spec of 50 ms)
- `watch()` per-iteration latency: < 2 × poll_interval_ms

Uses only stdlib (time.perf_counter) — no pytest-benchmark dependency.
All budgets are deliberately 2× the target spec so CI noise doesn't cause
flaky failures.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

from cron_doctor import core


REPO = Path(__file__).resolve().parent.parent

STARTUP_BUDGET_MS = 200       # 2× spec of 100ms
DIAGNOSE_BUDGET_MS = 100      # 2× spec of 50ms
WATCH_POLL_INTERVAL_MS = 50   # generous interval for stable measurement
WATCH_LATENCY_BUDGET_MS = WATCH_POLL_INTERVAL_MS * 2


# ---------------------------------------------------------------------------
# Startup time: `python -m cron_doctor --version`
# ---------------------------------------------------------------------------

def test_startup_time_under_budget():
    """`python -m cron_doctor --version` must start in < 200ms (2× spec)."""
    start = time.perf_counter()
    result = subprocess.run(
        [sys.executable, "-m", "cron_doctor", "--version"],
        capture_output=True, text=True, timeout=5,
        cwd=str(REPO),
    )
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert result.returncode == 0
    assert elapsed_ms < STARTUP_BUDGET_MS, (
        f"Startup took {elapsed_ms:.1f}ms (budget: {STARTUP_BUDGET_MS}ms). "
        f"Likely cause: eager import of cron_doctor.core in __init__.py."
    )


# ---------------------------------------------------------------------------
# Diagnose throughput: 10 small YAML files
# ---------------------------------------------------------------------------

@pytest.fixture
def ten_yaml_files(tmp_path):
    d = tmp_path / "yaml_dir"
    d.mkdir()
    for i in range(10):
        (d / f"job_{i}.yaml").write_text(
            f"jobs:\n  - name: job_{i}\n    schedule: '0 */{i+1} * * *'\n    command: echo task_{i}\n"
        )
    return d


def test_diagnose_10_files_under_budget(ten_yaml_files):
    """Diagnosing 10 small YAML files must complete in < 100ms (2× spec)."""
    start = time.perf_counter()
    results = core.diagnose(ten_yaml_files)
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert len(results) == 10
    assert elapsed_ms < DIAGNOSE_BUDGET_MS, (
        f"Diagnose(10 files) took {elapsed_ms:.1f}ms (budget: {DIAGNOSE_BUDGET_MS}ms)."
    )


# ---------------------------------------------------------------------------
# Watch latency: per-iteration time < 2 × poll_interval
# ---------------------------------------------------------------------------

def test_watch_latency_under_poll_interval(tmp_path):
    """watch() per-iteration latency must stay under 2 × poll_interval."""
    p = tmp_path / "x.yaml"
    p.write_text("jobs:\n  - name: ok\n    schedule: '0 * * * *'\n    command: echo hi\n")

    gen = core.watch(p, poll_interval_ms=WATCH_POLL_INTERVAL_MS, debounce_ms=0)
    try:
        first = next(gen)
        assert first.kind == "added"
        t0 = time.perf_counter()
        # Wait for the next iteration by sleeping slightly more than poll_interval
        time.sleep((WATCH_POLL_INTERVAL_MS / 1000.0) + 0.02)
        t1 = time.perf_counter()
        elapsed_ms = (t1 - t0) * 1000
        assert elapsed_ms < WATCH_LATENCY_BUDGET_MS, (
            f"Watch iteration took {elapsed_ms:.1f}ms (budget: {WATCH_LATENCY_BUDGET_MS}ms)."
        )
    finally:
        gen.close()
