"""Structs for errors and warnings."""

from enum import Enum
from typing import Optional, Dict, Any

from dataclasses import dataclass, field


class Severity(Enum):
    """Severity levels for errors."""

    FATAL = 'fatal'
    WARNING = 'warn'
    INFO = 'info'


# This is not an enum, because we want checkers to define and maintain their
# own codes.
Code = str
UNKNOWN: Code = 'unknown_error'


@dataclass
class Error:
    """Represents an error related to file processing."""

    severity: Severity
    """Severity level of this error."""

    message: str
    """Human-readable error message."""

    code: Code = field(default=UNKNOWN)
    """Specific code for this error."""

    path: Optional[str] = field(default=None)
    """Optional path for file associated with this error."""

    is_persistant: bool = field(default=True)
    """Indicates whether or not this error sticks around between requests."""

    @property
    def is_fatal(self) -> bool:
        """Indicates whether this is a fatal error."""
        return bool(self.severity == Severity.FATAL)

    @property
    def is_warning(self) -> bool:
        """Indicates whether this is is a warning."""
        return bool(self.severity == Severity.WARNING)

    def to_dict(self) -> Dict[str, Any]:
        """Generate a dict representation of this error."""
        return {
            'severity': self.severity.value,
            'message': self.message,
            'code': self.code,
            'path': self.path,
            'is_persistant': self.is_persistant
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Error':
        """Translate a dict to an :class:`.Error`."""
        return cls(
            severity=Severity(data['severity']),
            message=data['message'],
            code=data.get('code', UNKNOWN),
            path=data.get('path', None),
            is_persistant=data.get('is_persistant', True)
        )
