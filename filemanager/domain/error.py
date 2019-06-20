"""Structs for errors and warnings."""

from typing import Optional
from enum import Enum
from dataclasses import dataclass, field


@dataclass
class Error:
    """Represents an error related to file processing."""

    class Severity(Enum):
        """Severity levels for errors."""

        FATAL = 'fatal'
        WARNING = 'warn'

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
