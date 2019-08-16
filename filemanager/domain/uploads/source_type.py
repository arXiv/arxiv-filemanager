
from enum import Enum
from typing import Dict, Any

from dataclasses import dataclass, field
from typing_extensions import Protocol

from .base import IBaseWorkspace


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


class ISourceTypeable(Protocol):
    """Interface for source type behavior."""

    source_type: SourceType


class ISourceTypeableWorkspace(IBaseWorkspace, ISourceTypeable, Protocol):
    """Interface for workspace with source type behavior."""


@dataclass
class SourceTypeable(ISourceTypeable):

    source_type: SourceType = field(default=SourceType.UNKNOWN)

    @classmethod
    def args_from_dict(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Pluck constructor args from a dict representation."""
        return {'source_type': SourceType(data['source_type'])}

    @classmethod
    def to_dict_impl(cls, self: 'SourceTypeable') -> Dict[str, Any]:
        """Generate a dict representation of the workspace."""
        return {'source_type': self.source_type.value}