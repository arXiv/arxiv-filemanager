"""Provides :class:`.StatusMixin`."""

from enum import Enum

from dataclasses import dataclass, field


@dataclass
class StatusMixin:
    """Implements status-related methods and properties."""

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

    status: Status = field(default=Status.ACTIVE)
    """Status of upload workspace."""
    
    @property
    def is_active(self) -> bool:
        return bool(self.status == StatusMixin.Status.ACTIVE)
        
    @property
    def is_deleted(self) -> bool:
        return bool(self.status == StatusMixin.Status.DELETED)

    @property
    def is_released(self) -> bool:
        return bool(self.status == StatusMixin.Status.RELEASED)