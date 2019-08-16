"""Provides :class:`.Lockable`."""

from enum import Enum
from typing import Dict, Any

from dataclasses import dataclass, field
from typing_extensions import Protocol

from .base import IBaseWorkspace


class LockState(Enum):
    """Upload workspace lock states."""

    LOCKED = 'LOCKED'
    """
    Indicates upload workspace is locked and cannot be updated.

    The workspace might be locked during publish or when admins are
    updating uploaded files.
    """

    UNLOCKED = 'UNLOCKED'
    """
    Workspace is unlocked, updates are allowed.

    Workspace is normally in this state.
    """


class ILockable(Protocol):
    """Interface for lockable behavior."""

    lock_state: LockState

    @property
    def is_locked(self) -> bool:
        """Determine whether or not the workspace is locked."""


class ILockableWorkspace(IBaseWorkspace, ILockable, Protocol):
    """Interface for workspace with lockable behavior."""


@dataclass
class Lockable(ILockable):
    """Implements methods and properties related to locking/unlocking."""

    lock_state: LockState = field(default=LockState.UNLOCKED)
    """Lock state of upload workspace."""

    @classmethod
    def args_from_dict(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Pluck constructor args from dict representation of workspace."""
        return {'lock_state': LockState(data['lock_state'])}

    @classmethod
    def to_dict_impl(cls, self: 'Lockable') -> Dict[str, Any]:
        """Generate a dict representation of the workspace."""
        return {'lock_state': self.lock_state.value}

    @property
    def is_locked(self) -> bool:
        """Determine whether or not the workspace is locked."""
        return bool(self.lock_state == LockState.LOCKED)