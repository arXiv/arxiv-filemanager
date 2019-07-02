
from enum import Enum

from dataclasses import dataclass, field


@dataclass
class SourceTypeMixin:
    class SourceType(Enum):
        """High-level type of the submission source as a whole."""

        UNKNOWN = 'unknown'
        INVALID = 'invalid'
        POSTSCRIPT = 'ps'
        PDF = 'pdf'
        HTML = 'html'
        TEX = 'tex'

        @property
        def is_unknown(self) -> bool:
            """Indicate whether this is the :const:`.UNKNOWN` type."""
            return self is self.UNKNOWN

        @property
        def is_invalid(self) -> bool:
            """Indicate whether this is the :const:`.INVALID` type."""
            return self is self.INVALID

    source_type: SourceType = field(default=SourceType.UNKNOWN)