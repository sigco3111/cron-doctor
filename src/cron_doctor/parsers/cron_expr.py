"""cron 표현식 파서 (zero-deps).

다른 PC 작업 가이드:
    class CronExpression(NamedTuple):
        minute, hour, day, month, weekday: list[int]  # 확장된 값
        second: list[int] | None = None  # 6필드일 때만

    def parse(expr: str) -> CronExpression: ...
    def next_fire(expr: CronExpression, after: datetime) -> datetime: ...

    지원 케이스:
    - "*"  → 모든 값
    - "1-5"  → 범위
    - "*/15"  → 단계
    - "1,3,5"  → 목록
    - "0 2 * * 0"  → 5필드
    - "0 0 2 * * 0"  → 6필드 (Hermes 스타일, 초 먼저)
"""
# TODO: 다른 PC에서 구현
