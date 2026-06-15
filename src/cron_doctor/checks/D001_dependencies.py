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
# TODO: 다른 PC에서 구현
