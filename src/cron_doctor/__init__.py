"""cron-doctor: cron.yaml 검증 CLI.

이 패키지는 다른 PC에서 본격적으로 구현됩니다.
이 파일은 패키지 진입점 + 공개 API re-export 역할.

Phase 0 (현재): README/About만 공개, 소스 코드는 스켈레톤.
Phase 1+ (다른 PC):
    1. models.py 완성 (도메인 타입: Diagnosis, Severity, CheckResult)
    2. parsers/cron_expr.py + parsers/yaml_loader.py (의존성 없는 파서)
    3. checks/ 5개 모듈 구현
    4. cli.py (argparse)
    5. tests/ 골든 파일 + 단위 테스트

공개 API (v0.2.0+ 예정):
    from cron_doctor import diagnose, Diagnosis, Severity
"""
__version__ = "0.1.0"
__all__ = ["__version__"]
