# cron-doctor

> **cron 작업을 진단하는 가벼운 CLI** — `cron.yaml`의 문법, 의미, 의존성, 스키마를 한 번에 검증합니다.
> A lightweight CLI that diagnoses your cron jobs — syntax, semantics, dependencies, and schema in one shot.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-zero-brightgreen.svg)](#설치--installation)
[![Status: 0.1.0 (skeleton)](https://img.shields.io/badge/status-0.1.0--skeleton-orange.svg)](#로드맵--roadmap)

`md-doctor`의 짝꿍 프로젝트 — **마크다운을 진단하듯, cron 작업을 진단합니다**.

---

## 🤔 왜 이게 필요한가? — Why a Cron YAML Linter?

기존 cron 도구들의 갭 4가지:

1. **crontab(1)은 5필드만 안다** — Hermes/GitHub Actions 스타일의 `cron.yaml` (이름·명령·의존성 메타데이터) 은 모름
2. **온라인 검증기는 6필드 cron 파싱만** — YAML 문법 에러는 못 잡음, 의미 오류(0요일 0요일)도 못 잡음
3. **대부분 zero-deps를 안 지킴** — `croniter`, `pyyaml`, `click` 등 무거운 의존성을 끌고 옴
4. **CI 통합이 불편** — 사람이 보는 컬러 출력은 있지만, GitHub Actions용 SARIF/주석 포맷이 없음

`cron-doctor`는 이 4가지를 한 번에 해결합니다.

> **Why this exists.** Traditional `crontab(1)` only knows 5-field syntax. Modern job runners (Hermes, GitHub Actions) use richer `cron.yaml` files with names, commands, and dependency metadata — and existing tools don't validate them end-to-end. `cron-doctor` fills that gap with zero dependencies and CI-friendly output.

---

## ✨ 주요 기능 — Features

- ✅ **YAML 문법 검증** — 파싱 에러를 정확한 라인/컬럼으로
- ✅ **cron 표현식 검증** — 5필드(Quartz) + 6필드(Hermes) 모두 지원
- ✅ **의미 검사** — 비현실적 스케줄, 0요일 0요일, 1분마다 등 의심 패턴
- ✅ **의존성 그래프** — `context_from` 체인이 순환하는지, 깨진 참조가 있는지
- ✅ **스키마 검증** — Hermes `cron.yaml` 스키마에 맞는 키만 사용했는지
- 🎨 **사람용 컬러 출력** + **JSON** + **GitHub Actions 워크플로 명령** 출력 동시 지원
- 📦 **Zero external dependencies** — Python 3.9+ 표준 라이브러리만

---

## 📦 설치 — Installation

```bash
# 다른 PC에서 (이 PC는 README/About만 작업)
git clone https://github.com/sigco3111/cron-doctor.git
cd cron-doctor
pip install -e ".[dev]"
```

**다른 PC 작업 흐름**:
```bash
git clone → cd cron-doctor → python3 -m venv venv → 
source venv/bin/activate → pip install -e ".[dev]" → pytest
```
3분이면 환경 검증 끝.

> 📌 **현재 상태**: 이 repo는 **Phase 0 — 스켈레톤 + 문서** 단계입니다. 실제 소스 코드(`src/cron_doctor/`)는 다른 PC에서 작업 예정. README/CHANGELOG/CONTRIBUTING/LICENSE만 먼저 공개.

---

## 🚀 빠른 시작 — Quick Start (v0.1.0 이후)

```bash
# 단일 파일 검증
cron-doctor check ./cron.yaml

# 디렉토리 재귀 검증
cron-doctor check ./jobs/ --recursive

# JSON 출력 (CI/훅 통합)
cron-doctor check ./cron.yaml --format json

# GitHub Actions 워크플로 명령 출력
cron-doctor check ./cron.yaml --format github

# 사용 가능한 검사 목록
cron-doctor list-checks

# 자동 수정 제안 (안전, dry-run 기본)
cron-doctor fix ./cron.yaml --dry-run
```

**Python API (v0.2.0+ 예정)**:
```python
from cron_doctor import diagnose

result = diagnose("./cron.yaml")
for issue in result.issues:
    print(f"[{issue.severity}] {issue.check_id}: {issue.message}")
    if issue.suggestion:
        print(f"  💡 {issue.suggestion}")
```

---

## 🔍 검사 모듈 — Checks

### v0.1.0 (활성, 다른 PC에서 구현)
| ID | 이름 | 설명 |
|---|---|---|
| `Y001` | YAML 파싱 | YAML 문법 오류를 정확한 위치로 보고 |
| `C001` | cron 표현식 | 5/6필드, 범위, 단계, 별표 모두 검증 |
| `C002` | 의미 검사 | 0요일 0요일, 1분마다 등 의심 패턴 |
| `D001` | 의존성 그래프 | `context_from` 체인의 순환 / 깨진 참조 |
| `S001` | 스키마 검증 | Hermes cron.yaml 스키마 준수 |

### v0.2.0+ (예정)
- `T001` 시간대 — `timezone` 필드 유효성
- `P001` 프롬프트 자가검증 — 프롬프트 길이/민감정보
- `M001` MCP 설정 검증 — `enabled_toolsets` 참조 무결성

---

## 🎯 사용 시나리오 — Use Cases

### 1. 새 cron.yaml 커밋 전 로컬 검증
```bash
cron-doctor check ./cron.yaml
# exit 0 = 통과, 1 = 발견된 이슈, 2 = 사용 오류
```

### 2. CI에서 PR마다 자동 검사
```yaml
# .github/workflows/cron-validate.yml
- uses: sigco3111/cron-doctor@v1
  with:
    path: ./cron.yaml
    fail-on: error
```

### 3. 여러 환경의 cron.yaml 한꺼번에 비교
```bash
cron-doctor check ./jobs/ --recursive --format json | \
  jq '.[] | select(.severity == "error")'
```

### 4. 기존 cron 작업 회귀 테스트
```bash
cron-doctor check ./cron.yaml --format json > before.json
# 작업 수정 후
cron-doctor check ./cron.yaml --format json > after.json
diff before.json after.json
```

### 5. 새 cron 추가 시 안전성 확인
```bash
# 새로 추가한 job이 의존하는 context_from이 실재하는지
cron-doctor check ./cron.yaml --checks D001
```

---

## 🧩 다른 PC에서 작업 — Development on Another PC

이 repo는 **다른 PC에서 본격적으로 코딩**합니다. 이 PC에서는 README/About/스켈레톤만 작업했어요.

```bash
# 1. 클론
git clone https://github.com/sigco3111/cron-doctor.git
cd cron-doctor

# 2. 가상환경
python3 -m venv venv
source venv/bin/activate

# 3. 설치 (dev 의존성 포함)
pip install -e ".[dev]"

# 4. 테스트
pytest

# 5. 실제 CLI 동작 확인
cron-doctor --version
cron-doctor check tests/fixtures/valid.yaml
```

**작업 순서 제안**:
1. `src/cron_doctor/models.py` — 도메인 타입 (순환 import 방지 핵심)
2. `src/cron_doctor/parser.py` — YAML + cron 표현식 파서
3. `src/cron_doctor/checks/` — 5개 검사 모듈 (Y/C/D/S)
4. `src/cron_doctor/cli.py` — argparse CLI
5. `tests/` — 골든 파일 + 단위 테스트
6. `.github/workflows/ci.yml` + `action.yml`

---

## 🗺️ 로드맵 — Roadmap

- [x] **v0.1.0** — README/About/스켈레톤 (이 단계) ✅
- [ ] **v0.1.0** — 5개 핵심 검사 + CLI 골격 + 골든 파일 테스트
- [ ] **v0.2.0** — T001/P001/M001 + Python API + fix --dry-run
- [ ] **v0.3.0** — watch 모드 (실시간 파일 변경 감시)
- [ ] **v1.0.0** — 안정 API + 95% 코드 커버리지 + 공식 GitHub Action 마켓플레이스 등록

---

## 📁 디렉토리 구조 — Directory Layout

```
cron-doctor/
├── README.md               ← 한/영 병기, 다층 옵션
├── CHANGELOG.md            ← Keep a Changelog 형식
├── CONTRIBUTING.md         ← 새 검사 모듈 추가 가이드
├── LICENSE                 ← MIT
├── .gitignore              ← Python 표준
├── pyproject.toml          ← setuptools 백엔드, zero-deps
├── pytest.ini              ← 표준 pytest 설정
├── src/
│   └── cron_doctor/        ← 다른 PC에서 구현
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       ├── core.py
│       ├── models.py
│       ├── exceptions.py
│       └── checks/
│           ├── __init__.py
│           ├── yaml_check.py     (Y001)
│           ├── cron_syntax.py    (C001)
│           ├── cron_semantics.py (C002)
│           ├── dependencies.py   (D001)
│           └── schema.py         (S001)
├── tests/
│   ├── fixtures/
│   │   ├── valid.yaml
│   │   ├── invalid-cron.yaml
│   │   ├── circular-dep.yaml
│   │   └── broken-context.yaml
│   └── test_*.py
└── .github/
    ├── workflows/ci.yml
    └── action.yml
```

---

## 🙏 감사의 말 — Acknowledgements

- [`md-doctor`](https://github.com/sigco3111/md-doctor) — 같은 시리즈의 영감, "잘 진단해주는" 톤
- [`crontab(1)`](https://man7.org/linux/man-pages/man5/crontab.5.html) — 5필드 cron의 원형
- [Hermes Agent](https://hermes-agent.nousresearch.com/) — 6필드 cron.yaml의 실사용처

---

## 📄 라이선스 — License

MIT © 2026 sigco3111

---

<a id="english"></a>

## 🇬🇧 English Quick Reference

`cron-doctor` is a zero-dependency CLI that validates `cron.yaml` files for **syntax** (YAML + cron expressions), **semantics** (suspicious schedules, zero-weekday-zero), **dependencies** (`context_from` chains), and **schema** (Hermes cron.yaml schema).

**Install** (from another PC, where the source code will be developed):
```bash
git clone https://github.com/sigco3111/cron-doctor.git
cd cron-doctor
pip install -e ".[dev]"
```

**Status**: v0.1.0 skeleton (README + LICENSE only). Full implementation is in progress on a different machine.

**Roadmap**: v0.1.0 (5 core checks + CLI) → v0.2.0 (Python API + fix --dry-run) → v0.3.0 (watch mode) → v1.0.0 (stable API + GitHub Action marketplace).

See the [Korean section above](#crond-doctor) for full documentation, use cases, and check module details.
