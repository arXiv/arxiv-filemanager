"""Describes the data that will be passed around inside of the service."""

import os
import io
from itertools import accumulate
from typing import List, Callable, Optional, Any, Type, Dict, Mapping, Union, \
    Iterable, Tuple
from collections import defaultdict, Counter
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
from typing_extensions import Protocol

from .file_type import FileType


class IChecker(Protocol):
    """A visitor that performs a check on an :class:`.UploadedFile`."""

    def __call__(self, workspace: 'UploadWorkspace',
                 u_file: 'UploadedFile') -> None:
        """Check an :class:`.UploadedFile`."""
        ...


class ICheckingStrategy(Protocol):
    """Strategy for checking files in an :class:`.UploadWorkspace`."""

    def check(self, workspace: 'UploadWorkspace', *checkers: IChecker) -> None:
        """Perform checks on all files in the workspace."""
        ...


class IStorageAdapter(Protocol):
    """Responsible for providing a data access interface."""

    def move(self, workspace: 'UploadWorkspace', u_file: 'UploadedFile',
             from_path: str, to_path: str) -> None:
        """Move a file from one path to another."""
        ...

    def persist(self, workspace: 'UploadWorkspace',
                u_file: 'UploadedFile') -> None:
        ...

    def get_full_path(self, workspace: 'UploadWorkspace',
                      u_file: 'UploadedFile') -> str:
        ...

    def open(self, workspace: 'UploadWorkspace', u_file: 'UploadedFile',
             flags: str = 'r', **kwargs: Any) -> io.IOBase:
        """
        Get a file pointer for an :class:`.UploadedFile`.

        ``kwargs`` must be passed along to the builtin :func:`open`.
        """
        ...


# TODO: support for directories.
@dataclass
class UploadedFile:
    """Represents a single file in an upload workspace."""

    path: str
    """Path relative to the workspace in which the file resides."""

    size_bytes: int
    file_type: FileType = field(default=FileType.UNKNOWN)
    is_removed: bool = field(default=False)
    is_ancillary: bool = field(default=False)
    is_directory: bool = field(default=False)
    is_checked: bool = field(default=False)
    reason_for_removal: Optional[str] = field(default=None)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)
    """A register for checkers/strategies to store state between runs."""

    def __post_init__(self) -> None:
        """Make sure that directory paths end with '/'."""
        if self.is_directory and not self.path.endswith('/'):
            self.path += '/'

    @property
    def name(self) -> str:
        """File name without path/directory info."""
        return os.path.basename(self.path)

    @property
    def ext(self) -> str:
        """Return file extension."""
        _, ext = os.path.splitext(self.path)
        return ext.lstrip('.')

    @property
    def dir(self) -> str:
        """Directory which contains the file."""
        # if os.path.isfile(self.path):
        return f'{os.path.dirname(self.path)}/'
        # return ''

    @property
    def type_string(self) -> str:
        """Human-readable type name."""
        if self.is_removed:
            return "Invalid File"
        if self.is_directory:
            if self.path == 'anc/':
                return 'Ancillary files directory'
            return 'Directory'
        return self.file_type.name

    @property
    def is_always_ignore(self) -> bool:
        """Determine whether or not this file should be ignored."""
        return self.file_type is FileType.ALWAYS_IGNORE

    @property
    def is_empty(self) -> bool:
        """Indicate whether this file is an empty file."""
        return self.size_bytes == 0


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

    SOURCE_PREFIX = 'src'
    """The name of the source directory within the upload workspace."""

    REMOVED_PREFIX = 'removed'
    """The name of the removed directory within the upload workspace."""

    ANCILLARY_PREFIX = 'anc'
    """The directory within source directory where ancillary files are kept."""

    upload_id: int
    """Unique ID for the upload workspace."""

    submission_id: Optional[str]
    """
    Optionally associate upload workspace with submission_id.

    File Management Service 'upload_id' is independent and not directly
    tied to any external service.
    """

    owner_user_id: str
    """User id for owner of workspace."""

    archive: Optional[str]
    """Target archive for this submission."."""

    created_datetime: datetime
    """When workspace was created"""

    modified_datetime: datetime
    """When workspace was last modified"""

    # General state of upload
    strategy: ICheckingStrategy
    """Strategy for performing file checks."""

    storage: IStorageAdapter
    """Adapter for persistence."""

    state: Status = field(default=Status.ACTIVE)
    """Status of upload workspace."""

    lock: LockState = field(default=LockState.UNLOCKED)
    """Lock state of upload workspace."""

    checkers: List[IChecker] = field(default_factory=list)
    """File checkers that should be applied to all files in the workspace."""

    source_type: SourceType = field(default=SourceType.UNKNOWN)

    errors: Mapping[str, List[str]] \
        = field(default_factory=lambda: defaultdict(list))
    warnings: Mapping[str, List[str]] \
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

    lastupload_upload_status: str = field(default_factory=str)
    """Content readiness status after last upload event."""

    @property
    def source_path(self) -> str:
        """Get path where source files are deposited."""
        return os.path.join(str(self.upload_id), self.SOURCE_PREFIX)

    @property
    def removed_path(self) -> str:
        """Get path where source archive files get moved when unpacked."""
        return os.path.join(str(self.upload_id), self.REMOVED_PREFIX)

    @property
    def ancillary_path(self) -> str:
        """Get path where ancillary files are stored."""
        return os.path.join(self.source_path, self.ANCILLARY_PREFIX)

    def get_path(self, u_file: UploadedFile) -> str:
        """Get path to an :class:`.UploadedFile` in this workspace."""
        if u_file.is_ancillary:
            return os.path.join(self.ancillary_path, u_file.path)
        if u_file.is_removed:
            return os.path.join(self.removed_path, u_file.path)
        return os.path.join(self.source_path, u_file.path)

    def get_full_path(self, u_file: UploadedFile) -> str:
        """Get a full path to an :class:`.UploadedFile`."""
        return self.storage.get_full_path(self, u_file)

    @property
    def has_unchecked_files(self) -> bool:
        """Determine whether there are unchecked files in this workspace."""
        for u_file in self.iter_files():
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
        new_file = UploadedFile(path=new_path,
                                size_bytes=u_file.size_bytes,
                                file_type=u_file.file_type)
        self.storage.copy(self, u_file, new_file)
        return new_file

    def rename(self, u_file: UploadedFile, new_path: str) -> None:
        """Rename a file in this workspace."""
        former_path = u_file.path
        u_file.path = new_path

        self.storage.move(self.get_path(former_path), self.get_path(new_path))
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

    def iter_children(self, u_file: UploadedFile) \
            -> Iterable[Tuple[str, UploadedFile]]:
        """Get an iterator over path, :class:`.UploadedFile` tuples."""
        if not u_file.is_directory:
            raise ValueError('Not a directory')
        for _path, _file in list(self.files.items()):
            if _path.startswith(u_file.path):
                yield _path, _file

    def _update_refs(self, u_file: UploadedFile, from_path: str) -> None:
        self.files.pop(from_path)   # Discard old ref.
        self.files[u_file.path] = u_file
        self.errors[u_file.path] += self.errors.pop(from_path, [])
        self.warnings[u_file.path] += self.warnings.pop(from_path, [])

    def _drop_refs(self, from_path: str) -> None:
        self.files.pop(from_path, None)
        self.errors.pop(from_path, None)
        self.warnings.pop(from_path, None)

    def remove(self, u_file: UploadedFile, reason: Optional[str] = None) \
            -> None:
        """
        Mark a file as removed, and quarantine.

        This is not the same as deletion.
        """
        if reason is None:
            reason = f"Removed file '{u_file.name}'."

        previous_path = self.get_path(u_file)
        u_file.is_removed = True
        u_file.reason_for_removal = reason

        self.storage.move(self, u_file, previous_path, self.get_path(u_file))
        if u_file.is_directory:
            for former_path, _file in self.iter_children(u_file):
                _file.is_removed = True
        self.add_non_file_warning(reason)

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
        self.errors[u_file.path].append(message)

    def add_non_file_error(self, message: str) -> None:
        """Add an error for the workspace that is not specific to a file."""
        self.errors['__all__'].append(message)

    def add_warning(self, u_file: UploadedFile, message: str) -> None:
        """Add a warning for a specific file."""
        u_file.warnings.append(message)
        self.warnings[u_file.path].append(message)

    def add_non_file_warning(self, message: str) -> None:
        """Add a warning for the workspace that is not specific to a file."""
        self.warnings['__all__'].append(message)

    def set_source_type(self, source_type: SourceType,
                        force: bool = False) -> None:
        """
        Set the source type for this workspace.

        If already set to something other than :const:`SourceType.UNKOWN`,
        will not be changed unless ``force``  is ``True``.
        """
        if self.source_type is not self.SourceType.UNKOWN and not force:
            # Nothing to do; already set.
            return
        self.source_type = source_type

    def iter_files(self) -> Iterable[UploadedFile]:
        """Get an iterator over :class:`.UploadFile`s in this workspace."""
        return self.files.values()

    @property
    def file_count(self) -> int:
        """Get the total number of non-ancillary files in this workspace."""
        return len([f for f in self.iter_files()
                    if not f.is_ancillary
                    and not f.is_removed
                    and not f.is_directory])

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
            counts[u_file.file_type] += 1
        counts['files'] = counts['all_files'] - counts['ancillary']
        return counts

    def open(self, u_file: UploadedFile, flags: str = 'r',
             **kwargs: Any) -> io.IOBase:
        """Get a file pointer for a :class:`.UploadFile`."""
        if u_file.path not in self.files:
            raise ValueError('File does not belong to this workspace')
        return self.storage.open(self, u_file, flags, **kwargs)

    def create(self, path: str, file_type: FileType = FileType.UNKNOWN,
               replace: bool = False, is_directory: bool = False,
               is_ancillary: bool = False) -> UploadedFile:
        """Create a new :class:`.UploadedFile` at ``path``."""
        if path in self.files:
            if self.files[path].is_directory:
                raise ValueError('Directory exists at that path')
            if not replace:
                raise ValueError('File at that path already exists')

        u_file = UploadedFile(
            path=path,
            size_bytes=0,
            file_type=file_type,
            is_directory=is_directory,
            is_ancillary=is_ancillary
        )
        self.files[u_file.path] = u_file
        self.storage.create(self, u_file)
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
        self.storage.delete(self, u_file)
        self._drop_refs(u_file.path)
        if u_file.is_directory:
            for child_path, child_file in self.iter_children(u_file):
                self._drop_refs(child_path)

    def getsize(self, u_file: UploadedFile) -> int:
        """Get (and update) the size in bytes of a :class:`.UploadedFile`."""
        u_file.size_bytes = self.storage.getsize(self, u_file)
        return u_file.size_bytes

    def replace(self, to_replace: UploadedFile, replace_with: UploadedFile,
                keep_refs: bool = True) -> UploadedFile:
        self.storage.move(self, replace_with, to_replace.path)
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

    def get(self, path: str) -> UploadedFile:
        """Get a file at ``path``."""
        return self.files[path]

    @property
    def has_warnings(self):
        """Determine whether or not this workspace has warnings."""
        return len(self.warnings) > 0

    @property
    def has_errors(self):
        """Determine whether or not this workspace has errors."""
        return len(self.errors) > 0
