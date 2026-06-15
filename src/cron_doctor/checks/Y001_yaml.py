"""Y001: YAML 문법 검증.

다른 PC 작업 가이드:
    - PyYAML 의존 없이 가능? → 표준 라이브러리만으론 한계. trade-off 결정:
        옵션 A) `yaml` 패키지 의존성 추가 (PyYAML)
        옵션 B) 직접 미니 YAML 파서 구현 (단순 cron.yaml 패턴에 한정)
        옵션 C) v0.1.0은 옵션 B, v0.2.0+에서 옵션 A로 마이그레이션
    - 추천: 옵션 A (zero-deps 정책 양보, 정확도 우선)
    - 에러 시 정확한 line/column 보고 (yaml.YAMLError的属性)
"""
# TODO: 다른 PC에서 구현
