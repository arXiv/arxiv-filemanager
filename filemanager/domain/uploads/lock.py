"""Provides :class:`.LockMixin`."""

from enum import Enum

from dataclasses import dataclass, field

@dataclass 
class LockMixin:
    """Implements methods and properties related to locking/unlocking."""

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

    lock_state: LockState = field(default=LockState.UNLOCKED)
    """Lock state of upload workspace."""
    
    @property
    def is_locked(self) -> bool:
        return bool(self.lock_state == LockMixin.LockState.LOCKED)