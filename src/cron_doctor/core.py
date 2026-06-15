"""메인 로직 + I/O — 파일 읽기, 검사 오케스트레이션, 결과 집계.

다른 PC 작업 가이드:
    - diagnose(path: Path) -> CheckResult: 메인 진입점
    - 파일이 디렉토리면 재귀, .yaml/.yml 확장자만 처리
    - 각 job을 5개 검사에 통과시키고 issues 수집
    - _default_registry() 함수 내부에서 lazy import
"""
# TODO: 다른 PC에서 구현
