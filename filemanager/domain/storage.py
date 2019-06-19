"""Defines protocol(s) for storage."""

import io
from typing import Any, Union, Iterator
from typing_extensions import Protocol


class IStorageAdapter(Protocol):
    """Responsible for providing a data access interface."""

    def create(self, workspace: 'UploadWorkspace', u_file: 'UploadedFile') -> None:
        """
        Create a file.

        Creates any non-existant directories in the path.
        """

    def makedirs(self, workspace: 'UploadWorkspace', path: str) -> None:
        """Make directories recursively for ``path`` if they don't exist."""
        ...

    def is_safe(self, workspace: 'UploadWorkspace', path: str,
                is_ancillary: bool = False, is_removed: bool = False,
                is_persisted: bool = False) -> bool:
        """Determine whether or not a path is safe to use."""
        ...

    def set_permissions(self, workspace: 'UploadWorkspace',
                        file_mode: int = 0o664, dir_mode: int = 0o775) -> None:
        """Set permissions for files and directories in a workspace."""
        ...

    def remove(self, workspace: 'UploadWorkspace',
               u_file: 'UploadedFile') -> None:
        """Remove a file."""
        ...

    def copy(self, workspace: 'UploadWorkspace', u_file: 'UploadedFile',
             new_file: 'UploadedFile') -> None:
        """Copy the contents of ``u_file`` into ``new_file``."""
        ...

    def move(self, workspace: 'UploadWorkspace', u_file: 'UploadedFile',
             from_path: str, to_path: str) -> None:
        """Move a file from one path to another."""
        ...

    def delete(self, workspace: 'UploadWorkspace',
               u_file: 'UploadedFile') -> None:
        """Permanently delete a file or directory."""
        ...

    def persist(self, workspace: 'UploadWorkspace',
                u_file: 'UploadedFile') -> None:
        """
        Persist a file.

        The file should be available on subsequent requests.
        """
        ...

    def get_full_path(self, workspace: 'UploadWorkspace',
                      u_file: 'UploadedFile') -> str:
        ...

    def open(self, workspace: 'UploadWorkspace', u_file: 'UploadedFile',
             flags: str = 'r', **kwargs: Any) -> Iterator[io.IOBase]:
        """
        Get an open file pointer to a file on disk.

        To be used as a context manager. For example:

        .. code-block:: python

           with storage.open(workspace, u_file) as f:
               f.read()

        """
        ...

    def is_tarfile(self, workspace: 'UploadWorkspace',
                   u_file: 'UploadedFile') -> bool:
        """Determine whether or not a file can be opened with ``tarfile``."""

    def get_path(self, workspace: 'UploadWorkspace',
                 u_file_or_path: Union[str, 'UploadedFile'],
                 is_ancillary: bool = False,
                 is_removed: bool = False,
                 is_persisted: bool = False) -> str:
        """Get the absolute path to an :class:`.UploadedFile`."""
        ...

    def cmp(self, workspace: 'UploadWorkspace', a_file: 'UploadedFile',
            b_file: 'UploadedFile', shallow: bool = True) -> bool:
        """Compare the contents of two files."""
        ...

    def getsize(self, workspace: 'UploadWorkspace',
                u_file: 'UploadedFile') -> int:
        """Get the size in bytes of a file."""
        ...
