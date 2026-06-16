"""`python -m cron_doctor` 진입점.

Calls `cron_doctor.cli.main()` and exits with the returned code.
"""
import sys
from cron_doctor.cli import main

if __name__ == "__main__":
    sys.exit(main())
