"""Provides :class:`.Statusable`."""

from enum import Enum
from typing import Dict, Any

from dataclasses import dataclass, field
from typing_extensions import Protocol

from .base import IBaseWorkspace


class Status(Enum):
    """Upload workspace statuses."""

    ACTIVE = 'ACTIVE'
    """Upload workspace is actively being used."""

    RELEASED = 'RELEASED'
    """
    Workspace is released and can be removed.

    Client/Admin/System indicate release to indicate upload workspace is no
    longer in use.
    """

    DELETED = 'DELETED'
    """
    Workspace is deleted (no files on disk).

    After upload workspace files are deleted the state of workspace in
    database is set to deleted. Database entry is retained indefinitely.
    """


class IStatusable(Protocol):
    """Interface for status behavior."""

    status: Status

    @property
    def is_active(self) -> bool:
        """Determine whether or not the workspace is active."""

    @property
    def is_deleted(self) -> bool:
        """Determine whether or not the workspace is deleted."""

    @property
    def is_released(self) -> bool:
        """Determine whether or not the workspace is released."""



class IStatusableWorkspace(IBaseWorkspace, IStatusable, Protocol):
    """Interface for workspace with status behavior."""


@dataclass
class Statusable(IStatusable):
    """Implements status-related methods and properties."""

    status: Status = field(default=Status.ACTIVE)
    """Status of upload workspace."""

    @classmethod
    def args_from_dict(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Pluck constructor args from a dict representation."""
        return {'status': Status(data['status'])}

    @classmethod
    def to_dict_impl(cls, self: 'Statusable') -> Dict[str, Any]:
        """Generate a dict representation."""
        return {'status': self.status.value}

    @property
    def is_active(self) -> bool:
        """Determine whether or not the workspace is active."""
        return bool(self.status == Status.ACTIVE)

    @property
    def is_deleted(self) -> bool:
        """Determine whether or not the workspace is deleted."""
        return bool(self.status == Status.DELETED)

    @property
    def is_released(self) -> bool:
        """Determine whether or not the workspace is released."""
        return bool(self.status == Status.RELEASED)

