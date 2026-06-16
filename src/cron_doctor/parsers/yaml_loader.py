"""YAML loader for cron-doctor.

Wraps PyYAML to:
- Always return list[dict] (wrap single-dict top-level in a list)
- Translate PyYAML YAMLError to ParseError with file/line/column
- Translate FileNotFoundError / PermissionError to UnreadableFileError
"""

from __future__ import annotations

from pathlib import Path
from typing import Union

import yaml

from cron_doctor.exceptions import ParseError, UnreadableFileError


def load_cron_yaml(path: Union[str, Path]) -> list[dict]:
    """Load a cron.yaml file and return a list of job dicts.

    Top-level may be a list of dicts OR a single dict (treated as one job).
    Empty file returns [].

    Raises:
        UnreadableFileError: file missing or permission denied.
        ParseError: YAML syntax error (carries file, line, column, message).
    """
    path = Path(path)

    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as e:
        raise UnreadableFileError(str(path), f"No such file: {e}") from e
    except PermissionError as e:
        raise UnreadableFileError(str(path), f"Permission denied: {e}") from e
    except OSError as e:
        raise UnreadableFileError(str(path), str(e)) from e

    if not text.strip():
        return []

    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        line = None
        column = None
        msg = str(e)
        mark = getattr(e, "problem_mark", None)
        if mark is not None:
            line = mark.line + 1   # 1-based
            column = mark.column + 1  # 1-based
            msg = f"{e.problem} at line {line}, column {column}"
        raise ParseError(str(path), msg, line=line, column=column) from e

    if data is None:
        return []
    if isinstance(data, list):
        return list(data)
    if isinstance(data, dict):
        return [data]

    # Top-level scalar/other — treat as parse error
    raise ParseError(
        str(path),
        f"Top-level must be a list of jobs or a single job dict, got {type(data).__name__}",
    )
