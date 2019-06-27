"""
Provides :class:`.UploadWorkspace`, the organizing concept for this service. 

Because :class:`.UploadWorkspace` has many properties and methods, its 
members are split out into mixins that group related functionality.
"""

import os
import re
import io
from hashlib import md5
from base64 import urlsafe_b64encode
from itertools import accumulate
from typing import List, Callable, Optional, Any, Type, Dict, Mapping, Union, \
    Iterable, Tuple, Iterator
from collections import defaultdict, Counter
from contextlib import contextmanager
from datetime import datetime
from enum import Enum
from itertools import chain
from functools import partial, wraps

from typing_extensions import Literal
from dataclasses import dataclass, field
from pytz import UTC

from arxiv.base import logging
from .file_type import FileType
from .storage import IStorageAdapter
from .checks import IChecker, ICheckingStrategy
from .log import SourceLog
from .package import SourcePackage
from .uploaded_file import UploadedFile
from .error import Error
from .index import FileIndex
logger = logging.getLogger(__name__)
logger.propagate = False


def modifies_workspace(func: Callable) -> Callable:
    """Extend an instance method to perform post-modification steps."""
    @wraps(func)
    def inner(workspace: 'UploadWorkspace', *args: Any, **kwargs: Any) -> Any:
        result = func(workspace, *args, **kwargs)
        workspace.modified_datetime = datetime.now(UTC)
        return result
    return inner


class FileStaticOperationsMixin:
    """Implements methods for non-mutating operations on individual files."""

    def cmp(self: 'UploadWorkspace', a_file: UploadedFile, 
            b_file: UploadedFile, shallow: bool = True) -> bool:
        """Compare the contents of two files."""
        return self.storage.cmp(self, a_file, b_file, shallow=shallow)
    
    def is_tarfile(self: 'UploadWorkspace', u_file: UploadedFile) -> bool:
        """Determine whether or not a file is a tarfile."""
        return self.storage.is_tarfile(self, u_file)
    
    def get_size_bytes(self: 'UploadWorkspace', u_file: UploadedFile) -> int:
        """Get (and update) the size in bytes of a file."""
        u_file.size_bytes = self.storage.get_size_bytes(self, u_file)
        return u_file.size_bytes

    def get_last_modified(self: 'UploadWorkspace', u_file: UploadedFile) -> datetime:
        u_file.last_modified = self.storage.get_last_modified(self, u_file)
        return u_file.last_modified

    def get_checksum(self: 'UploadWorkspace', u_file: UploadedFile) -> str:
        hash_md5 = md5()
        with self.open(u_file, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return urlsafe_b64encode(hash_md5.digest()).decode('utf-8')
    

class OpenFilesMixin:
    """Implements methods for opening files."""

    @contextmanager
    @modifies_workspace
    def open(self, u_file: UploadedFile, flags: str = 'r', **kwargs: Any) \
            -> Iterator[io.IOBase]:
        """Get a file pointer for a :class:`.UploadFile`."""
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
                     **kwargs: Any) -> io.IOBase:
        return self.storage.open_pointer(self, u_file, flags, **kwargs)


class FileMutationsMixin:
    """Implements methods that alter files."""

    LEADING_DOTSLASH = re.compile(r'^\./')
    """Pattern to match leading ``./`` in relative paths."""

    @modifies_workspace
    def create(self: 'UploadWorkspace', path: str, 
               file_type: FileType = FileType.UNKNOWN,
               replace: bool = False,
               is_directory: bool = False,
               is_ancillary: Optional[bool] = None,
               is_system: bool = False,
               touch: bool = True) -> UploadedFile:
        """Create a new :class:`.UploadedFile` at ``path``."""
        path = self.LEADING_DOTSLASH.sub('', path)
        logger.debug('Create a file at %s with type %s', path, file_type.value)
        if self.files.contains(path, is_ancillary=is_ancillary,
                               is_system=is_system):
            e_file = self.files.get(path, is_ancillary=is_ancillary,
                                    is_system=is_system)
            if e_file.is_directory:
                raise ValueError('Directory exists at that path')
            # if not replace:
            #     raise ValueError('File at that path already exists')

        if is_ancillary is None:    # Infer whether this is an ancillary file.
            path, is_ancillary = self._check_is_ancillary_path(path)

        u_file = UploadedFile(self, path=path, size_bytes=0,
                              file_type=file_type,
                              is_directory=is_directory,
                              is_ancillary=is_ancillary,
                              is_system=is_system)

        # if not is_system:   # System files are not part of the source package.
        self.files.set(u_file.path, u_file)

        if touch:
            self.storage.create(self, u_file)
        else:
            self.get_size_bytes(u_file)
            self.get_last_modified(u_file)
        return u_file

    @modifies_workspace
    def delete(self: 'UploadWorkspace', u_file: UploadedFile) -> None:
        """
        Completely delete a file.

        See also :func:`UploadWorkspace.remove`.
        """
        logger.debug('Delete file %s', u_file.path)
        self.storage.delete(self, u_file)
        self._drop_refs(u_file.path, is_ancillary=u_file.is_ancillary,
                        is_system=u_file.is_system,
                        is_removed=u_file.is_removed)
        if u_file.is_directory:
            for child_path, child_file in self.iter_children(u_file):
                self._drop_refs(child_path)
    
    @modifies_workspace
    def delete_all_files(self: 'UploadWorkspace') -> None:
        """Delete all source and ancillary files in the workspace."""
        self.storage.delete_all(self)
        self.files.source.clear()
        self.files.ancillary.clear()
        self.storage.makedirs(self, self.source_path)
        self.storage.makedirs(self, self.ancillary_path)
    
    @modifies_workspace
    def copy(self: 'UploadWorkspace', u_file: UploadedFile, new_path: str,
             replace: bool = False) -> UploadedFile:
        """Make a copy of a file."""
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

    @modifies_workspace
    def replace(self: 'UploadWorkspace', to_replace: UploadedFile, 
                replace_with: UploadedFile, keep_refs: bool = True) \
            -> UploadedFile:
        """Replace a file with another file."""
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
    
    @modifies_workspace
    def remove(self: 'UploadWorkspace', u_file: UploadedFile, 
               reason: Optional[str] = None) -> None:
        """
        Mark a file as removed, and quarantine.

        This is not the same as deletion.
        """
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

    @modifies_workspace
    def persist(self: 'UploadWorkspace', u_file: UploadedFile) -> None:
        self.storage.persist(self, u_file, self.get_path(u_file))
    
    @modifies_workspace
    def rename(self: 'UploadWorkspace', u_file: UploadedFile, 
               new_path: str) -> None:
        """Rename a file in this workspace."""
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

    @modifies_workspace
    def add_files(self: 'UploadWorkspace', *u_files: UploadedFile) -> None:
        """Add new :class:`.UploadedFile`s to this workspace."""
        for u_file in u_files:
            parts = u_file.path.split('/')
            for parent in accumulate(parts, lambda *p: os.path.join(*p)):
                parent += '/'
                if not self.exists(parent):
                    self.create(parent, FileType.DIRECTORY, is_directory=True)
            self.files.set(u_file.path, u_file)
        self.strategy.check(self, self.checkers)
    
    def _update_refs(self: 'UploadWorkspace', u_file: UploadedFile, 
                     from_path: str) -> None:
        self.files.pop(from_path, is_ancillary=u_file.is_ancillary,
                       is_removed=u_file.is_removed,
                       is_system=u_file.is_system)   # Discard old ref.
        self.files.set(u_file.path, u_file)

    def _drop_refs(self: 'UploadWorkspace', from_path: str, 
                   is_ancillary: bool = False, is_removed: bool = False, 
                   is_system: bool = False) -> None:
        self.files.pop(from_path, is_ancillary=is_ancillary,
                       is_removed=is_removed, is_system=is_system)


class PathsMixin:
    """Implements methods related to paths in :class:`.UploadWorkspace."""

    @property
    def base_path(self: 'UploadWorkspace'):
        """Relative base path for this workspace."""
        return str(self.upload_id)

    @property
    def source_path(self: 'UploadWorkspace') -> str:
        """Get the path where source files are deposited."""
        return os.path.join(self.base_path, self.SOURCE_PREFIX)

    @property
    def removed_path(self: 'UploadWorkspace') -> str:
        """Get path where source archive files get moved when unpacked."""
        return os.path.join(self.base_path, self.REMOVED_PREFIX)

    @property
    def ancillary_path(self: 'UploadWorkspace') -> str:
        """Get the path where ancillary files are stored."""
        return os.path.join(self.source_path, self.ANCILLARY_PREFIX)

    def get(self: 'UploadWorkspace', path: str, 
            is_ancillary: Optional[bool] = None, is_removed: bool = False, 
            is_system: bool = False) -> UploadedFile:
        """Get a file at ``path``."""
        if is_system:
            # Create a description of the file, since system files are not part
            # of the source package.
            return self.create(path, is_system=is_system, touch=True)
        if is_ancillary is None:
            path, is_ancillary = self._check_is_ancillary_path(path)
        return self.files.get(path, is_ancillary=is_ancillary,
                              is_removed=is_removed, is_system=is_system)
    
    def get_public_path(self: 'UploadWorkspace', u_file: UploadedFile) -> str:
        if u_file.is_system or u_file.is_removed:
            raise RuntimeError('Not a public file')
        if u_file.is_ancillary:
            return os.path.join(self.ANCILLARY_PREFIX, u_file.path)
        return u_file.path

    def get_path(self: 'UploadWorkspace', 
                 u_file_or_path: Union[str, UploadedFile],
                 is_ancillary: bool = False, is_removed: bool = False,
                 is_system: bool = False, **kwargs) -> str:
        """Get the path to an :class:`.UploadedFile` in this workspace."""
        if isinstance(u_file_or_path, UploadedFile):
            logger.debug('Get path for file: %s', u_file_or_path.path)
            path = self._get_path_from_file(u_file_or_path)
        else:
            path = self._get_path(u_file_or_path, is_ancillary=is_ancillary,
                                  is_removed=is_removed, is_system=is_system)
        return path.lstrip('/')

    def get_full_path(self: 'UploadWorkspace', 
                      u_file_or_path: Union[str, UploadedFile],
                      is_ancillary: bool = False,
                      is_removed: bool = False,
                      is_persisted: bool = False,
                      is_system: bool = False) -> str:
        """Get the absolute path to a :class:`.UploadedFile`."""
        return self.storage.get_path(self, u_file_or_path,
                                     is_ancillary=is_ancillary,
                                     is_removed=is_removed,
                                     is_persisted=is_persisted,
                                     is_system=is_system)

    def _get_path(self: 'UploadWorkspace', path: str, 
                  is_ancillary: bool = False, is_removed: bool = False, 
                  is_system: bool = False) -> str:
        path = path.lstrip('/')
        if is_system:
            return os.path.join(self.base_path, path)
        if is_ancillary:
            return os.path.join(self.ancillary_path, path)
        if is_removed:
            return os.path.join(self.removed_path, path)
        return os.path.join(self.source_path, path)

    def _get_path_from_file(self: 'UploadWorkspace', u_file: UploadedFile) \
            -> str:
        return self._get_path(u_file.path, is_ancillary=u_file.is_ancillary,
                              is_removed=u_file.is_removed,
                              is_system=u_file.is_system)
    
    def is_safe(self: 'UploadWorkspace', path: str) -> bool:
        """Determine whether or not a path is safe to use in this workspace."""
        return self.storage.is_safe(self, path)
    
    def exists(self: 'UploadWorkspace', path: str, is_ancillary: bool = False,
               is_removed: bool = False, is_system: bool = False) -> bool:
        """Determine whether or not a file exists in this workspace."""
        return self.files.contains(path, is_ancillary=is_ancillary,
                                   is_removed=is_removed, is_system=is_system)

    def _check_is_ancillary_path(self, path: str) -> Tuple[str, bool]:
        if path.startswith(self.ANCILLARY_PREFIX):
            logger.debug('Path indicates an ancillary file')
            _, path = path.split(self.ANCILLARY_PREFIX, 1)
            path = path.strip('/')
            logger.debug('Path indicates ancillary file; trimmed to `%s`',
                         path)
            return path, True
        return path, False  


class ErrorsAndWarningsMixin:
    """Implements properties and methods for errors and warnings."""

    @property
    def errors(self: 'UploadWorkspace') -> List[Error]:
        return [error for u_file in self.files for error in u_file.errors] \
            + self._errors

    @property
    def fatal_errors(self: 'UploadWorkspace') -> List[Error]:
        return (
            [error for u_file in self.files for error in u_file.errors
             if u_file.is_active and error.severity is Error.Severity.FATAL]
            +
            [error for error in self._errors
             if error.severity is Error.Severity.FATAL]
        )

    @property
    def warnings(self: 'UploadWorkspace') -> Mapping[str, List[str]]:
        """Warnings for all files in the workspace."""
        return self._get_warnings()
    
    @property
    def active_warnings(self: 'UploadWorkspace') -> Mapping[str, List[str]]:
        """Warnings for active files only."""
        return self._get_warnings(is_active=True)

    def _get_warnings(self: 'UploadWorkspace', is_active: bool = None) \
            -> Mapping[str, List[str]]:
        return (
            [error for u_file in self.files for error in u_file.errors
             if error.severity is Error.Severity.WARNING
             and (is_active is None or u_file.is_active == is_active)]
            +
            [error for error in self._errors
             if error.severity is Error.Severity.WARNING]
        )

    def get_warnings_for_path(self: 'UploadWorkspace', path: str, 
                              is_ancillary: bool = False,
                              is_system: bool = False,
                              is_removed: bool = False) -> List[str]:
        u_file = self.files.get(path, is_ancillary=is_ancillary,
                                is_system=is_system, is_removed=is_removed)
        return [e.message for e in u_file.errors
                if e.severity is Error.Severity.WARNING]
    
    def add_error(self: 'UploadWorkspace', u_file: UploadedFile, msg: str,
                  severity: Error.Severity = Error.Severity.FATAL,
                  is_persistant: bool = True) -> None:
        """Add an error for a specific file."""
        u_file.add_error(Error(severity=severity, path=u_file.path,
                               message=msg, is_persistant=is_persistant))

    def add_non_file_error(self: 'UploadWorkspace', msg: str,
                           severity: Error.Severity = Error.Severity.FATAL,
                           is_persistant: bool = True) -> None:
        """Add an error for the workspace that is not specific to a file."""
        self._errors.append(Error(severity=severity, path=None, message=msg,
                                  is_persistant=is_persistant))

    def add_warning(self: 'UploadWorkspace', u_file: UploadedFile, msg: str,
                    is_persistant: bool = False) -> None:
        """Add a warning for a specific file."""
        self.add_error(u_file, msg, severity=Error.Severity.WARNING,
                       is_persistant=is_persistant)

    def add_non_file_warning(self: 'UploadWorkspace', msg: str, 
                             is_persistant: bool = False) -> None:
        """Add a warning for the workspace that is not specific to a file."""
        self.add_non_file_error(msg, severity=Error.Severity.WARNING,
                                is_persistant=is_persistant)
    
    @property
    def has_warnings(self: 'UploadWorkspace') -> bool:
        """Determine whether or not this workspace has warnings."""
        return len(self.warnings) > 0

    @property
    def has_active_warnings(self: 'UploadWorkspace') -> bool:
        """Determine whether this workspace has warnings for active files."""
        return len(self.active_warnings) > 0

    @property
    def has_errors(self: 'UploadWorkspace') -> bool:
        """Determine whether or not this workspace has errors."""
        return len(self.errors) > 0

    @property
    def has_fatal_errors(self: 'UploadWorkspace') -> bool:
        return len(self.fatal_errors) > 0


class CountsMixin:
    """Implements methods related to file counts."""

    @property
    def file_count(self) -> int:
        """Get the total number of non-ancillary files in this workspace."""
        return len(self.iter_files(allow_ancillary=False))
    
    @property
    def ancillary_file_count(self) -> int:
        """Get the total number of ancillary files in this workspace."""
        files = self.iter_files(allow_ancillary=True, allow_removed=False)
        return len([f for f in files if f.is_ancillary])

    def get_file_type_counts(self) -> Mapping[Union[FileType, str], int]:
        """Get the number of files of each type in the workspace."""
        counts = Counter()
        for u_file in self.iter_files():
            counts['all_files'] += 1
            if u_file.is_ancillary:
                counts['ancillary'] += 1
                continue
            elif u_file.is_always_ignore:
                counts['ignore'] += 1
                continue
            counts[u_file.file_type] += 1
        counts['files'] = counts['all_files'] - counts['ancillary']
        return counts


class StatusMixin:
    """Implements status-related methods and properties."""

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
    
    @property
    def is_active(self: 'UploadWorkspace') -> bool:
        return bool(self.status == UploadWorkspace.Status.ACTIVE)
        
    @property
    def is_deleted(self: 'UploadWorkspace') -> bool:
        return bool(self.status == UploadWorkspace.Status.DELETED)

    @property
    def is_released(self: 'UploadWorkspace') -> bool:
        return bool(self.status == UploadWorkspace.Status.RELEASED)


class ReadinessMixin:
    """Implements methods and properties releated to source readiness."""

    class Readiness(Enum):
        """
        Upload workspace readiness states.

        Provides an indication (but not the final word) on whether the
        workspace is suitable for incorporating into a submission to arXiv.
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

    @property
    def readiness(self: 'UploadWorkspace') -> 'Readiness':
        """Readiness state of the upload workspace."""
        if self.has_fatal_errors:
            return UploadWorkspace.Readiness.ERRORS
        elif self.has_active_warnings:
            return UploadWorkspace.Readiness.READY_WITH_WARNINGS
        return UploadWorkspace.Readiness.READY


class LockMixin:
    """Implements methods and properties related to locking/unlocking."""

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
    
    @property
    def is_locked(self: 'UploadWorkspace') -> bool:
        return bool(self.lock_state == UploadWorkspace.LockState.LOCKED)


class SingleFileMixin:
    """Implements methods related to single-file source packages."""

    @property
    def is_single_file_submission(self):
        """Indicate whether or not this is a valid single-file submission."""
        if self.file_count != 1:
            return False
        counts = self.get_file_type_counts()
        if counts['ignore'] == 1:
            return False
        return True

    def get_single_file(self) -> Optional[UploadedFile]:
        """
        Return File object for single-file submission.

        This routine is intended for submission that are composed of a single
        content file.

        Single file can't be type 'ancillary'. Single ancillary file is invalid
        submission and generates an error.

        Returns
        -------
        :class:`.UploadedFile` or ``None``
            Single file. Returns None when submission has more than one file.

        """
        if self.is_single_file_submission:
            for u_file in self.iter_files(allow_ancillary=False):
                return u_file    # Return the first file.
    

class ChecksMixin:
    """Implements methods related to file and workspace checks."""

    @property
    def has_unchecked_files(self: 'UploadWorkspace') -> bool:
        """Determine whether there are unchecked files in this workspace."""
        for u_file in self.iter_files(allow_directories=True):
            if not u_file.is_checked:
                return True
        return False
    
    def perform_checks(self: 'UploadWorkspace') -> None:
        """Perform all checks on this workspace using the assigned strategy."""
        self.strategy.check(self, *self.checkers)
        if self.source_package.is_stale:
            self.source_package.pack()


@dataclass
class UploadWorkspace(ErrorsAndWarningsMixin, PathsMixin, CountsMixin,
                      FileStaticOperationsMixin, FileMutationsMixin,
                      OpenFilesMixin, StatusMixin, ReadinessMixin,
                      LockMixin, SingleFileMixin, ChecksMixin):
    """An upload workspace contains a set of submission source files."""

    class SourceType(Enum):
        """High-level type of the submission source as a whole."""

        UNKNOWN = 'unknown'
        INVALID = 'invalid'
        POSTSCRIPT = 'ps'
        PDF = 'pdf'
        HTML = 'html'
        TEX = 'tex'

        @property
        def is_unknown(self) -> bool:
            """Indicate whether this is the :const:`.UNKNOWN` type."""
            return self is self.UNKNOWN

        @property
        def is_invalid(self) -> bool:
            """Indicate whether this is the :const:`.INVALID` type."""
            return self is self.INVALID

    SOURCE_PREFIX = 'src'
    """The name of the source directory within the upload workspace."""

    REMOVED_PREFIX = 'removed'
    """The name of the removed directory within the upload workspace."""

    ANCILLARY_PREFIX = 'anc'
    """The directory within source directory where ancillary files are kept."""

    upload_id: int
    """Unique ID for the upload workspace."""

    owner_user_id: str
    """User id for owner of workspace."""

    created_datetime: datetime
    """When workspace was created"""

    modified_datetime: datetime
    """When workspace was last modified"""

    # General state of upload

    storage: IStorageAdapter
    """Adapter for persistence."""

    status: 'Status' = field(default=StatusMixin.Status.ACTIVE)
    """Status of upload workspace."""

    lock_state: 'LockState' = field(default=LockMixin.LockState.UNLOCKED)
    """Lock state of upload workspace."""

    checkers: List[IChecker] = field(default_factory=list)
    """File checkers that should be applied to all files in the workspace."""

    strategy: Optional[ICheckingStrategy] = field(default=None)
    """Strategy for performing file checks."""

    source_type: SourceType = field(default=SourceType.UNKNOWN)

    _errors: List[Error] = field(default_factory=list)

    files: FileIndex = field(default_factory=FileIndex)
    """Index of all of the files in this workspace."""

    # Data about last upload

    lastupload_start_datetime: Optional[datetime] = field(default=None)
    """When we started processing last upload event."""

    lastupload_completion_datetime: Optional[datetime] = field(default=None)
    """When we completed processing last upload event."""

    lastupload_logs: str = field(default_factory=str)
    """Logs associated with last upload event."""

    lastupload_file_summary: str = field(default_factory=str)
    """Logs associated with last upload event."""

    lastupload_readiness: 'Readiness' = \
        field(default=ReadinessMixin.Readiness.READY)
    """Content readiness status after last upload event."""

    def __post_init__(self) -> None:
        """Make sure that we have all of the required directories."""
        self.storage.makedirs(self, self.source_path)
        self.storage.makedirs(self, self.ancillary_path)
        self.storage.makedirs(self, self.removed_path)
        self.log = SourceLog(self)
        self.source_package = SourcePackage(self)
    
    @property
    def size_bytes(self) -> int:
        """Total size of the source content (including ancillary files)."""
        return sum([f.size_bytes for f in self.iter_files()])

    @property
    def last_modified(self) -> Optional[datetime]:
        """Time of the most recent change to a file in the workspace."""
        files_last_modified = [f.last_modified for f in self.iter_files()]
        if not files_last_modified:
            return None
        return max(files_last_modified + [self.modified_datetime])   

    def iter_children(self, u_file_or_path: Union[str, UploadedFile],
                      max_depth: int = None, is_ancillary: bool = False,
                      is_removed: bool = False, is_system: bool = False) \
            -> Iterable[Tuple[str, UploadedFile]]:
        """Get an iterator over path, :class:`.UploadedFile` tuples."""
        # QUESTION: is it really so bad to use non-directories here? Can be
        # like the key-prefix for S3. --Erick 2019-06-11.
        u_file: Optional[UploadedFile] = None
        if isinstance(u_file_or_path, str) \
                and self.files.contains(u_file_or_path,
                                        is_ancillary=is_ancillary,
                                        is_removed=is_removed,
                                        is_system=is_system):
            u_file = self.files.get(u_file_or_path,
                                    is_ancillary=is_ancillary,
                                    is_removed=is_removed,
                                    is_system=is_system)
        elif isinstance(u_file_or_path, UploadedFile):
            u_file = u_file_or_path

        if u_file is not None and not u_file.is_directory:
            raise ValueError('Not a directory')

        path = u_file.path if u_file is not None else u_file_or_path
        for _path, _file in list(self.files.items(is_ancillary=is_ancillary,
                                                  is_removed=is_removed,
                                                  is_system=is_system)):
            if _path.startswith(path) and not _path == path:
                if max_depth is not None:
                    if path != '':
                        remainder = _path.split(path, 1)[1]
                    else:
                        remainder = _path
                    if len(remainder.strip('/').split('/')) > max_depth:
                        continue
                yield _path, _file

    def iter_files(self, allow_ancillary: bool = True,
                   allow_removed: bool = False,
                   allow_directories: bool = False,
                   allow_system: bool = False) -> Iterable[UploadedFile]:
        """Get an iterator over :class:`.UploadFile`s in this workspace."""
        return [f for f in self.files
                if (allow_directories or not f.is_directory)
                and (allow_removed or not f.is_removed)
                and (allow_ancillary or not f.is_ancillary)
                and (allow_system or not f.is_system)]  

    @modifies_workspace
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
        self.log.info('********** Delete Workspace ************\n')

        # Think about stashing source.log, otherwise any logging is fruitless
        # since we are deleting all files under workspace.
        # Let's stash a copy of the source.log file (if it exists)
        self.storage.stash_log(self)

        # Now blow away the workspace
        self.storage.delete_workspace(self)
        return True
