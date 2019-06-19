"""Describes the core concepts and domain rules for uploaded content."""

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

from dataclasses import dataclass, field

from arxiv.base import logging
from .file_type import FileType
from .storage import IStorageAdapter
from .checks import IChecker, ICheckingStrategy
from .log import SourceLog
from .package import SourcePackage
from .uploaded_file import UploadedFile
logger = logging.getLogger(__name__)
logger.propagate = False


@dataclass
class UploadWorkspace:
    """An upload workspace contains a set of submission source files."""

    # Various state settings

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

    state: Status = field(default=Status.ACTIVE)
    """Status of upload workspace."""

    lock_state: LockState = field(default=LockState.UNLOCKED)
    """Lock state of upload workspace."""

    checkers: List[IChecker] = field(default_factory=list)
    """File checkers that should be applied to all files in the workspace."""

    strategy: Optional[ICheckingStrategy] = field(default=None)
    """Strategy for performing file checks."""

    source_type: SourceType = field(default=SourceType.UNKNOWN)

    _errors: Mapping[str, List[str]] \
        = field(default_factory=lambda: defaultdict(list))
    _warnings: Mapping[str, List[str]] \
        = field(default_factory=lambda: defaultdict(list))

    files: Dict[str, UploadedFile] = field(default_factory=dict)
    """All of the files in this workspace. Keys are path-like."""

    # Data about last upload

    lastupload_start_datetime: Optional[datetime] = field(default=None)
    """When we started processing last upload event."""

    lastupload_completion_datetime: Optional[datetime] = field(default=None)
    """When we completed processing last upload event."""

    lastupload_logs: str = field(default_factory=str)
    """Logs associated with last upload event."""

    lastupload_file_summary: str = field(default_factory=str)
    """Logs associated with last upload event."""

    lastupload_readiness: str = field(default_factory=str)
    """Content readiness status after last upload event."""

    def __post_init__(self) -> None:
        """Make sure that we have all of the required directories."""
        self.storage.makedirs(self, self.source_path)
        self.storage.makedirs(self, self.ancillary_path)
        self.storage.makedirs(self, self.removed_path)
        self._log = SourceLog(self)
        self.source_package = SourcePackage(self)

    @property
    def base_path(self):
        """Relative base path for this workspace."""
        return str(self.upload_id)

    @property
    def source_path(self) -> str:
        """Get the path where source files are deposited."""
        return os.path.join(self.base_path, self.SOURCE_PREFIX)

    @property
    def removed_path(self) -> str:
        """Get path where source archive files get moved when unpacked."""
        return os.path.join(self.base_path, self.REMOVED_PREFIX)

    @property
    def ancillary_path(self) -> str:
        """Get the path where ancillary files are stored."""
        return os.path.join(self.source_path, self.ANCILLARY_PREFIX)

    def get_path(self, u_file_or_path: Union[str, UploadedFile],
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

    def get_full_path(self, u_file_or_path: Union[str, UploadedFile],
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

    def _get_path(self, path: str, is_ancillary: bool = False,
                  is_removed: bool = False, is_system: bool = False) -> str:
        path = path.lstrip('/')
        if is_system:
            return os.path.join(self.base_path, path)
        if is_ancillary:
            return os.path.join(self.ancillary_path, path)
        if is_removed:
            return os.path.join(self.removed_path, path)
        return os.path.join(self.source_path, path)

    def _get_path_from_file(self, u_file: UploadedFile) -> str:
        return self._get_path(u_file.path, is_ancillary=u_file.is_ancillary,
                              is_removed=u_file.is_removed,
                              is_system=u_file.is_system)

    def is_tarfile(self, u_file: UploadedFile) -> bool:
        """Determine whether or not a file is a tarfile."""
        return self.storage.is_tarfile(self, u_file)

    def is_safe(self, path: str) -> bool:
        """Determine whether or not a path is safe to use in this workspace."""
        return self.storage.is_safe(self, path)

    def log(self, message: str) -> None:
        """Add a workspace log entry."""
        self._log.info(message)

    @property
    def has_unchecked_files(self) -> bool:
        """Determine whether there are unchecked files in this workspace."""
        for u_file in self.iter_files(allow_directories=True):
            if not u_file.is_checked:
                return True
        return False

    def exists(self, path: str) -> bool:
        """Determine whether or not a file exists in this workspace."""
        return bool(path in self.files and not self.files[path].is_removed)

    def copy(self, u_file: UploadedFile, new_path: str,
             replace: bool = False) -> UploadedFile:
        """Make a copy of a file."""
        if new_path in self.files:
            if self.files[new_path].is_directory:
                raise ValueError('Directory exists at that path')
            if not replace:
                raise ValueError('File at that path already exists')
        new_file = UploadedFile(self, path=new_path,
                                size_bytes=u_file.size_bytes,
                                file_type=u_file.file_type)
        self.storage.copy(self, u_file, new_file)
        return new_file

    def rename(self, u_file: UploadedFile, new_path: str) -> None:
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

    def iter_children(self, u_file_or_path: Union[str, UploadedFile],
                      max_depth: int = None) \
            -> Iterable[Tuple[str, UploadedFile]]:
        """Get an iterator over path, :class:`.UploadedFile` tuples."""
        # QUESTION: is it really so bad to use non-directories here? Can be
        # like the key-prefix for S3. --Erick 2019-06-11.
        if isinstance(u_file_or_path, str) and u_file_or_path in self.files:
            if not self.files['u_file_or_path'].is_directory:
                raise ValueError('Not a directory')
        elif isinstance(u_file_or_path, UploadedFile):
            if not u_file_or_path.is_directory:
                raise ValueError('Not a directory')
            path = u_file_or_path.path
        else:
            path = u_file_or_path

        for _path, _file in list(self.files.items()):
            if _path.startswith(path) and not _path == path:
                if max_depth is not None:
                    if path != '':
                        remainder = _path.split(path, 1)[1]
                    else:
                        remainder = _path
                    if len(remainder.strip('/').split('/')) > max_depth:
                        continue
                yield _path, _file

    def _update_refs(self, u_file: UploadedFile, from_path: str) -> None:
        self.files.pop(from_path)   # Discard old ref.
        self.files[u_file.path] = u_file
        self._errors[u_file.path] += self._errors.pop(from_path, [])
        self._warnings[u_file.path] += self._warnings.pop(from_path, [])

    def _drop_refs(self, from_path: str) -> None:
        self.files.pop(from_path, None)
        self._errors.pop(from_path, None)
        self._warnings.pop(from_path, None)

    @property
    def errors(self) -> Mapping[str, List[str]]:
        return {path: errors for path, errors in self._errors.items()
                if path in self.files and self.files[path].is_active}

    @property
    def warnings(self) -> Mapping[str, List[str]]:
        return {path: warnings for path, warnings in self._warnings.items()
                if path in self.files}

    @property
    def readiness(self) -> Readiness:
        """Readiness state of the upload workspace."""
        if self.has_errors:
            return UploadWorkspace.Readiness.ERRORS
        elif self.has_warnings:
            return UploadWorkspace.Readiness.READY_WITH_WARNINGS
        return UploadWorkspace.Readiness.READY

    def remove(self, u_file: UploadedFile, reason: Optional[str] = None,
               keep_refs: bool = True) -> None:
        """
        Mark a file as removed, and quarantine.

        This is not the same as deletion.
        """
        if reason is None:
            reason = f"Removed file '{u_file.name}'."
        logger.debug('Remove file %s: %s', u_file.path, reason)
        self.storage.remove(self, u_file)
        u_file.is_removed = True
        u_file.reason_for_removal = reason
        if u_file.is_directory:
            for former_path, _file in self.iter_children(u_file):
                _file.is_removed = True
        self.add_non_file_warning(reason)
        if not keep_refs:
            self._drop_refs(u_file.path)

    def persist(self, u_file: UploadedFile) -> None:
        self.storage.persist(self, u_file, self.get_path(u_file))

    def add_files(self, *u_files: UploadedFile) -> None:
        """Add new :class:`.UploadedFile`s to this workspace."""
        for u_file in u_files:
            parts = u_file.path.split('/')
            for parent in accumulate(parts, lambda *p: os.path.join(*p)):
                parent += '/'
                if not self.exists(parent):
                    self.create(parent, FileType.DIRECTORY, is_directory=True)
            self.files[u_file.path] = u_file
        self.strategy.check(self, self.checkers)

    def add_error(self, u_file: UploadedFile, message: str) -> None:
        """Add an error for a specific file."""
        u_file.errors.append(message)
        self._errors[u_file.path].append(message)

    def add_non_file_error(self, message: str) -> None:
        """Add an error for the workspace that is not specific to a file."""
        self._errors['__all__'].append(message)

    def add_warning(self, u_file: UploadedFile, message: str) -> None:
        """Add a warning for a specific file."""
        u_file.warnings.append(message)
        self._warnings[u_file.path].append(message)

    def add_non_file_warning(self, message: str) -> None:
        """Add a warning for the workspace that is not specific to a file."""
        self._warnings['__all__'].append(message)

    def iter_files(self, allow_ancillary: bool = True,
                   allow_removed: bool = False,
                   allow_directories: bool = False) -> Iterable[UploadedFile]:
        """Get an iterator over :class:`.UploadFile`s in this workspace."""
        return [f for f in self.files.values()
                if (allow_ancillary or not f.is_ancillary)
                and (allow_removed or not f.is_removed)
                and (allow_directories or not f.is_directory)]

    @property
    def file_count(self) -> int:
        """Get the total number of non-ancillary files in this workspace."""
        return len([f for f in self.iter_files()
                    if not f.is_ancillary
                    and not f.is_removed
                    and not f.is_directory])

    @property
    def last_modified(self) -> datetime:
        """Time of the most recent change to a file in the workspace."""
        most_recent = max(os.path.getmtime(root) for root, _, _
                          in os.walk(self.source_path))
        return datetime.fromtimestamp(most_recent, tz=UTC)

    @property
    def ancillary_file_count(self) -> int:
        """Get the total number of ancillary files in this workspace."""
        return len([f for f in self.iter_files()
                    if f.is_ancillary and not f.is_removed])

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

    @contextmanager
    def open(self, u_file: UploadedFile, flags: str = 'r', **kwargs: Any) \
            -> Iterator[io.IOBase]:
        """Get a file pointer for a :class:`.UploadFile`."""
        if u_file.path not in self.files and not u_file.is_system:
            raise ValueError('File does not belong to this workspace')
        with self.storage.open(self, u_file, flags, **kwargs) as f:
            yield f
        self.get_size_bytes(u_file)

    LEADING_DOTSLASH = re.compile(r'^\./')
    """Pattern to match leading ``./`` in relative paths."""

    def create(self, path: str, file_type: FileType = FileType.UNKNOWN,
               replace: bool = False,
               is_directory: bool = False,
               is_ancillary: Optional[bool] = None,
               is_system: bool = False,
               touch: bool = True) -> UploadedFile:
        """Create a new :class:`.UploadedFile` at ``path``."""
        path = self.LEADING_DOTSLASH.sub('', path)
        logger.debug('Create a file at %s with type %s', path, file_type.value)
        if path in self.files:
            if self.files[path].is_directory:
                raise ValueError('Directory exists at that path')
            if not replace:
                raise ValueError('File at that path already exists')

        if is_ancillary is None:    # Infer whether this is an ancillary file.
            if path.startswith(self.ANCILLARY_PREFIX):
                logger.debug('Path indicates an ancillary file')
                is_ancillary = True
                _, path = path.split(self.ANCILLARY_PREFIX, 1)
                path = path.strip('/')
                logger.debug('Path indicates ancillary file; trimmed to `%s`',
                             path)

        u_file = UploadedFile(self, path=path, size_bytes=0,
                              file_type=file_type,
                              is_directory=is_directory,
                              is_ancillary=is_ancillary,
                              is_system=is_system)

        if not is_system:   # System files are not part of the source package.
            self.files[u_file.path] = u_file

        if touch:
            self.storage.create(self, u_file)
        else:
            self.get_size_bytes(u_file)
        return u_file

    def cmp(self, a_file: UploadedFile, b_file: UploadedFile,
            shallow: bool = True) -> bool:
        """Compare the contents of two files."""
        return self.storage.cmp(self, a_file, b_file, shallow=shallow)

    def delete(self, u_file: UploadedFile) -> None:
        """
        Completely delete a file.

        See also :func:`UploadWorkspace.remove`.
        """
        logger.debug('Delete file %s', u_file.path)
        self.storage.delete(self, u_file)
        self._drop_refs(u_file.path)
        if u_file.is_directory:
            for child_path, child_file in self.iter_children(u_file):
                self._drop_refs(child_path)

    def get_size_bytes(self, u_file: UploadedFile) -> int:
        """Get (and update) the size in bytes of a file."""
        u_file.size_bytes = self.storage.get_size_bytes(self, u_file)
        return u_file.size_bytes

    def get_last_modified(self, u_file: UploadedFile) -> datetime:
        return self.storage.get_last_modified(self, u_file)

    def get_checksum(self, u_file: UploadedFile) -> str:
        hash_md5 = md5()
        with self.open(u_file, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return urlsafe_b64encode(hash_md5.digest()).decode('utf-8')

    def replace(self, to_replace: UploadedFile, replace_with: UploadedFile,
                keep_refs: bool = True) -> UploadedFile:
        """Replace a file with another file."""
        self.storage.move(self, replace_with, replace_with.path,
                          to_replace.path)

        if not keep_refs:
            self._drop_refs(to_replace.path)
        old_path = replace_with.path
        replace_with.path = to_replace.path
        self._update_refs(replace_with, old_path)
        self.files[replace_with.path] = replace_with

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

    def get(self, path: str, is_system: bool = False) -> UploadedFile:
        """Get a file at ``path``."""
        if is_system:
            # Create a description of the file, since system files are not part
            # of the source package.
            return self.create(path, is_system=is_system, touch=True)
        return self.files[path]

    @property
    def has_warnings(self):
        """Determine whether or not this workspace has warnings."""
        return len([w for warnings in self.warnings.values()
                    for w in warnings]) > 0

    @property
    def has_errors(self):
        """Determine whether or not this workspace has errors."""
        return len([e for errors in self.errors.values() for e in errors]) > 0

    def perform_checks(self) -> None:
        """Perform all checks on this workspace using the assigned strategy."""
        self.strategy.check(self, *self.checkers)

    @property
    def is_single_file_submission(self):
        """Indicate whether or not this is a valid single-file submission."""
        if self.file_count != 1:
            return False
        counts = self.get_file_type_counts()
        if counts['ignore'] == 1:
            return False
        return True

    @property
    def is_locked(self) -> bool:
        return bool(self.lock_state == UploadWorkspace.LockState.LOCKED)

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
