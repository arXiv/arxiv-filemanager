"""On-disk storage for uploads."""

from typing import Any, Union, Iterator, Type, Dict, Tuple, IO
import io
import os
import tarfile
import zipfile
import shutil
import subprocess
import filecmp
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime

from pytz import UTC
from flask import Flask

from arxiv.base import logging
from ..domain import StoredWorkspace, UploadedFile, IStorageAdapter

logger = logging.getLogger(__name__)
logger.propagate = False


class SimpleStorageAdapter(IStorageAdapter):
    """Simple storage adapter for a workspace."""

    PARAMS: Tuple[str, ...] = ('base_path', )

    def __init__(self, base_path: str) -> None:
        """Initialize with a base path."""
        self._base_path = base_path
        self.deleted_logs_path = os.path.join(self._base_path,
                                               'deleted_workspace_logs')
        if not os.path.exists(self._base_path):
            raise RuntimeError('Volume does not exist')
        if not os.path.exists(self.deleted_logs_path):
            os.makedirs(self.deleted_logs_path)
        logger.debug('New SimpleStorageAdapter at %s', self._base_path)

    def makedirs(self, workspace: StoredWorkspace, path: str) -> None:
        """Make directories recursively for ``path``."""
        logger.debug('Make dirs to %s', path)
        abs_path = self.get_path_bare(path)
        if not os.path.exists(abs_path):
            os.makedirs(abs_path)

    def is_safe(self, workspace: StoredWorkspace, path: str,
                is_ancillary: bool = False, is_removed: bool = False,
                is_persisted: bool = False, is_system: bool = False,
                strict: bool = True) -> bool:
        """Determine whether or not a path is safe to use."""
        path_in_workspace = workspace.get_path(path, is_ancillary=is_ancillary,
                                               is_removed=is_removed,
                                               is_system=is_system)
        full_path = self.get_path_bare(path_in_workspace,
                                       is_persisted=is_persisted)
        try:
            self._check_safe(workspace, full_path, is_ancillary=is_ancillary,
                             is_removed=is_removed, is_persisted=is_persisted,
                             is_system=is_system, strict=strict)
        except ValueError:
            return False
        return True

    def _check_safe(self, workspace: StoredWorkspace, full_path: str,
                    is_ancillary: bool = False, is_removed: bool = False,
                    is_persisted: bool = False, is_system: bool = False,
                    strict: bool = True) -> None:
        if not strict or is_system:
            logger.debug('evaluate liberally: %s', full_path)
            wks_full_path = self.get_path_bare(workspace.base_path,
                                               is_persisted=is_persisted)
        elif is_ancillary:
            logger.debug('evaluate as ancillary: %s', full_path)
            wks_full_path = self.get_path_bare(workspace.ancillary_path,
                                                is_persisted=is_persisted)
        elif is_removed:
            logger.debug('evaluate as removed: %s', full_path)
            wks_full_path = self.get_path_bare(workspace.removed_path,
                                                is_persisted=is_persisted)
        else:
            logger.debug('evaluate as active source file: %s', full_path)
            wks_full_path = self.get_path_bare(workspace.source_path,
                                                is_persisted=is_persisted)
        logger.debug('Valid path (persisted=%s)? %s', is_persisted, full_path)
        if wks_full_path not in full_path:
            raise ValueError(f'Not a valid path for workspace: {full_path}')

    def set_permissions(self, workspace: StoredWorkspace,
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

    def remove(self, workspace: StoredWorkspace, u_file: UploadedFile) -> None:
        """Remove a file."""
        src_path = self.get_path_bare(workspace.get_path(u_file),
                                       u_file.is_persisted)
        dest_path = self.get_path_bare(
            workspace.get_path(u_file.path, is_removed=True),
            is_persisted=u_file.is_persisted
        )
        self._check_safe(workspace, src_path, is_ancillary=u_file.is_ancillary,
                         is_persisted=u_file.is_persisted)
        self._check_safe(workspace, dest_path, is_removed=True,
                         is_persisted=u_file.is_persisted)
        self._make_way(dest_path)
        shutil.move(src_path, dest_path)

    def _make_way(self, dest_path: str) -> None:
        """Prepare a path to receive moved/copied files."""
        logger.debug('make way at path: %s', dest_path)
        parent, _ = os.path.split(dest_path)
        if not os.path.exists(parent):
            os.makedirs(parent)

        if os.path.exists(dest_path):
            if os.path.isdir(dest_path):
                shutil.rmtree(dest_path)
            else:
                os.unlink(dest_path)

    def stash_deleted_log(self, workspace: StoredWorkspace,
                          u_file: UploadedFile) -> None:
        # Since every source log has the same filename we will prefix
        # upload identifier to log.
        padded_id = '{0:07d}'.format(workspace.upload_id)
        new_filename = padded_id + "_source.log"

        deleted_logs_path = os.path.join(self.deleted_logs_path, new_filename)
        shutil.move(u_file.full_path, deleted_logs_path)

    def move(self, workspace: StoredWorkspace, u_file: UploadedFile,
             from_path: str, to_path: str) -> None:
        """Move a file from one path to another."""
        src_path_rel = workspace.get_path(from_path,
                                          is_ancillary=u_file.is_ancillary,
                                          is_removed=u_file.is_removed)
        src_path = self.get_path_bare(src_path_rel, u_file.is_persisted)
        dest_path_rel = workspace.get_path(to_path,
                                           is_ancillary=u_file.is_ancillary,
                                           is_removed=u_file.is_removed)
        dest_path = self.get_path_bare(dest_path_rel, u_file.is_persisted)

        logger.debug('Move %s from %s to %s', u_file.path, from_path, to_path)
        logger.debug('%s -> %s', from_path, src_path)
        logger.debug('%s -> %s', to_path, dest_path)
        self._check_safe(workspace, src_path,
                         is_ancillary=u_file.is_ancillary,
                         is_removed=u_file.is_removed,
                         strict=False)
        self._check_safe(workspace, dest_path,
                         is_ancillary=u_file.is_ancillary,
                         is_removed=u_file.is_removed)
        parent, _ = os.path.split(dest_path)
        self._make_way(dest_path)
        shutil.move(src_path, dest_path)

    @contextmanager
    def open(self, workspace: StoredWorkspace, u_file: UploadedFile,
             flags: str = 'r', **kwargs: Any) -> Iterator[IO]:
        """Get an open file pointer to a file on disk."""
        with open(self.get_path(workspace, u_file), flags, **kwargs) as f:
            yield f

    def open_pointer(self, workspace: StoredWorkspace, u_file: UploadedFile,
                     flags: str = 'r', **kwargs: Any) -> IO[Any]:
        return open(self.get_path(workspace, u_file), flags, **kwargs)

    def is_tarfile(self, workspace: StoredWorkspace,
                   u_file: UploadedFile) -> bool:
        """Determine whether or not a file can be opened with ``tarfile``."""
        return tarfile.is_tarfile(self.get_path(workspace, u_file))

    def pack_tarfile(self, workspace: StoredWorkspace,
                    u_file: UploadedFile, path: str) -> UploadedFile:
        """
        Pack the contents of ``path`` into a gzipped tarball ``u_file``.

        Parameters
        ----------
        workspace : :class:`.StoredWorkspace`
            The workspace in which the contents and tarball reside.
        u_file : :class:`.UploadedFile`
            A file in ``workspace`` into which the contents of ``path`` should
            be packed.
        path : str
            Workspace path to contents that should be packed into ``u_file``.

        Returns
        -------
        :class:`.UploadedFile`
            The passed ``u_file``, with size and time properties updated.

        """
        # This uses the system ``tar`` command for performance reasons. The
        # built-in Python ``tarfile`` library is a pure-Python implementation.
        # It relies on the ``gzip`` library, which is also implemented in
        # Python. These are already far less performant than the system tar and
        # gzip routines, and this is further exascerbated by slower I/O on
        # networked filesystems. This is around 10x faster than the original
        # ``tarfile``-based implementation. --Erick 2019-07-10
        result = subprocess.Popen(['tar', '-czf',
                                   self.get_path(workspace, u_file),
                                   '-C', self.get_path_bare(path),
                                   '.']).wait()
        if result != 0:
            raise RuntimeError('tar exited with %i', result)
        u_file.size_bytes = self.get_size_bytes(workspace, u_file)
        u_file.last_modified = self.get_last_modified(workspace, u_file)
        return u_file

    def get_path(self, workspace: StoredWorkspace,
                 u_file_or_path: Union[str, UploadedFile],
                 is_ancillary: bool = False,
                 is_removed: bool = False,
                 is_persisted: bool = False,
                 is_system: bool = False) -> str:
        """Get the absolute path to an :class:`.UploadedFile`."""
        if isinstance(u_file_or_path, UploadedFile):
            is_ancillary = u_file_or_path.is_ancillary
            is_removed = u_file_or_path.is_removed
            is_persisted = u_file_or_path.is_persisted
            is_system = u_file_or_path.is_system
        path = self.get_path_bare(
            workspace.get_path(u_file_or_path, is_ancillary=is_ancillary,
                               is_removed=is_removed,
                               is_persisted=is_persisted,
                               is_system=is_system),
            is_persisted=is_persisted
        )
        self._check_safe(workspace, path, is_ancillary=is_ancillary,
                         is_removed=is_removed, is_persisted=is_persisted,
                         is_system=is_system)
        return path

    def get_path_bare(self, path: str, is_persisted: bool = True) -> str:
        return os.path.normpath(os.path.join(self._base_path, path))

    def persist(self, workspace: StoredWorkspace,
                u_file: UploadedFile) -> None:
        """Persist a file."""
        if not os.path.exists(self.get_path(workspace, u_file)):
            raise RuntimeError('File does not exist')
        u_file.is_persisted = True

    def cmp(self, workspace: StoredWorkspace, a_file: UploadedFile,
            b_file: UploadedFile, shallow: bool = True) -> bool:
        """Compare the contents of two files."""
        return filecmp.cmp(self.get_path(workspace, a_file),
                           self.get_path(workspace, b_file),
                           shallow=shallow)

    def create(self, workspace: StoredWorkspace, u_file: UploadedFile) -> None:
        """Create a file."""
        full_path = self.get_path(workspace, u_file)
        parent, _ = os.path.split(full_path)
        if not os.path.exists(parent):
            os.makedirs(parent)
            logger.debug('Made dirs to %s', parent)
        if u_file.is_directory and not os.path.exists(full_path):
            os.makedirs(full_path)
        else:
            Path(full_path).touch()
        logger.debug('Touched %s', full_path)

    def copy(self, workspace: StoredWorkspace, u_file: UploadedFile,
             new_file: UploadedFile) -> None:
        """Copy the contents of ``u_file`` into ``new_file``."""
        shutil.copy(self.get_path(workspace, u_file),
                    self.get_path(workspace, new_file))

    def delete(self, workspace: StoredWorkspace, u_file: UploadedFile,
               is_ancillary: bool = False,
               is_system: bool = False,
               is_persisted: bool = False) -> None:
        """Delete a file or directory."""
        path = self.get_path(workspace, u_file, is_ancillary=is_ancillary,
                             is_system=is_system, is_persisted=is_persisted)
        if u_file.is_directory:
            shutil.rmtree(path)
        else:
            os.unlink(path)

    def delete_path(self, workspace: StoredWorkspace, path: str) -> None:
        shutil.rmtree(self.get_path(workspace, path))

    def delete_all(self, workspace: StoredWorkspace) -> None:
        shutil.rmtree(self.get_path_bare(workspace.ancillary_path))
        shutil.rmtree(self.get_path_bare(workspace.source_path))

    def get_size_bytes(self, workspace: StoredWorkspace,
                       u_file: UploadedFile) -> int:
        """Get the size in bytes of a file."""
        return os.path.getsize(self.get_path(workspace, u_file))

    def get_last_modified(self, workspace: StoredWorkspace,
                          u_file: UploadedFile) -> datetime:
        _path = self.get_path(workspace, u_file)
        ts = datetime.utcfromtimestamp(os.path.getmtime(_path))
        return ts.replace(tzinfo=UTC)

    def set_last_modified(self, workspace: StoredWorkspace,
                          u_file: UploadedFile, modified: datetime) -> None:
        mtime = modified.timestamp()
        os.utime(self.get_path(workspace, u_file), (mtime, mtime))

    def delete_workspace(self, workspace: StoredWorkspace) -> None:
        """Completely delete a workspace and all of its contents."""
        shutil.rmtree(self.get_path_bare(workspace.base_path,
                                         is_persisted=True))


class QuarantineStorageAdapter(SimpleStorageAdapter):
    """Storage adapter that keeps un/persisted files in separate locations."""

    PARAMS = ('base_path', 'quarantine_path')

    def __init__(self, base_path: str, quarantine_path: str) -> None:
        """Initialize with two distinct base paths."""
        self._base_path = base_path
        self._quarantine_path = quarantine_path
        self.deleted_logs_path = os.path.join(self._base_path,
                                               'deleted_workspace_logs')
        if not os.path.exists(self._base_path):
            raise RuntimeError(f'Volume does not exist: {base_path}')
        if not os.path.exists(self._quarantine_path):
            raise RuntimeError(f'Volume does not exist: {quarantine_path}')
        if not os.path.exists(self.deleted_logs_path):
            os.makedirs(self.deleted_logs_path)

    def _get_permanent_path(self, path: str) -> str:
        return os.path.join(self._base_path, path)

    def _get_quarantine_path(self, path: str) -> str:
        return os.path.join(self._quarantine_path, path)

    def get_path_bare(self, path: str, is_persisted: bool = True) -> str:
        if is_persisted:
            return os.path.normpath(self._get_permanent_path(path))
        return os.path.normpath(self._get_quarantine_path(path))

    def set_permissions(self, workspace: StoredWorkspace,
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

    def persist(self, workspace: StoredWorkspace,
                u_file: UploadedFile) -> None:
        """Move a file or directory from quarantine to permanent storage."""
        src_path = self._get_quarantine_path(workspace.get_path(u_file))
        dst_path = self._get_permanent_path(workspace.get_path(u_file))
        self._check_safe(workspace, src_path,
                         is_ancillary=u_file.is_ancillary,
                         is_removed=u_file.is_removed,
                         is_system=u_file.is_system,
                         is_persisted=False)
        self._check_safe(workspace, dst_path,
                         is_ancillary=u_file.is_ancillary,
                         is_removed=u_file.is_removed,
                         is_system=u_file.is_system,
                         is_persisted=True)
        parent, _ = os.path.split(dst_path)
        if not os.path.exists(parent):
            os.makedirs(parent)
        logger.debug('Persist from %s to %s', src_path, dst_path)
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


ADAPTERS: Dict[str, Type[IStorageAdapter]] = {
    'simple': SimpleStorageAdapter,
    'quarantine': QuarantineStorageAdapter,
}


def init_app(app: Flask) -> None:
    app.config.setdefault('STORAGE_BACKEND', 'simple')


def create_adapter(app: Flask) -> IStorageAdapter:
    adapter_class = ADAPTERS[app.config['STORAGE_BACKEND']]
    values = [app.config[f'STORAGE_{param.upper()}']
              for param in adapter_class.PARAMS]
    return adapter_class(*values)
