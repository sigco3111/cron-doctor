"""S001: Hermes cron.yaml 스키마 검증.

다른 PC 작업 가이드:
    - 허용된 키: name, schedule, timezone, prompt, enabled_toolsets, workdir,
                 context_from, skills, model, script, deliver, repeat, no_agent, profile
    - 미허용 키 발견 시 ERROR (오타 가능성)
    - 필수 키: name, schedule, prompt (또는 script)
    - 타입 검증: schedule은 str, repeat는 int, context_from은 list[str] 등
    - 스키마 정의는 SCHEMA dict 상수로 (json schema 스타일)
"""
# TODO: 다른 PC에서 구현
