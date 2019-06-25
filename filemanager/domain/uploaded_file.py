"""Provides :class:`UploadedFile`."""

import os
from typing import Optional, List, Dict, Any
from datetime import datetime
from functools import partial

from pytz import UTC
from dataclasses import dataclass, field

from .file_type import FileType


@dataclass
class UploadedFile:
    """Represents a single file in an upload workspace."""

    workspace: 'UploadWorkspace'
    """The workspace to which this file belongs."""

    path: str
    """Path relative to the workspace in which the file resides."""

    size_bytes: int
    """Size of the file in bytes."""

    file_type: FileType = field(default=FileType.UNKNOWN)
    """The content type of the file."""

    is_removed: bool = field(default=False)
    """
    Indicates whether or not this file has been removed.

    Removed files are retained, but moved outside of the source package and
    are therefore generally not mutable by clients.
    """

    is_ancillary: bool = field(default=False)
    """Indicates whether or not this file is an ancillary file."""

    is_directory: bool = field(default=False)
    """Indicates whether or not this file is a directory."""

    is_checked: bool = field(default=False)
    """Indicates whether or not this file has been subjected to all checks."""

    is_persisted: bool = field(default=False)
    """
    Indicates whether or not this file has been persisted.

    Non-persisted files will generally not live beyond a single request
    context.
    """

    is_system: bool = field(default=False)
    """
    Indicates whether or not this is a system file.

    System files are not part of the source package, and usually not directly
    mutable by clients.
    """

    last_modified: datetime = field(default_factory=partial(datetime.now, UTC))

    reason_for_removal: Optional[str] = field(default=None)
    errors: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Make sure that directory paths end with '/'."""
        if self.is_directory and not self.path.endswith('/'):
            self.path += '/'

    @property
    def name(self) -> str:
        """File name without path/directory info."""
        if '/' in self.path.strip('/'):
            return os.path.basename(self.path)
        return self.path

    @property
    def name_sans_ext(self) -> str:
        """File name without extension."""
        return os.path.splitext(self.path)[0]

    @property
    def ext(self) -> str:
        """Return file extension."""
        _, ext = os.path.splitext(self.path)
        return ext.lstrip('.')

    @property
    def dir(self) -> str:
        """
        Directory which contains the file.

        Should end with ``/`` but not begin with ``/``.
        """
        return f'{os.path.dirname(self.path)}/'.lstrip('/')

    @property
    def type_string(self) -> str:
        """Human-readable type name."""
        if self.is_removed:
            return "Invalid File"
        if self.is_directory:
            if self.path == 'anc/':
                return 'Ancillary files directory'
            return 'Directory'
        return self.file_type.name

    @property
    def is_always_ignore(self) -> bool:
        """Determine whether or not this file should be ignored."""
        return self.file_type is FileType.ALWAYS_IGNORE

    @property
    def is_empty(self) -> bool:
        """Indicate whether this file is an empty file."""
        return self.size_bytes == 0

    @property
    def is_active(self) -> bool:
        """Indicate whether or not this file is part of the primary source."""
        return not any((self.is_ancillary, self.is_removed, self.is_system))

    @property
    def full_path(self) -> str:
        """Absolute path to this file."""
        return self.workspace.get_full_path(self)
    
    @property
    def checksum(self) -> str:
        """Base64-endocded MD5 hash of the file contents."""
        return self.workspace.get_checksum(self)
