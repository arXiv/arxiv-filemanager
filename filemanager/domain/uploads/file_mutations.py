"""Provides :class:`.FileMutationsMixin`."""

import re
import os
import io
import logging
from typing import Optional, List, Union, Iterable, Tuple, IO, Iterator, Any
from itertools import accumulate
from datetime import datetime
from contextlib import contextmanager

from dataclasses import dataclass, field

from ..index import FileIndex

from ..uploaded_file import UploadedFile
from ..error import Error
from ..file_type import FileType

from .stored import IStorageAdapter
from .translatable import TranslatableWorkspace
from .util import modifies_workspace, logger


@dataclass
class FileMutationsWorkspace(TranslatableWorkspace):
    """
    Adds methods that alter files.

    Introduces the source package.
    """

    LEADING_DOTSLASH = re.compile(r'^\./')
    """Pattern to match leading ``./`` in relative paths."""

    def initialize(self) -> None:
        self.source_package = SourcePackage(self, f'{self.upload_id}.tar.gz')
        self.log = SourceLog(self, 'source.log')


    @modifies_workspace()
    def create(self, path: str, file_type: FileType = FileType.UNKNOWN,
               replace: bool = False, is_directory: bool = False,
               is_ancillary: Optional[bool] = None, is_system: bool = False,
               is_persisted: bool = False, touch: bool = True) -> UploadedFile:
        """Create a new :class:`.UploadedFile` at ``path``."""
        if self.storage is None:
            raise RuntimeError('No storage adapter available')
        path = self.LEADING_DOTSLASH.sub('', path)

        # if self.files.contains(path, is_ancillary=is_ancillary,
        #                        is_system=is_system):
        #     e_file = self.files.get(path, is_ancillary=is_ancillary,
        #                             is_system=is_system)
        #     if e_file.is_directory:
        #         raise ValueError('Directory exists at that path')

        if is_ancillary is None:    # Infer whether this is an ancillary file.
            path, is_ancillary = self._check_is_ancillary_path(path)

        u_file = UploadedFile(self, path=path, size_bytes=0,
                              file_type=file_type,
                              is_directory=is_directory,
                              is_ancillary=is_ancillary,
                              is_system=is_system,
                              is_persisted=is_persisted)

        # Make sure that we have references for the parent director(y|ies).
        parts = u_file.path.split('/')
        for parent in accumulate(parts[:-1], lambda *p: os.path.join(*p)):
            parent += '/'
            if not self.exists(parent):
                parent_file = UploadedFile(self, path=parent, size_bytes=0,
                                           file_type=FileType.DIRECTORY,
                                           is_directory=True,
                                           is_ancillary=is_ancillary,
                                           is_system=is_system,
                                           is_persisted=is_persisted)
                self.files.set(parent_file.path, parent_file)
                if touch:
                    self.storage.create(self, parent_file)

        self.files.set(u_file.path, u_file)

        if touch:
            self.storage.create(self, u_file)
        else:
            self.set_last_modified(u_file)
            self.get_size_bytes(u_file)
            self.get_last_modified(u_file)
        return u_file

    @modifies_workspace()
    def delete(self, u_file: UploadedFile) -> None:
        """
        Completely delete a file.

        See also :func:`UploadWorkspace.remove`.
        """
        if self.storage is None:
            raise RuntimeError('Storage adapter is not set')
        logger.debug('Delete file %s', u_file.path)
        self.storage.delete(self, u_file)
        self._drop_refs(u_file.path, is_ancillary=u_file.is_ancillary,
                        is_system=u_file.is_system,
                        is_removed=u_file.is_removed)
        if u_file.is_directory:
            for child_path, child_file in self.iter_children(u_file):
                self._drop_refs(child_path)

    @modifies_workspace()
    def delete_all_files(self) -> None:
        """Delete all source and ancillary files in the workspace."""
        if self.storage is None:
            raise RuntimeError('Storage adapter is not set')
        self.storage.delete_all(self)
        self.files.source.clear()
        self.files.ancillary.clear()
        self.storage.makedirs(self, self.source_path)
        self.storage.makedirs(self, self.ancillary_path)

    @modifies_workspace()
    def copy(self, u_file: UploadedFile, new_path: str,
             replace: bool = False) -> UploadedFile:
        """Make a copy of a file."""
        if self.storage is None:
            raise RuntimeError('Storage adapter is not set')
        if self.files.contains(new_path, is_ancillary=u_file.is_ancillary,
                               is_removed=u_file.is_removed,
                               is_system=u_file.is_system):
            existing_file = self.files.get(new_path,
                                           is_ancillary=u_file.is_ancillary,
                                           is_removed=u_file.is_removed,
                                           is_system=u_file.is_system)
            if existing_file.is_directory:
                raise ValueError('Directory exists at that path')
            # if not replace:
            #     raise ValueError('File at that path already exists')
        new_file = UploadedFile(self, path=new_path,
                                size_bytes=u_file.size_bytes,
                                file_type=u_file.file_type,
                                is_ancillary=u_file.is_ancillary,
                                is_removed=u_file.is_removed,
                                is_checked=u_file.is_checked,
                                is_system=u_file.is_system)
        self.storage.copy(self, u_file, new_file)
        self.files.set(new_path, new_file)
        return new_file

    @modifies_workspace()
    def replace(self, to_replace: UploadedFile,
                replace_with: UploadedFile, keep_refs: bool = True) \
            -> UploadedFile:
        """Replace a file with another file."""
        if self.storage is None:
            raise RuntimeError('Storage adapter is not set')
        self.storage.move(self, replace_with, replace_with.path,
                          to_replace.path)

        if keep_refs:
            for error in to_replace.errors:
                replace_with.add_error(error)

        self._drop_refs(to_replace.path)
        old_path = replace_with.path
        replace_with.path = to_replace.path
        self._update_refs(replace_with, old_path)

        # If the file is a directory, we are counting on storage to have moved
        # both the directory itself along with all of its children. But we must
        # still update all of our path-based references to reflect this change.
        if replace_with.is_directory:
            for _former_path, _file in self.iter_children(replace_with):
                _new_path = os.path.join(to_replace.path.rstrip('/'),
                                         _former_path.split(old_path, 1)[1])
                _file.path = _new_path
                if not keep_refs:
                    self._drop_refs(_new_path)
                self._update_refs(_file, _former_path)

        # TODO: update info for target children if target was a directory.
        return replace_with

    @modifies_workspace()
    def remove(self, u_file: UploadedFile,
               reason: Optional[str] = None) -> None:
        """
        Mark a file as removed, and quarantine.

        This is not the same as deletion.
        """
        if self.storage is None:
            raise RuntimeError('Storage adapter is not set')
        if reason is None:
            reason = f"Removed file '{u_file.name}'."
        logger.debug('Remove file %s: %s', u_file.path, reason)
        self.storage.remove(self, u_file)

        if u_file.is_directory:
            for former_path, _file in self.iter_children(u_file):
                _file.is_removed = True
                self._drop_refs(_file.path, is_ancillary=_file.is_ancillary,
                                is_removed=False, is_system=_file.is_system)
                self.files.set(_file.path, _file)

        u_file.is_removed = True
        u_file.reason_for_removal = reason

        self.add_error(u_file, reason, severity=Error.Severity.INFO,
                       is_persistant=False)

        self._drop_refs(u_file.path, is_ancillary=u_file.is_ancillary,
                        is_removed=False, is_system=u_file.is_system)
        self.files.set(u_file.path, u_file)

    @modifies_workspace()
    def persist(self, u_file: UploadedFile) -> None:
        if self.storage is None:
            raise RuntimeError('Storage adapter is not set')
        self.storage.persist(self, u_file)

    @modifies_workspace()
    def persist_all(self) -> None:
        for u_file in self.iter_files(allow_system=True):
            if not u_file.is_persisted:
                self.persist(u_file)

    @modifies_workspace()
    def rename(self, u_file: UploadedFile,
               new_path: str) -> None:
        """Rename a file in this workspace."""
        if self.storage is None:
            raise RuntimeError('Storage adapter is not set')
        logger.debug('Rename %s to %s (ancillary = %s)',
                     u_file.path, new_path, u_file.is_ancillary)
        former_path = u_file.path
        u_file.path = new_path
        self.storage.move(self, u_file, former_path, u_file.path)
        self._update_refs(u_file, former_path)

        # If the file is a directory, we are counting on storage to have moved
        # both the directory itself along with all of its children. But we must
        # still update all of our path-based references to reflect this change.
        if u_file.is_directory:
            for _former_path, _file in self.iter_children(u_file):
                _new_path = os.path.join(new_path.rstrip('/'),
                                         _former_path.split(former_path, 1)[1])
                _file.path = _new_path
                self._update_refs(_file, _former_path)

    @modifies_workspace()
    def add_files(self, *u_files: UploadedFile) -> None:
        """Add new :class:`.UploadedFile`s to this workspace."""
        if self.storage is None:
            raise RuntimeError('Storage adapter is not set')
        for u_file in u_files:
            parts = u_file.path.split('/')
            for parent in accumulate(parts[:-1], lambda *p: os.path.join(*p)):
                parent += '/'
                if not self.exists(parent):
                    self.create(parent, FileType.DIRECTORY, is_directory=True)
            self.files.set(u_file.path, u_file)

    @modifies_workspace()
    def delete_workspace(self) -> bool:
        """
        Complete delete the upload workspace.

        This completely removes the upload workspace directory. No backup is
        made here (system backups may have files for period of time).

        Returns
        -------
        bool
            True if source log was saved and workspace deleted.

        """
        if self.storage is None:
            raise RuntimeError('Storage adapter is not set')

        # Think about stashing source.log, otherwise any logging is fruitless
        # since we are deleting all files under workspace.
        # Let's stash a copy of the source.log file (if it exists)
        self._stash_log()

        # Now blow away the workspace
        self.storage.delete_workspace(self)
        return True

    def _stash_log(self) -> None:
        """Copy the workspace log to the deleted logs directory."""
        if self.storage is None:
            raise RuntimeError('Storage adapter is not set')
        self.log.info(f"Move source log for {self.upload_id} to"
                      f" '{self.storage.deleted_logs_path}'.")
        self.log.info(f"Delete workspace '{self.upload_id}'.")
        try:
            self.storage.stash_deleted_log(self, self.log.file)
        except Exception as e:
            self.log.info(f'Saving source.log failed: {e}')


@dataclass
class _SpecialSystemFile:
    """Some system files have specific and unique semantics."""

    workspace: FileMutationsWorkspace
    """Workspace to which the special system file belongs."""

    path: str
    """Relative path to the system file within the containing workspace."""

    _file: Optional[UploadedFile] = None

    @property
    def file(self) -> UploadedFile:
        """Create the underlying file if it does not already exist."""
        if self._file is None:
            if self.workspace.exists(self.path, is_system=True):
                self._file = self.workspace.get(self.path, is_system=True)
            else:
                self._file  = self.workspace.create(self.path, is_system=True,
                                                is_persisted=True, touch=True)
        return self._file


    @property
    def name(self) -> str:
        """File name."""
        name: str = self.file.name
        return name

    @property
    def size_bytes(self) -> int:
        """Get the size of the file in bytes."""
        return self.workspace.get_size_bytes(self.file)

    @property
    def last_modified(self) -> datetime:
        """Get the datetime when the file was last modified."""
        return self.workspace.get_last_modified(self.file)

    @property
    def checksum(self) -> str:
        """Get the Base64-encoded MD5 hash of the file."""
        return self.workspace.get_checksum(self.file)

    @contextmanager
    def open(self, flags: str = 'r', **kwargs: Any) -> Iterator[IO]:
        """
        Get an open file pointer to the file.

        To be used as a context manager.
        """
        with self.workspace.open(self.file, flags, **kwargs) as f:
            yield f

    def open_pointer(self, flags: str = 'r', **kwargs: Any) -> IO:
        return self.workspace.open_pointer(self.file, flags, **kwargs)

    @property
    def full_path(self) -> str:
        return self.workspace.get_full_path(self.file)


@dataclass
class SourceLog(_SpecialSystemFile):
    """Record of upload and processing events for a source workspace."""

    DEFAULT_LOG_FORMAT = '%(asctime)s %(message)s'
    DEFAULT_TIME_FORMAT = '%d/%b/%Y:%H:%M:%S %z'

    log_format: str = field(default=DEFAULT_LOG_FORMAT)
    """Format string for log messages."""

    time_format: str = field(default=DEFAULT_TIME_FORMAT)

    level: int = field(default=logging.INFO)
    """Log level."""

    def __post_init__(self) -> None:
        # super(SourceLog, self).__post_init__()
        # Grab standard logger and customize it.
        self._logger = logging.getLogger(f'source:{self.workspace.upload_id}')
        self._f_path = self.workspace.get_full_path(self.file, is_system=True)
        self.file_handler = logging.FileHandler(self._f_path)
        self.file_handler.setLevel(self.level)
        self._formatter = logging.Formatter(self.log_format, self.time_format)
        self.file_handler.setFormatter(self._formatter)
        self._logger.handlers = []
        self._logger.addHandler(self.file_handler)
        self._logger.setLevel(self.level)
        self._logger.propagate = False

    def debug(self, message: str) -> None:
        self._logger.debug(message)

    def info(self, message: str) -> None:

        self._logger.info(message)

    def error(self, message: str) -> None:
        self._logger.error(message)


@dataclass
class SourcePackage(_SpecialSystemFile):
    """An archive containing an entire submission source package."""

    @property
    def is_stale(self) -> bool:
        """Indicates whether or not the source package is out of date."""
        if self.workspace.last_modified is None:
            return True
        stale = self.last_modified < self.workspace.last_modified
        return stale

    def pack(self) -> None:
        if self.workspace.storage is None:
            raise RuntimeError('Storage adapter is not set')
        self._file = self.workspace.pack_source(self.file)