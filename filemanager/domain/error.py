"""Structs for errors and warnings."""

from enum import Enum
from typing import Optional, Dict, Any

from dataclasses import dataclass, field


@dataclass
class Error:
    """Represents an error related to file processing."""

    class Severity(Enum):
        """Severity levels for errors."""

        FATAL = 'fatal'
        WARNING = 'warn'
        INFO = 'info'

    class Code(Enum):
        """
        Known error conditions.

        Not implemented.
        """

        UNKNOWN = -1

    severity: Severity
    """Severity level of this error."""

    message: str
    """Human-readable error message."""

    code: Code = field(default=Code.UNKNOWN)
    """Specific code for this error. Not implemented."""

    path: Optional[str] = field(default=None)
    """Optional path for file associated with this error."""

    is_persistant: bool = field(default=True)
    """Indicates whether or not this error sticks around between requests."""

    def to_dict(self) -> Dict[str, Any]:
        return {
            'severity': self.severity.value,
            'message': self.message,
            'code': self.code.value,
            'path': self.path,
            'is_persistant': self.is_persistant
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Error':
        """Translate a dict to an :class:`.Error`."""
        return cls(
            severity=cls.Severity(data['severity']),
            message=data['message'],
            code=cls.Code(data.get('code', cls.Code.UNKNOWN.value)),
            path=data.get('path', None),
            is_persistant=data.get('is_persistant', True)
        )
