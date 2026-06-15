"""YAML 로더 (스키마 검증 전 단계).

다른 PC 작업 가이드:
    def load_cron_yaml(path: Path) -> list[dict]: ...
        - 파일 읽고 YAML 파싱
        - 최상위가 list[dict] 또는 dict 가정
        - 파싱 에러 시 (line, column) 함께 예외 발생
        - PyYAML 의존 vs 자체 구현 결정 필요 (Y001 가이드 참고)
"""
# TODO: 다른 PC에서 구현
