# Contributing to cron-doctor

`cron-doctor`에 기여하는 방법 — 새로운 검사 모듈을 추가하거나 기존 코드를 개선하는 가이드.

## 🎯 핵심 원칙 — Core Principles

1. **Minimal 외부 의존성** — Python 3.9+ 표준 라이브러리 + **PyYAML만**. PyYAML은 YAML 파싱 시 정확한 line/column 정보를 얻기 위해 사용됨. 그 외 추가 패키지는 끌어오지 않음.
2. **순환 import 방지** — `core.py` ↔ `checks/` 간 의존은 항상 `models.py`를 통해.
3. **테스트 우선** — 새 검사 모듈은 골든 파일(`tests/fixtures/`)과 함께 PR.
4. **한/영 문서** — README/CHANGELOG는 항상 한/영 병기.

## 🆕 새 검사 모듈 추가 — Adding a New Check

`cron-doctor`의 검사 모듈은 4단계로 추가합니다.

### 1단계: `src/cron_doctor/checks/` 에 새 파일

예: `C003_dst_safety.py` (서머타임 안전성 검사)

```python
# src/cron_doctor/checks/C003_dst_safety.py
from cron_doctor.models import Diagnosis, Severity, CheckResult
from cron_doctor.parsers.cron_expr import parse

class DSTSafetyCheck:
    """Detect cron schedules that may fire at the wrong time during DST transitions."""

    check_id = "C003"
    name = "DST safety"

    def run(self, job, context):
        issues = []
        schedule = job.get("schedule", "")
        if not schedule:
            return issues
        # 검사 로직 ...
        if problematic:
            issues.append(Diagnosis(
                check_id=self.check_id,
                severity=Severity.WARNING,
                message=f"Schedule '{schedule}' may fire twice or skip during DST",
                suggestion="Consider using UTC or a timezone-aware expression",
            ))
        return issues
```

### 2단계: `src/cron_doctor/checks/__init__.py` 의 레지스트리에 등록

```python
# src/cron_doctor/checks/__init__.py
from .C003_dst_safety import DSTSafetyCheck

ALL_CHECKS = [
    YAMLCheck(),           # Y001
    CronSyntaxCheck(),     # C001
    CronSemanticsCheck(),  # C002
    DSTSafetyCheck(),      # C003  ← 새로 추가
    DependenciesCheck(),   # D001
    SchemaCheck(),         # S001
]

def default_checks():
    return ALL_CHECKS
```

### 3단계: 골든 파일 추가

`tests/fixtures/` 에 검사 결과를 미리 알고 있는 YAML 파일을 추가:

```yaml
# tests/fixtures/dst-unsafe.yaml
- name: dst_unsafe_job
  schedule: "0 2 * * *"
  timezone: "America/New_York"
  prompt: "..."
```

### 4단계: 테스트 추가

```python
# tests/test_C003_dst_safety.py
from cron_doctor.checks.C003_dst_safety import DSTSafetyCheck

def test_dst_unsafe_emits_warning():
    check = DSTSafetyCheck()
    issues = check.run(
        {"name": "x", "schedule": "0 2 * * *", "timezone": "America/New_York"},
        context={},
    )
    assert len(issues) == 1
    assert issues[0].check_id == "C003"
    assert issues[0].severity == Severity.WARNING
```

## 🧪 테스트 실행 — Running Tests

```bash
# 전체 테스트
pytest

# 특정 검사 모듈만
pytest tests/test_C003_dst_safety.py -v

# 골든 파일 비교
pytest tests/test_golden.py -v
```

## 📝 커밋 메시지 — Commit Messages

[Conventional Commits](https://www.conventionalcommits.org/) 형식:

```
feat: add C003 DST safety check
fix: handle empty schedule in C001
docs: update README with C003 example
test: add golden file for C003
```

## 🔖 PR 체크리스트 — PR Checklist

- [ ] 골든 파일 추가 (`tests/fixtures/<name>.yaml`)
- [ ] 단위 테스트 1개 이상
- [ ] `pytest` 모두 통과
- [ ] `cron-doctor --list-checks` 에 새 검사가 표시됨
- [ ] README/CHANGELOG 업데이트 (영문/한글)
- [ ] Minimal 의존성 유지 (pyproject.toml `dependencies`는 `pyyaml`만 포함)

## ❓ 질문 — Questions

GitHub Issues 또는 `sigco3111` GitHub Discussions 에 올려주세요.

---

<a id="english"></a>

## 🇬🇧 English Quick Reference

To add a new check: (1) create `src/cron_doctor/checks/<id>_<name>.py`, (2) register in `checks/__init__.py`, (3) add a golden YAML to `tests/fixtures/`, (4) add a unit test. See the four-step tutorial above for full code examples.
