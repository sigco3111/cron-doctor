"""D001: 의존성 그래프 검증.

다른 PC 작업 가이드:
    - `context_from: [other_job_id]` 체인이 올바른지
    - 검사 3종:
        1. 깨진 참조: 존재하지 않는 job_id 참조 → ERROR
        2. 순환 의존: A→B→A → ERROR
        3. 자기 자신 참조: A → A → ERROR
    - 알고리즘: dict + DFS + visited set
    - 의존성 깊이 5+ 이면 WARNING (깊은 체인)
"""
from __future__ import annotations

from typing import List

from cron_doctor.models import Diagnosis, Severity


class DependenciesCheck:
    check_id = "D001"
    name = "dependencies"

    def run(self, job: dict, context: dict) -> list[Diagnosis]:
        """For each job, check that its context_from references valid existing jobs.
        Also detects cycles by traversing the graph.
        """
        issues = []
        file = context.get("file", "<unknown>")
        all_jobs = context.get("all_jobs", [])
        # Build name → job map
        names = {j.get("name"): j for j in all_jobs if isinstance(j, dict) and j.get("name")}

        context_from = job.get("context_from")
        if not isinstance(context_from, list):
            return issues  # S001 catches wrong type

        for ref in context_from:
            if not isinstance(ref, str):
                continue
            if ref not in names:
                issues.append(Diagnosis(
                    check_id=self.check_id,
                    severity=Severity.ERROR,
                    message=f"Job {job.get('name', '?')!r} context_from references unknown job {ref!r}",
                    suggestion=f"Either add a job named {ref!r} or remove this reference",
                    file=file,
                ))

        return issues

    def check_file(self, all_jobs: list, file: str) -> list[Diagnosis]:
        """File-level check: detect cycles and deep chains across all jobs.
        Called by core.py after per-job checks.
        """
        issues = []
        names = {j.get("name"): j for j in all_jobs if isinstance(j, dict) and j.get("name")}

        # Build adjacency map: name → list of context_from names
        graph = {}
        for job in all_jobs:
            if not isinstance(job, dict):
                continue
            name = job.get("name")
            if not name:
                continue
            deps = job.get("context_from", [])
            if isinstance(deps, list):
                graph[name] = [d for d in deps if isinstance(d, str)]
            else:
                graph[name] = []

        # Detect cycles using DFS
        cycles = self._find_cycles(graph)
        for cycle in cycles:
            cycle_str = " → ".join(cycle)
            issues.append(Diagnosis(
                check_id=self.check_id,
                severity=Severity.ERROR,
                message=f"Circular dependency: {cycle_str}",
                suggestion="Break the cycle by removing one context_from reference",
                file=file,
            ))

        # Detect deep chains (depth >= 5)
        depths = self._compute_depths(graph)
        for name, depth in depths.items():
            if depth >= 5:
                issues.append(Diagnosis(
                    check_id=self.check_id,
                    severity=Severity.WARNING,
                    message=f"Job {name!r} has a deep dependency chain (depth {depth})",
                    suggestion="Consider flattening the chain or using intermediate jobs",
                    file=file,
                ))

        return issues

    def _find_cycles(self, graph: dict) -> list[list[str]]:
        """DFS-based cycle detection. Returns list of cycles (each as list of names)."""
        cycles = []
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {n: WHITE for n in graph}
        path = []

        def dfs(node):
            color[node] = GRAY
            path.append(node)
            for neighbor in graph.get(node, []):
                if neighbor not in color:
                    continue  # broken ref, handled per-job
                if color[neighbor] == GRAY:
                    # Found a cycle: path[path.index(neighbor):] + [neighbor]
                    idx = path.index(neighbor)
                    cycle = path[idx:] + [neighbor]
                    cycles.append(cycle)
                elif color[neighbor] == WHITE:
                    dfs(neighbor)
            path.pop()
            color[node] = BLACK

        for node in list(graph.keys()):
            if color[node] == WHITE:
                dfs(node)

        return cycles

    def _compute_depths(self, graph: dict) -> dict[str, int]:
        """Compute longest-path depth for each node (0 = no deps)."""
        depths = {}
        def depth(n, visited=None):
            if visited is None:
                visited = set()
            if n in visited:
                return 0  # cycle, treat as 0
            if n in depths:
                return depths[n]
            visited.add(n)
            deps = graph.get(n, [])
            if not deps:
                depths[n] = 0
                return 0
            d = 1 + max((depth(x, visited.copy()) for x in deps), default=0)
            depths[n] = d
            return d
        for n in graph:
            depth(n)
        return depths
