"""Provides the content package."""

import io
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterator
from dataclasses import dataclass, field


@dataclass
class SourcePackage:
    """An archive containing an entire submission source package."""

    workspace: 'UploadWorkspace'
    """Workspace to which the source log belongs."""

    def __post_init__(self) -> None:
        self._path = f'{self.workspace.upload_id}.tar.gz'
        self._file = self.workspace.get(self._path, is_system=True)

    @property
    def is_stale(self) -> bool:
        """Indicates whether or not the source package is out of date."""
        return self.last_modified > self.workspace.last_modified

    @property
    def size_bytes(self) -> int:
        """Get the size of the source package in bytes."""
        return self.workspace.get_size_bytes(self._file)

    @property
    def last_modified(self) -> datetime:
        """Get the datetime when the source package was last modified."""
        return self.workspace.get_last_modified(self._file)

    @property
    def checksum(self) -> str:
        """Get the Base64-encoded MD5 hash of the source package."""
        return self.workspace.get_checksum(self._file)

    @contextmanager
    def open(self, flags: str = 'r', **kwargs: Any) -> Iterator[io.IOBase]:
        """
        Get an open file pointer to the source package.

        To be used as a context manager.
        """
        with self.workspace.open(self._file, flags, **kwargs) as f:
            yield f

    def pack(self) -> None:
        self.workspace.delete(self._file)
        self._file = \
            self.workspace.storage.pack_source(self.workspace, self._file)

    @property
    def full_path(self) -> str:
        return self.workspace.get_full_path(self._file)
