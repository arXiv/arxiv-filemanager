"""Describes the data that will be passed around inside of the service."""

from typing import List, Callable, Optional, Any, Type, Dict
import os
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
from typing_extensions import Protocol

from .file_type import FileType


class IChecker(Protocol):
    """A visitor that performs a check on an :class:`.UploadedFile`."""

    def __call__(self, workspace: 'UploadWorkspace',
                 uploaded_file: 'UploadedFile') -> None:
        """Check an :class:`.UploadedFile`."""
        ...


class ICheckingStrategy(Protocol):
    """Strategy for checking files in an :class:`.UploadWorkspace`."""

    def check(self, workspace: 'UploadWorkspace', *checkers: IChecker) -> None:
        """Perform checks on all files in the workspace."""
        ...


@dataclass
class UploadedFile:
    """Represents a single file in an upload workspace."""

    path: str
    """Path relative to the workspace in which the file resides."""

    size_bytes: int
    file_type: FileType = field(default=FileType.TYPE_UNKNOWN)
    is_removed: bool = field(default=False)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)
    _meta: Dict[str, Any] = field(default_factory=dict)
    """A register for checkers to store state between runs."""

    @property
    def name(self) -> str:
        """File name without path/directory info."""
        return os.path.basename(self.filepath)

    @property
    def ext(self) -> str:
        """Return file extension."""
        _, ext = os.path.splitext(self.filepath)
        return ext

    @property
    def dir(self) -> str:
        """Directory which contains the file. This is only used for files."""
        if os.path.isfile(self.filepath):
            return os.path.dirname(self.filepath)

        return ''

    @property
    def type_string(self) -> str:
        """Human-readable type name."""
        if self.removed:
            return "Invalid File"
        if self.dir:
            return self.file_type.name
        if self.dir == '' and self.path == 'anc':
            return 'Ancillary files directory'
        return 'Directory'


@dataclass
class UploadWorkspace:
    """All information about an upload."""

    # Various state settings

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

        READY = 'READY'
        """Overall state of workspace is good; no warnings/errors reported."""

        READY_WITH_WARNINGS = 'READY_WITH_WARNINGS'
        """
        Workspace is ready, but there are warnings for the user.

        Upload processing reported warnings which do not prohibit client
        from continuing on to compilation and submit steps.
        """

        ERRORS = 'ERRORS'
        """
        There were errors reported while processing upload files.

        Subsequent steps [compilation, submit, publish] should reject working
        with such an upload package.
        """

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

    upload_id: int
    """Unique ID for the upload workspace."""

    submission_id: str
    """
    Optionally associate upload workspace with submission_id.

    File Management Service 'upload_id' is independent and not directly
    tied to any external service.
    """

    owner_user_id: str
    """User id for owner of workspace."""

    archive: str
    """Target archive for this submission."."""

    created_datetime: datetime
    """When workspace was created"""

    modified_datetime: datetime
    """When workspace was last modified"""

    # Data about last upload

    lastupload_start_datetime: datetime
    """When we started processing last upload event."""

    lastupload_completion_datetime: datetime
    """When we completed processing last upload event."""

    lastupload_logs: str
    """Logs associated with last upload event."""

    lastupload_file_summary: str
    """Logs associated with last upload event."""

    lastupload_upload_status: str
    """Content eadiness status after last upload event."""

    # General state of upload

    state: Status
    """Status of upload workspace."""

    lock: LockState
    """Lock state of upload workspace."""

    checkers: List[IChecker]
    """File checkers that should be applied to all files in the workspace."""

    strategy: ICheckingStrategy
    """Strategy for performing file checks."""

    files: List[UploadedFile] = field(default_factory=list)
    """All of the files in this workspace."""

    def add_files(self, *uploaded_files: UploadedFile) -> None:
        """Add new :class:`.UploadedFile`s to this workspace."""
        self.files.extend(uploaded_files)
        self.strategy.check(self, self.checkers)
