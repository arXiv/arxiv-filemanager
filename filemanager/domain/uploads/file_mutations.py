"""Provides :class:`.FileMutationsMixin`."""

import io
import logging
import os
import re
from contextlib import contextmanager
from datetime import datetime
from itertools import accumulate
from typing import Optional, List, Union, Iterable, Tuple, IO, Iterator, Any, \
    Callable, cast

from dataclasses import dataclass, field
from typing_extensions import Protocol

from ..index import FileIndex

from ..uploaded_file import UserFile
from ..error import Error, Severity
from ..file_type import FileType

from .base import IStorageAdapter, IBaseWorkspace
from .util import modifies_workspace, logger


class IWorkspace(IBaseWorkspace, Protocol):
    """
    Workspace API required for :class:`.FileMutations`.

    This incorporates the base API and any additional structures that require
    implementation by other components of the workspace.
    """

    def add_error(self, u_file: UserFile, msg: str,
                  severity: Severity = Severity.FATAL,
                  is_persistant: bool = True) -> None:
        """Add an error for a specific file."""

    def perform_checks(self) -> None:
        """Perform all checks on the workspace."""


class IFileMutations(Protocol):
    """Interface for file mutations behavior."""

    @property
    def source_package(self) -> 'SourcePackage':
        """Get the source package for this workspace."""

    @property
    def log(self) -> 'SourceLog':
        """Get the source log for this workspace."""

    def add_files(self, *u_files: UserFile) -> None:
        """Add new :class:`.UserFile`s to this workspace."""

    def copy(self, u_file: UserFile, new_path: str,
             replace: bool = False) -> UserFile:
        """Copy :class:`.UserFile` ``u_file`` to path ``new_path``."""

    def create(self, path: str, file_type: FileType = FileType.UNKNOWN,
               replace: bool = False, is_directory: bool = False,
               is_ancillary: Optional[bool] = None, is_system: bool = False,
               is_persisted: bool = False, touch: bool = True) -> UserFile:
        """Create a new :class:`.UserFile` at ``path``."""

    def delete(self, u_file: UserFile) -> None:
        """Completely delete a file."""

    def delete_all_files(self) -> None:
        """Delete all source and ancillary files in the workspace."""

    def delete_workspace(self) -> bool:
        """Complete delete the upload workspace."""

    def drop_refs(self, from_path: str, is_ancillary: bool = False,
                  is_removed: bool = False, is_system: bool = False) -> None:
        """Drop references to ``from_path``."""

    def initialize(self) -> None:
        """Set up the source package and log for this workspace."""

    def persist(self, u_file: UserFile) -> None:
        """Move a file to permanent storage."""

    def persist_all(self) -> None:
        """Move all files in the workspace to permanent storage."""

    def remove(self, u_file: UserFile, reason: Optional[str] = None) -> None:
        """Mark a file as removed, and quarantine."""

    def replace(self, to_replace: UserFile, replace_with: UserFile,
                keep_refs: bool = True) -> UserFile:
        """Replace a file with another file."""



@dataclass
class FileMutations(IFileMutations):
    """
    Adds methods that alter files, including deleting the whole workspace.

    Introduces the source package.
    """

    _source_package: Optional['SourcePackage'] = field(default=None)
    _log: Optional['SourceLog'] = field(default=None)

    LEADING_DOTSLASH = re.compile(r'^\./')
    """Pattern to match leading ``./`` in relative paths."""

    __internal_api = None

    def __api_init__(self, api: IWorkspace) -> None:
        """Register the workspace API."""
        if hasattr(super(FileMutations, self), '__api_init__'):
            super(FileMutations, self).__api_init__(api)    # type: ignore
        self.__internal_api = api

    @property
    def __api(self) -> IWorkspace:
        assert self.__internal_api is not None
        return self.__internal_api

    @property
    def source_package(self) -> 'SourcePackage':
        """Get the source package for this workspace."""
        if self._source_package is None:
            raise RuntimeError('Package not set; call initialize() first')
        return self._source_package

    @property
    def log(self) -> 'SourceLog':
        """Get the source log for this workspace."""
        if self._log is None:
            raise RuntimeError('Source log not set; call initialize() first')
        return self._log

    @modifies_workspace()
    def add_files(self, *u_files: UserFile) -> None:
        """Add new :class:`.UserFile`s to this workspace."""
        for u_file in u_files:
            parts = u_file.path.split('/')
            for parent in accumulate(parts[:-1], lambda *p: os.path.join(*p)):
                parent += '/'
                if not self.__api.exists(parent):
                    self.create(parent, FileType.DIRECTORY, is_directory=True)
            self.__api.files.set(u_file.path, u_file)
        self.__api.perform_checks()

    @modifies_workspace()
    def copy(self, u_file: UserFile, new_path: str,
             replace: bool = False) -> UserFile:
        """Copy :class:`.UserFile` ``u_file`` to path ``new_path``."""
        if self.__api.files.contains(new_path,
                                              is_ancillary=u_file.is_ancillary,
                                              is_removed=u_file.is_removed,
                                              is_system=u_file.is_system):
            existing_file = self.__api.files.get(
                new_path,
                is_ancillary=u_file.is_ancillary,
                is_removed=u_file.is_removed,
                is_system=u_file.is_system
            )
            if existing_file.is_directory:
                raise ValueError('Directory exists at that path')
        new_file = UserFile(cast(IWorkspace, self), path=new_path,
                                size_bytes=u_file.size_bytes,
                                file_type=u_file.file_type,
                                is_ancillary=u_file.is_ancillary,
                                is_removed=u_file.is_removed,
                                is_checked=u_file.is_checked,
                                is_system=u_file.is_system)
        self.__api.storage.copy(self, u_file, new_file)
        self.__api.files.set(new_path, new_file)
        return new_file

    @modifies_workspace()
    def create(self, path: str, file_type: FileType = FileType.UNKNOWN,
               replace: bool = False, is_directory: bool = False,
               is_ancillary: Optional[bool] = None, is_system: bool = False,
               is_persisted: bool = False, touch: bool = True) -> UserFile:
        """Create a new :class:`.UserFile` at ``path``."""
        path = self.LEADING_DOTSLASH.sub('', path)
        if is_ancillary is None:    # Infer whether this is an ancillary file.
            path, is_ancillary = self.__api.is_ancillary_path(path)

        u_file = UserFile(cast(IWorkspace, self),
                              path=path, size_bytes=0,
                              file_type=file_type,
                              is_directory=is_directory,
                              is_ancillary=is_ancillary,
                              is_system=is_system,
                              is_persisted=is_persisted)

        # Make sure that we have references for the parent director(y|ies).
        parts = u_file.path.split('/')
        for parent in accumulate(parts[:-1], lambda *p: os.path.join(*p)):
            parent += '/'
            if not self.__api.exists(parent):
                parent_file = UserFile(cast(IWorkspace, self),
                                           path=parent, size_bytes=0,
                                           file_type=FileType.DIRECTORY,
                                           is_directory=True,
                                           is_ancillary=is_ancillary,
                                           is_system=is_system,
                                           is_persisted=is_persisted)
                self.__api.files.set(parent_file.path, parent_file)
                if touch:
                    self.__api.storage.create(self, parent_file)

        self.__api.files.set(u_file.path, u_file)

        if touch:
            self.__api.storage.create(self, u_file)
        else:
            self.__api.set_last_modified(u_file)
            self.__api.get_size_bytes(u_file)
            self.__api.get_last_modified(u_file)
        return u_file

    @modifies_workspace()
    def delete(self, u_file: UserFile) -> None:
        """
        Completely delete a file.

        See also :func:`Workspace.remove`.
        """
        logger.debug('Delete file %s', u_file.path)
        self.__api.storage.delete(self, u_file)
        self.drop_refs(u_file.path,
                                      is_ancillary=u_file.is_ancillary,
                                      is_system=u_file.is_system,
                                      is_removed=u_file.is_removed)
        if u_file.is_directory:
            for child_path, child_file \
                    in self.__api.iter_children(u_file):
                self.drop_refs(child_path)

    @modifies_workspace()
    def delete_all_files(self) -> None:
        """Delete all source and ancillary files in the workspace."""
        self.__api.storage.delete_all(self)
        self.__api.files.source.clear()
        self.__api.files.ancillary.clear()
        self.__api.storage.makedirs(self, self.__api.source_path)
        self.__api.storage.makedirs(self, self.__api.ancillary_path)

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
        # Think about stashing source.log, otherwise any logging is fruitless
        # since we are deleting all files under workspace.
        # Let's stash a copy of the source.log file (if it exists)
        self._stash_log()

        # Now blow away the workspace
        self.__api.storage.delete_workspace(self)
        return True

    def drop_refs(self, from_path: str, is_ancillary: bool = False,
                  is_removed: bool = False, is_system: bool = False) -> None:
        """Drop references to ``from_path``."""
        self.__api.files.pop(from_path, is_ancillary=is_ancillary,
                             is_removed=is_removed, is_system=is_system)

    def initialize(self) -> None:
        """Set up the source package and log for this workspace."""
        self._source_package = SourcePackage(cast(ISystemFilesWorkspace, self),
                                             f'{self.__api.upload_id}.tar.gz')
        self._log = SourceLog(cast(ISystemFilesWorkspace, self), 'source.log')

    @modifies_workspace()
    def persist(self, u_file: UserFile) -> None:
        """Move a file to permanent storage."""
        self.__api.storage.persist(self, u_file)

    @modifies_workspace()
    def persist_all(self) -> None:
        """Move all files in the workspace to permanent storage."""
        for u_file in self.__api.iter_files(allow_system=True):
            if not u_file.is_persisted:
                self.persist(u_file)

    @modifies_workspace()
    def remove(self, u_file: UserFile, reason: Optional[str] = None) -> None:
        """
        Mark a file as removed, and quarantine.

        This is not the same as deletion.
        """
        if reason is None:
            reason = f"Removed file '{u_file.name}'."
        logger.debug('Remove file %s: %s', u_file.path, reason)
        self.__api.storage.remove(self, u_file)

        if u_file.is_directory:
            for former_path, _file \
                    in self.__api.iter_children(u_file):
                _file.is_removed = True
                self.drop_refs(_file.path,
                                              is_ancillary=_file.is_ancillary,
                                              is_removed=False,
                                              is_system=_file.is_system)
                self.__api.files.set(_file.path, _file)

        u_file.is_removed = True
        u_file.reason_for_removal = reason

        self.__api.add_error(u_file, reason, severity=Severity.INFO,
                             is_persistant=False)

        self.drop_refs(u_file.path, is_ancillary=u_file.is_ancillary,
                             is_removed=False,
                             is_system=u_file.is_system)
        self.__api.files.set(u_file.path, u_file)

    @modifies_workspace()
    def replace(self, to_replace: UserFile, replace_with: UserFile,
                keep_refs: bool = True) -> UserFile:
        """Replace a file with another file."""
        self.__api.storage.move(self, replace_with,
                                           replace_with.path, to_replace.path)

        if keep_refs:
            for error in to_replace.errors:
                replace_with.add_error(error)

        self.drop_refs(to_replace.path)
        old_path = replace_with.path
        replace_with.path = to_replace.path
        self.update_refs(replace_with, old_path)

        # If the file is a directory, we are counting on storage to have moved
        # both the directory itself along with all of its children. But we must
        # still update all of our path-based references to reflect this change.
        if replace_with.is_directory:
            for _former_path, _file \
                    in self.__api.iter_children(replace_with):
                _new_path = os.path.join(to_replace.path.rstrip('/'),
                                         _former_path.split(old_path, 1)[1])
                _file.path = _new_path
                if not keep_refs:
                    self.drop_refs(_new_path)
                self.update_refs(_file, _former_path)

        # TODO: update info for target children if target was a directory.
        return replace_with

    @modifies_workspace()
    def rename(self, u_file: UserFile,
               new_path: str) -> None:
        """Rename a file in this workspace."""
        logger.debug('Rename %s to %s (ancillary = %s)',
                     u_file.path, new_path, u_file.is_ancillary)
        former_path = u_file.path
        u_file.path = new_path
        self.__api.storage.move(self, u_file, former_path,
                                           u_file.path)
        self.update_refs(u_file, former_path)

        # If the file is a directory, we are counting on storage to have moved
        # both the directory itself along with all of its children. But we must
        # still update all of our path-based references to reflect this change.
        if u_file.is_directory:
            for _former_path, _file \
                    in self.__api.iter_children(u_file):
                _new_path = os.path.join(new_path.rstrip('/'),
                                         _former_path.split(former_path, 1)[1])
                _file.path = _new_path
                self.update_refs(_file, _former_path)

    def update_refs(self, u_file: UserFile, from_path: str) -> None:
        """Update references to ``from_path`` to ``u_file``."""
        self.__api.files.pop(from_path, is_ancillary=u_file.is_ancillary,
                             is_removed=u_file.is_removed,
                             is_system=u_file.is_system)   # Discard old ref.
        self.__api.files.set(u_file.path, u_file)

    def _stash_log(self) -> None:
        """Copy the workspace log to the deleted logs directory."""
        self.log.info(f"Move source log for {self.__api.upload_id} to"
                      f" '{self.__api.storage.deleted_logs_path}'.")
        self.log.info(f"Delete workspace '{self.__api.upload_id}'.")
        try:
            self.__api.storage.stash_deleted_log(self,
                                                            self.log.file)
        except Exception as e:
            self.log.info(f'Saving source.log failed: {e}')



class ISystemFilesWorkspace(IWorkspace, Protocol):
    def create(self, path: str, file_type: FileType = FileType.UNKNOWN,
               replace: bool = False, is_directory: bool = False,
               is_ancillary: Optional[bool] = None, is_system: bool = False,
               is_persisted: bool = False, touch: bool = True) -> UserFile:
        ...
    # open
    # open_pointer
    # get_full_path
    # last_modified
    # pack_source

@dataclass
class _SpecialSystemFile:
    """Some system files have specific and unique semantics."""

    workspace: ISystemFilesWorkspace
    """Workspace to which the special system file belongs."""

    path: str
    """Relative path to the system file within the containing workspace."""

    _file: Optional[UserFile] = None

    @property
    def file(self) -> UserFile:
        """Create the underlying file if it does not already exist."""
        if self._file is None:
            if self.workspace.exists(self.path, is_system=True):
                self._file = self.workspace.get(self.path,
                                                            is_system=True)
            else:
                self._file  = self.workspace.create(self.path, is_system=True,
                                                    is_persisted=True,
                                                    touch=True)
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
        return self.workspace.open_pointer(self.file, flags,
                                                        **kwargs)

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
        log_name = f'source:{self.workspace.upload_id}'
        self._logger = logging.getLogger(log_name)
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