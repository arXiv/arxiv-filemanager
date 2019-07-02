"""Provides :class:`.FileBaseWorkspace`."""

from typing import Optional, Any, IO, Iterator, Tuple, Union
from contextlib import contextmanager 
from datetime import datetime
from hashlib import md5
from base64 import urlsafe_b64encode

from pytz import UTC
from typing_extensions import Protocol

from dataclasses import dataclass, field

from ..uploaded_file import UploadedFile
from .paths import FilePathsWorkspace
from .util import modifies_workspace


class IStorageAdapter(Protocol):
    """Responsible for providing a data access interface."""

    PARAMS: Tuple[str, ...]
    deleted_logs_path: str

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize with implementation-specific configuration params."""
        ...

    def create(self, workspace: 'StoredWorkspace', u_file: UploadedFile) \
            -> None:
        """
        Create a file.

        Creates any non-existant directories in the path.
        """
        ...

    def makedirs(self, workspace: 'StoredWorkspace', path: str) -> None:
        """Make directories recursively for ``path`` if they don't exist."""
        ...

    def is_safe(self, workspace: 'StoredWorkspace', path: str,
                is_ancillary: bool = False, is_removed: bool = False,
                is_persisted: bool = False, is_system: bool = False,
                strict: bool = True) -> bool:
        """Determine whether or not a path is safe to use."""
        ...

    def set_permissions(self, workspace: 'StoredWorkspace',
                        file_mode: int = 0o664, dir_mode: int = 0o775) -> None:
        """Set permissions for files and directories in a workspace."""
        ...

    def get_last_modified(self, workspace: 'StoredWorkspace',
                          u_file: UploadedFile) -> datetime:
        """Get the datetime when a file was last modified."""
        ...

    def set_last_modified(self, workspace: 'StoredWorkspace', 
                          u_file: UploadedFile, modified: datetime) -> None:
        """Set the modification datetime on a file."""
        ...

    def remove(self, workspace: 'StoredWorkspace',
               u_file: UploadedFile) -> None:
        """Remove a file."""
        ...

    def copy(self, workspace: 'StoredWorkspace', u_file: UploadedFile,
             new_file: UploadedFile) -> None:
        """Copy the contents of ``u_file`` into ``new_file``."""
        ...

    def move(self, workspace: 'StoredWorkspace', u_file: UploadedFile,
             from_path: str, to_path: str) -> None:
        """Move a file from one path to another."""
        ...

    def delete(self, workspace: 'StoredWorkspace',
               u_file: UploadedFile) -> None:
        """Permanently delete a file or directory."""
        ...
    
    def delete_all(self, workspace: 'StoredWorkspace') -> None:
        """Delete all files in the workspace."""
        ...
    
    def delete_workspace(self, workspace: 'StoredWorkspace') -> None:
        """Completely delete a workspace and all of its contents."""
        ...

    def persist(self, workspace: 'StoredWorkspace',
                u_file: UploadedFile) -> None:
        """
        Persist a file.

        The file should be available on subsequent requests.
        """
        ...

    def get_full_path(self, workspace: 'StoredWorkspace',
                      u_file: UploadedFile) -> str:
        ...

    @contextmanager
    def open(self, workspace: 'StoredWorkspace', u_file: UploadedFile,
             flags: str = 'r', **kwargs: Any) -> Iterator[IO]:
        """
        Get an open file pointer to a file on disk.

        To be used as a context manager. For example:

        .. code-block:: python

           with storage.open(workspace, u_file) as f:
               f.read()

        """
        ...

    def open_pointer(self, workspace: 'StoredWorkspace', 
                     u_file: UploadedFile, flags: str = 'r', **kwargs: Any) \
            -> IO[Any]:
        """Get an open file pointer to a file on disk."""
        ...

    def is_tarfile(self, workspace: 'StoredWorkspace',
                   u_file: UploadedFile) -> bool:
        """Determine whether or not a file can be opened with ``tarfile``."""

    def get_path(self, workspace: 'StoredWorkspace',
                 u_file_or_path: Union[str, UploadedFile],
                 is_ancillary: bool = False,
                 is_removed: bool = False,
                 is_persisted: bool = False,
                 is_system: bool = False) -> str:
        """Get the absolute path to an :class:`.UploadedFile`."""

    def cmp(self, workspace: 'StoredWorkspace', a_file: UploadedFile,
            b_file: UploadedFile, shallow: bool = True) -> bool:
        """Compare the contents of two files."""
        ...

    def getsize(self, workspace: 'StoredWorkspace',
                u_file: UploadedFile) -> int:
        """Get the size in bytes of a file."""
        ...
    
    def stash_deleted_log(self, workspace: 'StoredWorkspace', 
                          u_file: UploadedFile) -> None:
        ...
    
    def pack_tarfile(self, workspace: 'StoredWorkspace',
                    u_file: UploadedFile, path: str) -> UploadedFile:
        """Pack ``path`` into ``u_file`` as a tarball."""
        ...


@dataclass
class StoredWorkspace(FilePathsWorkspace):
    """Adds basic storage-backed file operations."""

    storage: Optional[IStorageAdapter] = field(default=None)
    """Adapter for persistence."""

    lastupload_start_datetime: Optional[datetime] = field(default=None)
    """When we started processing last upload event."""

    lastupload_completion_datetime: Optional[datetime] = field(default=None)
    """When we completed processing last upload event."""

    lastupload_logs: str = field(default_factory=str)
    """Logs associated with last upload event."""

    lastupload_file_summary: str = field(default_factory=str)
    """Logs associated with last upload event."""

    @contextmanager
    @modifies_workspace()
    def open(self, u_file: UploadedFile, flags: str = 'r', **kwargs: Any) \
            -> Iterator[IO]:
        """Get a file pointer for a :class:`.UploadFile`."""
        if self.storage is None:
            raise RuntimeError('Storage adapter is not set')
        if not self.files.contains(u_file.path,
                                   is_ancillary=u_file.is_ancillary,
                                   is_system=u_file.is_system,
                                   is_removed=u_file.is_removed):
            raise ValueError('No such file')
        with self.storage.open(self, u_file, flags, **kwargs) as f:
            yield f
        self.get_size_bytes(u_file)
        self.get_last_modified(u_file)

    def open_pointer(self, u_file: UploadedFile, flags: str = 'r', 
                     **kwargs: Any) -> IO:
        if self.storage is None:
            raise RuntimeError('Storage adapter is not set')
        return self.storage.open_pointer(self, u_file, flags, **kwargs)

    def cmp(self, a_file: UploadedFile, 
            b_file: UploadedFile, shallow: bool = True) -> bool:
        """Compare the contents of two files."""
        if self.storage is None:
            raise RuntimeError('Storage adapter is not set')
        return self.storage.cmp(self, a_file, b_file, shallow=shallow)
    
    def is_tarfile(self, u_file: UploadedFile) -> bool:
        """Determine whether or not a file is a tarfile."""
        if self.storage is None:
            raise RuntimeError('Storage adapter is not set')
        return self.storage.is_tarfile(self, u_file)
    
    def get_size_bytes(self, u_file: UploadedFile) -> int:
        """Get (and update) the size in bytes of a file."""
        if self.storage is None:
            raise RuntimeError('Storage adapter is not set')
        size_bytes: int = self.storage.get_size_bytes(self, u_file)
        u_file.size_bytes = size_bytes
        return size_bytes

    def get_last_modified(self, u_file: UploadedFile) -> datetime:
        """Get the datetime when a :class:`.UploadedFile` was last modified."""
        if self.storage is None:
            raise RuntimeError('Storage adapter is not set')
        u_file.last_modified = self.storage.get_last_modified(self, u_file)
        return u_file.last_modified
    
    def set_last_modified(self, u_file: UploadedFile, 
                          modified: Optional[datetime] = None) -> None:
        """Set the last modified time on a :class:`UploadedFile`."""
        if self.storage is None:
            raise RuntimeError('Storage adapter is not set')
        if modified is None:
            modified = datetime.now(UTC)
        self.storage.set_last_modified(self, u_file, modified)
        
    def get_checksum(self, u_file: UploadedFile) -> str:
        """Get the urlsafe base64-encoded MD5 hash of the file contents."""
        hash_md5 = md5()
        with self.open(u_file, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return urlsafe_b64encode(hash_md5.digest()).decode('utf-8')
    
    def is_safe(self, path: str, is_ancillary: bool = False, 
                is_removed: bool = False, is_persisted: bool = False, 
                is_system: bool = False, strict: bool = True) -> bool:
        """Determine whether or not a path is safe to use in this workspace."""
        if self.storage is None:
            raise RuntimeError('No storage adapter set on workspace')
        return self.storage.is_safe(self, path, is_ancillary=is_ancillary, 
                                    is_removed=is_removed, 
                                    is_persisted=is_persisted,
                                    is_system=is_system, strict=strict)
    
    def get_full_path(self, u_file_or_path: Union[str, UploadedFile],
                      is_ancillary: bool = False, is_removed: bool = False,
                      is_persisted: bool = False, is_system: bool = False) \
            -> str:
        """Get the absolute path to a :class:`.UploadedFile`."""
        if self.storage is None:
            raise RuntimeError('No storage adapter set on workspace')
        return self.storage.get_path(self, u_file_or_path,
                                     is_ancillary=is_ancillary,
                                     is_removed=is_removed,
                                     is_persisted=is_persisted,
                                     is_system=is_system)
    
    def pack_source(self, u_file: UploadedFile) -> UploadedFile:
        """Pack the source + ancillary content of a workspace as a tarball."""
        if self.storage is None:
            raise RuntimeError('No storage adapter set on workspace')
        return self.storage.pack_tarfile(self, u_file, self.source_path)
        