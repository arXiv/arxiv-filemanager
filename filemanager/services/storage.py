"""On-disk storage for uploads."""

from typing import Any
import io
import os
import shutil
import filecmp
from pathlib import Path

from ..domain import UploadWorkspace, UploadedFile


class SimpleStorageAdapter:
    """Simple storage adapter for a workspace."""

    def __init__(self, base_path: str) -> None:
        """Initialize with a base path."""
        self._base_path = base_path
        if not os.path.exists(self._base_path):
            raise RuntimeError('Volume does not exist')

    def move(self, workspace: UploadWorkspace, u_file: UploadedFile,
             from_path: str, to_path: str) -> None:
        """Move a file from one path to another."""
        src_path = self._get_path_bare(from_path, u_file.is_persisted)
        dest_path = self._get_path_bare(to_path, u_file.is_persisted)
        parent, _ = os.path.split(dest_path)
        if not os.path.exists(parent):
            os.makedirs(parent)
        shutil.move(src_path, dest_path)

    def open(self, workspace: UploadWorkspace, u_file: UploadedFile,
             flags: str = 'r', **kwargs: Any) -> io.IOBase:
        """Get an open file pointer to a file on disk."""
        return open(self._get_path(workspace, u_file), flags, **kwargs)

    def _get_path(self, workspace: UploadWorkspace,
                  u_file: UploadedFile) -> str:
        return self._get_path_bare(workspace.get_path(u_file))

    def _get_path_bare(self, path: str, persisted: bool = True) -> str:
        return os.path.join(self._base_path, path)

    def persist(self, workspace: UploadWorkspace,
                u_file: UploadedFile) -> None:
        """Persist a file."""
        if not os.path.exists(self._get_path(workspace, u_file)):
            raise RuntimeError('File does not exist')
        u_file.is_persisted = True

    def cmp(self, workspace: UploadWorkspace, a_file: UploadedFile,
            b_file: UploadedFile, shallow: bool = True) -> bool:
        """Compare the contents of two files."""
        return filecmp.cmp(self._get_path(workspace, a_file),
                           self._get_path(workspace, b_file),
                           shallow=shallow)

    def create(self, workspace: UploadWorkspace, u_file: UploadedFile) -> None:
        """Create a file."""
        full_path = self._get_path(workspace, u_file)
        parent, _ = os.path.split(full_path)
        if not os.path.exists(parent):
            os.makedirs(parent)
        Path(full_path).touch()

    def copy(self, workspace: UploadWorkspace, u_file: UploadedFile,
             new_file: UploadedFile) -> None:
        """Copy the contents of ``u_file`` into ``new_file``."""
        shutil.copy(self._get_path(workspace, u_file),
                    self._get_path(workspace, new_file))

    def delete(self, workspace: UploadWorkspace, u_file: UploadedFile) -> None:
        """Delete a file or directory."""
        if u_file.is_directory:
            shutil.rmtree(self._get_path(workspace, u_file))
        else:
            os.unlink(self._get_path(workspace, u_file))

    def getsize(self, workspace: UploadWorkspace, u_file: UploadedFile) -> int:
        """Get the size in bytes of a file."""
        return os.path.getsize(self._get_path(workspace, u_file))


class QuarantineStorageAdapter(SimpleStorageAdapter):
    """Storage adapter that keeps un/persisted files in separate locations."""

    def __init__(self, base_path: str, quarantine_path: str) -> None:
        """Initialize with two distinct base paths."""
        self._base_path = base_path
        self._quarantine_path = quarantine_path
        if not os.path.exists(self._base_path):
            raise RuntimeError(f'Volume does not exist: {base_path}')
        if not os.path.exists(self._quarantine_path):
            raise RuntimeError(f'Volume does not exist: {quarantine_path}')

    def _get_permanent_path(self, path: str) -> str:
        return os.path.join(self._base_path, path)

    def _get_quarantine_path(self, path: str) -> str:
        return os.path.join(self._quarantine_path, path)

    def _get_path(self, workspace: UploadWorkspace,
                  u_file: UploadedFile) -> str:
        return self._get_path_bare(workspace.get_path(u_file),
                                   u_file.is_persisted)

    def _get_path_bare(self, path: str, persisted: bool = True) -> str:
        if persisted:
            return self._get_permanent_path(path)
        return self._get_quarantine_path(path)

    def persist(self, workspace: UploadWorkspace,
                u_file: UploadedFile) -> None:
        """Move a file or directory from quarantine to permanent storage."""
        src_path = self._get_quarantine_path(workspace.get_path(u_file))
        dst_path = self._get_permanent_path(workspace.get_path(u_file))
        parent, _ = os.path.split(dst_path)
        if not os.path.exists(parent):
            os.makedirs(parent)
        shutil.move(src_path, dst_path)
        u_file.is_persisted = True

        # Since we are working on a conventional file system, if we just copied
        # a directory then we have also copied all of its children. So we can
        # go ahead and mark those as persisted, too, in order to prevent
        # unnecessary i/o.
        if u_file.is_directory:
            for _path, _file in workspace.iter_children(u_file):
                if _path.startswith(u_file.path) and not _file.is_persisted:
                    _file.is_persisted = True
