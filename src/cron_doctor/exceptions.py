"""Exception hierarchy for cron-doctor.

All cron-doctor exceptions inherit from `CronDoctorError`, so user code can
catch every project-specific error with a single `except CronDoctorError`.

Hierarchy:
    CronDoctorError (base)
    ├── ParseError             — YAML/config could not be parsed (carries file/line/column)
    ├── InvalidCronExpression  — malformed cron string (carries field name/index)
    ├── UnreadableFileError    — file not found / permission denied
    └── SchemaViolation        — YAML document does not match Hermes cron.yaml schema
"""


class CronDoctorError(Exception):
    """Base class for all cron-doctor errors."""


class ParseError(CronDoctorError):
    """YAML or config file could not be parsed.

    Attributes:
        file: Path to the offending file (str).
        line: 1-based line number, or None if not available.
        column: 1-based column number, or None if not available.
        message: Human-readable description.
    """

    def __init__(self, file: str, message: str, line: int | None = None, column: int | None = None) -> None:
        loc_parts = []
        if line is not None:
            loc_parts.append(f"line {line}")
        if column is not None:
            loc_parts.append(f"col {column}")
        loc = f" ({', '.join(loc_parts)})" if loc_parts else ""
        super().__init__(f"{file}{loc}: {message}")
        self.file = file
        self.message = message
        self.line = line
        self.column = column


class InvalidCronExpression(CronDoctorError):
    """A cron expression string is malformed or out of range.

    Attributes:
        expression: The original expression string.
        field_index: 0-based index of the offending field (0-5), or None.
        field_name: 'minute'|'hour'|'day'|'month'|'weekday'|'second', or None.
        message: Human-readable description.
    """

    def __init__(
        self,
        expression: str,
        message: str,
        field_index: int | None = None,
        field_name: str | None = None,
    ) -> None:
        where = ""
        if field_name is not None:
            where = f" [field={field_name}"
            if field_index is not None:
                where += f" index={field_index}"
            where += "]"
        super().__init__(f"{expression!r}{where}: {message}")
        self.expression = expression
        self.field_index = field_index
        self.field_name = field_name
        self.message = message


class UnreadableFileError(CronDoctorError):
    """File could not be read (missing, permission denied, etc.).

    Attributes:
        path: Path to the file.
        reason: Human-readable explanation.
    """

    def __init__(self, path: str, reason: str) -> None:
        super().__init__(f"{path}: {reason}")
        self.path = path
        self.reason = reason


class SchemaViolation(CronDoctorError):
    """A YAML document does not conform to the Hermes cron.yaml schema.

    Attributes:
        file: Path to the offending file.
        key: Offending key (str) or None.
        reason: Human-readable explanation.
    """

    def __init__(self, file: str, reason: str, key: str | None = None) -> None:
        key_part = f" (key={key!r})" if key is not None else ""
        super().__init__(f"{file}{key_part}: {reason}")
        self.file = file
        self.key = key
        self.reason = reason
