"""YAML loader for cron-doctor.

Wraps PyYAML to:
- Always return list[dict] (wrap single-dict top-level in a list)
- Translate PyYAML YAMLError to ParseError with file/line/column
- Translate FileNotFoundError / PermissionError to UnreadableFileError

Stable since v1.0.0. No breaking changes within v1.x.
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


def load_cron_document(path):
    """Load the full YAML document as a dict. Supports both legacy (top-level list)
    and v0.2+ (top-level dict with `toolsets:` and `jobs:` keys) formats.

    Returns:
        dict with optional keys:
            - "jobs": list of job dicts (always present, may be empty)
            - "toolsets": list of toolset dicts (only present if declared)
            - "raw": the top-level value as-is (for ad-hoc inspection)

    Raises:
        UnreadableFileError: file missing or permission denied.
        ParseError: YAML syntax error (carries file, line, column, message).
    """
    from typing import Union
    path_obj = Path(path)

    try:
        text = path_obj.read_text(encoding="utf-8")
    except FileNotFoundError as e:
        raise UnreadableFileError(str(path_obj), f"No such file: {e}") from e
    except PermissionError as e:
        raise UnreadableFileError(str(path_obj), f"Permission denied: {e}") from e
    except OSError as e:
        raise UnreadableFileError(str(path_obj), str(e)) from e

    if not text.strip():
        return {"jobs": []}

    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        line = None
        column = None
        msg = str(e)
        mark = getattr(e, "problem_mark", None)
        if mark is not None:
            line = mark.line + 1
            column = mark.column + 1
            msg = f"{e.problem} at line {line}, column {column}"
        raise ParseError(str(path_obj), msg, line=line, column=column) from e

    if data is None:
        return {"jobs": []}
    if isinstance(data, list):
        # Legacy format: top-level is a list of jobs
        return {"jobs": list(data)}
    if isinstance(data, dict):
        # v0.2+ format: top-level is a dict with optional `toolsets:` and `jobs:` keys
        out = {"raw": data}
        if "jobs" in data:
            jobs_val = data["jobs"]
            out["jobs"] = list(jobs_val) if isinstance(jobs_val, list) else []
        else:
            # No `jobs:` key — treat the dict itself as a single job
            out["jobs"] = [data]
        if "toolsets" in data:
            ts_val = data["toolsets"]
            out["toolsets"] = list(ts_val) if isinstance(ts_val, list) else []
        return out

    raise ParseError(
        str(path_obj),
        f"Top-level must be a list of jobs or a dict, got {type(data).__name__}",
    )
