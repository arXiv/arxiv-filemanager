"""On-disk storage for uploads."""

from typing import Any, Union
import io
import os
import tarfile
import zipfile
import shutil
import filecmp
from pathlib import Path

from arxiv.base import logging

from ..domain import UploadWorkspace, UploadedFile

logger = logging.getLogger(__name__)
logger.propagate = False


class SimpleStorageAdapter:
    """Simple storage adapter for a workspace."""

    def __init__(self, base_path: str) -> None:
        """Initialize with a base path."""
        self._base_path = base_path
        if not os.path.exists(self._base_path):
            raise RuntimeError('Volume does not exist')
        logger.debug('New SimpleStorageAdapter at %s', self._base_path)

    def is_safe(self, workspace: UploadWorkspace, path: str,
                is_ancillary: bool = False, is_removed: bool = False) -> bool:
        """Determine whether or not a path in a workspace is safe to use."""
        path_in_workspace = workspace.get_path(path, is_ancillary, is_removed)
        full_path = self._get_path_bare(path_in_workspace)
        try:
            self._check_safe(workspace, full_path, is_ancillary, is_removed)
        except ValueError:
            return False
        return True

    def _check_safe(self, workspace: UploadWorkspace, full_path: str,
                    is_ancillary: bool = False, is_removed: bool = False,
                    strict: bool = True) -> None:
        if not strict:
            workspace_full_path = self._get_path_bare(workspace.base_path)
        elif is_ancillary:
            workspace_full_path = self._get_path_bare(workspace.ancillary_path)
        elif is_removed:
            workspace_full_path = self._get_path_bare(workspace.removed_path)
        else:
            workspace_full_path = self._get_path_bare(workspace.source_path)
        if workspace_full_path not in full_path:
            raise ValueError(f'Not a valid path for workspace: {full_path}')

    def set_permissions(self, workspace: UploadWorkspace,
                        file_mode: int = 0o664, dir_mode: int = 0o775) -> None:
        """
        Set the file permissions for all uploaded files and directories.

        Applies to files and directories in submitter's upload source
        directory.
        """
        for u_file in workspace.iter_files(allow_directories=True):
            if u_file.is_directory:
                os.chmod(self.get_path(workspace, u_file), dir_mode)
            else:
                os.chmod(self.get_path(workspace, u_file), file_mode)

    def remove(self, workspace: UploadWorkspace, u_file: UploadedFile) -> None:
        """Remove a file."""
        src_path = self._get_path_bare(workspace.get_path(u_file),
                                       u_file.is_persisted)
        dest_path = self._get_path_bare(workspace.get_path(u_file.path,
                                                           is_removed=True),
                                        u_file.is_persisted)
        self._check_safe(workspace, src_path, is_ancillary=u_file.is_ancillary)
        self._check_safe(workspace, dest_path, is_removed=True)
        parent, _ = os.path.split(dest_path)
        if not os.path.exists(parent):
            os.makedirs(parent)
        shutil.move(src_path, dest_path)
        u_file.is_removed = True

    def move(self, workspace: UploadWorkspace, u_file: UploadedFile,
             from_path: str, to_path: str) -> None:
        """Move a file from one path to another."""
        src_path = self._get_path_bare(workspace.get_path(from_path),
                                       u_file.is_persisted)
        dest_path = self._get_path_bare(workspace.get_path(to_path),
                                        u_file.is_persisted)
        self._check_safe(workspace, src_path, u_file.is_ancillary,
                         u_file.is_removed, strict=False)
        self._check_safe(workspace, dest_path, u_file.is_ancillary,
                         u_file.is_removed)
        parent, _ = os.path.split(dest_path)
        if not os.path.exists(parent):
            os.makedirs(parent)
        shutil.move(src_path, dest_path)

    def open(self, workspace: UploadWorkspace, u_file: UploadedFile,
             flags: str = 'r', **kwargs: Any) -> io.IOBase:
        """Get an open file pointer to a file on disk."""
        return open(self.get_path(workspace, u_file), flags, **kwargs)

    def is_tarfile(self, workspace: UploadWorkspace,
                   u_file: UploadedFile) -> bool:
        """Determine whether or not a file can be opened with ``tarfile``."""
        return tarfile.is_tarfile(self.get_path(workspace, u_file))

    def get_path(self, workspace: UploadWorkspace,
                 u_file_or_path: Union[str, UploadedFile],
                 is_ancillary: bool = False,
                 is_removed: bool = False) -> str:
        """Get the absolute path to an :class:`.UploadedFile`."""
        path = self._get_path_bare(workspace.get_path(u_file_or_path))
        if isinstance(u_file_or_path, UploadedFile):
            is_ancillary = u_file_or_path.is_ancillary
            is_removed = u_file_or_path.is_removed
        self._check_safe(workspace, path, is_ancillary, is_removed)
        return path

    def _get_path_bare(self, path: str, persisted: bool = True) -> str:
        return os.path.normpath(os.path.join(self._base_path, path))

    def persist(self, workspace: UploadWorkspace,
                u_file: UploadedFile) -> None:
        """Persist a file."""
        if not os.path.exists(self.get_path(workspace, u_file)):
            raise RuntimeError('File does not exist')
        u_file.is_persisted = True

    def cmp(self, workspace: UploadWorkspace, a_file: UploadedFile,
            b_file: UploadedFile, shallow: bool = True) -> bool:
        """Compare the contents of two files."""
        return filecmp.cmp(self.get_path(workspace, a_file),
                           self.get_path(workspace, b_file),
                           shallow=shallow)

    def create(self, workspace: UploadWorkspace, u_file: UploadedFile) -> None:
        """Create a file."""
        full_path = self.get_path(workspace, u_file)
        parent, _ = os.path.split(full_path)
        if not os.path.exists(parent):
            os.makedirs(parent)
        Path(full_path).touch()

    def copy(self, workspace: UploadWorkspace, u_file: UploadedFile,
             new_file: UploadedFile) -> None:
        """Copy the contents of ``u_file`` into ``new_file``."""
        shutil.copy(self.get_path(workspace, u_file),
                    self.get_path(workspace, new_file))

    def delete(self, workspace: UploadWorkspace, u_file: UploadedFile) -> None:
        """Delete a file or directory."""
        if u_file.is_directory:
            shutil.rmtree(self.get_path(workspace, u_file))
        else:
            os.unlink(self.get_path(workspace, u_file))

    def getsize(self, workspace: UploadWorkspace, u_file: UploadedFile) -> int:
        """Get the size in bytes of a file."""
        return os.path.getsize(self.get_path(workspace, u_file))


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

    def _get_path_bare(self, path: str, persisted: bool = True) -> str:
        if persisted:
            return self._get_permanent_path(path)
        return self._get_quarantine_path(path)

    def set_permissions(self, workspace: UploadWorkspace,
                        file_mode: int = 0o664, dir_mode: int = 0o775) -> None:
        """
        Set the file permissions for all uploaded files and directories.

        Applies to files and directories in submitter's upload source
        directory.
        """
        for u_file in workspace.iter_files(allow_directories=True):
            if u_file.is_persisted:     # Skip persisted content.
                continue
            if u_file.is_directory:
                os.chmod(self.get_path(workspace, u_file), dir_mode)
            else:
                os.chmod(self.get_path(workspace, u_file), file_mode)

    def persist(self, workspace: UploadWorkspace,
                u_file: UploadedFile) -> None:
        """Move a file or directory from quarantine to permanent storage."""
        src_path = self._get_quarantine_path(workspace.get_path(u_file))
        dst_path = self._get_permanent_path(workspace.get_path(u_file))
        self._check_safe(workspace, src_path, u_file.is_ancillary,
                         u_file.is_removed)
        self._check_safe(workspace, dst_path, u_file.is_ancillary,
                         u_file.is_removed)
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
