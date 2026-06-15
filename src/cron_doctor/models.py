"""도메인 타입 모음 — 순환 import 방지의 핵심.

다른 PC 작업 가이드:
    - Diagnosis (frozen dataclass): check_id, severity, message, suggestion, file, line
    - Severity (str, Enum): INFO, WARNING, ERROR
    - CheckResult (dataclass): 진단 결과 종합 (file, jobs, issues[])
    - BaseCheck (Protocol): 모든 검사가 구현할 인터페이스 (run(job, context) -> list[Diagnosis])

순환 import 방지 패턴:
    - core.py와 checks/ 모두 이 모듈만 직접 import
    - core가 default_checks() 호출 시 함수 내부 lazy import
    - 자세한 내용: CONTRIBUTING.md 참고
"""
# TODO: 다른 PC에서 Severity, Diagnosis, CheckResult, BaseCheck 구현
