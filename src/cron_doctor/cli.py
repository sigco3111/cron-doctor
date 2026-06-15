"""argparse 기반 CLI.

다른 PC 작업 가이드:
    위치 인자 path는 nargs="?" (--list-checks 같은 부속 명령과 공존)
    표준 옵션 5종:
        -o/--output, --format (text/json/github), --min-severity, --fail-on, --checks/--list, --version
    부속 명령 1종: --list-checks
    exit code: 0=통과, 1=발견된 이슈, 2=사용자 오류

    GitHub Actions 워크플로 포맷:
        ::warning file=F,line=L::msg%0A
        msg.replace(chr(10), '%0A') 잊지 말 것
"""
# TODO: 다른 PC에서 구현
