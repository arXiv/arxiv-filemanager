"""Provides :class:`.BaseWorkspace`."""

import os
from base64 import urlsafe_b64encode
from contextlib import contextmanager
from datetime import datetime
from hashlib import md5
from typing import Iterable, Union, Optional, Tuple, List, Any, Dict, \
    Callable, Iterator, IO, TypeVar, cast

from dataclasses import dataclass, field
from pytz import UTC
from typing_extensions import Protocol

from ..uploaded_file import UserFile
from ..index import FileIndex
from .util import modifies_workspace


WorkspaceType = TypeVar('WorkspaceType', bound='BaseWorkspace')


class IBaseWorkspace(Protocol):  # pylint: disable=too-many-public-methods
    """Defines the base workspace API."""

    created_datetime: datetime
    """When workspace was created"""

    files: FileIndex = field(default_factory=FileIndex)
    """Index of all of the files in this workspace."""

    last_upload_completion_datetime: Optional[datetime]
    """When we completed processing last upload event."""

    last_upload_logs: str
    """Logs associated with last upload event."""

    last_upload_file_summary: str
    """Logs associated with last upload event."""

    last_upload_start_datetime: Optional[datetime]
    """When we started processing last upload event."""

    modified_datetime: datetime
    """When workspace was last modified"""

    owner_user_id: str
    """User id for owner of workspace."""

    upload_id: int
    """Unique ID for the upload workspace."""

    @property
    def ancillary_path(self) -> str:
        """Get the path where ancillary files are stored."""

    @property
    def base_path(self) -> str:
        """Relative base path for this workspace."""

    @property
    def last_modified(self) -> Optional[datetime]:
        """Time of the most recent change to a file in the workspace."""

    @property
    def removed_path(self) -> str:
        """Get path where source archive files get moved when unpacked."""

    @property
    def size_bytes(self) -> int:
        """Total size of the source content (including ancillary files)."""

    @property
    def source_path(self) -> str:
        """Get the path where source files are deposited."""

    # I would prefer that this were defined as an attribute, but see
    # https://github.com/python/mypy/issues/4125
    @property
    def storage(self) -> 'IStorageAdapter':
        """Get the storage adapter for this workspace."""

    def cmp(self, a_file: UserFile,
            b_file: UserFile, shallow: bool = True) -> bool:
        """Compare the contents of two files."""

    def exists(self, path: str, is_ancillary: bool = False,
               is_removed: bool = False, is_system: bool = False) -> bool:
        """Determine whether or not a file exists in this workspace."""

    def get_checksum(self, u_file: UserFile) -> str:
        """Get the urlsafe base64-encoded MD5 hash of the file contents."""

    def get(self, path: str, is_ancillary: Optional[bool] = None,
            is_removed: bool = False, is_system: bool = False) -> UserFile:
        """Get a file at ``path``."""

    def get_full_path(self, u_file_or_path: Union[str, UserFile],
                      is_ancillary: bool = False,
                      is_removed: bool = False,
                      is_persisted: bool = False,
                      is_system: bool = False) -> str:
        """Get the absolute path to a :class:`.UserFile`."""

    def get_last_modified(self, u_file: UserFile) -> datetime:
        """Get the datetime when a :class:`.UserFile` was last modified."""

    def get_path(self, u_file_or_path: Union[str, UserFile],
                 is_ancillary: bool = False, is_removed: bool = False,
                 is_system: bool = False, **kwargs: Any) -> str:
        """Get the path to an :class:`.UserFile` in this workspace."""

    def get_public_path(self, u_file: UserFile) -> str:
        """Get the public path for a file in the workspace."""

    def get_size_bytes(self, u_file: UserFile) -> int:
        """Get (and update) the size in bytes of a file."""

    def is_ancillary_path(self, path: str) -> Tuple[str, bool]:
        """Determine whether or not ``path`` is an ancillary path."""

    def is_tarfile(self, u_file: UserFile) -> bool:
        """Determine whether or not a file is a tarfile."""

    def iter_children(self, u_file_or_path: Union[str, UserFile],
                      max_depth: Optional[int] = None,
                      is_ancillary: bool = False,
                      is_removed: bool = False,
                      is_system: bool = False) -> Iterable[Tuple[str,
                                                                 UserFile]]:
        """Get an iterator over (path, :class:`.UserFile`) tuples."""

    def iter_files(self, allow_ancillary: bool = True,
                   allow_removed: bool = False,
                   allow_directories: bool = False,
                   allow_system: bool = False) -> List[UserFile]:
        """Get an iterator over :class:`.UploadFile`s in this workspace."""

    @contextmanager
    def open(self, u_file: UserFile, flags: str = 'r',
             **kwargs: Any) -> Iterator[IO]:
        """Get a file pointer for a :class:`.UploadFile`."""

    def open_pointer(self, u_file: UserFile, flags: str = 'r',
                     **kwargs: Any) -> IO:
        """Get an open file pointer to a file on disk."""

    def pack_source(self, u_file: UserFile) -> UserFile:
        """Pack the source + ancillary content of a workspace as a tarball."""

    def set_last_modified(self, u_file: UserFile,
                          modified: Optional[datetime] = None) -> None:
        """Set the last modified time on a :class:`UserFile`."""


class IStorageAdapter(Protocol):  # pylint: disable=too-many-public-methods
    """Responsible for providing a data access interface."""

    PARAMS: Tuple[str, ...]
    deleted_logs_path: str

    def __init__(self, *args: Any, **kwargs: Any) -> None:  # pylint: disable=super-init-not-called
        """Initialize with implementation-specific configuration params."""

    def cmp(self, workspace: Any, a_file: UserFile,
            b_file: UserFile, shallow: bool = True) -> bool:
        """Compare the contents of two files."""

    def copy(self, workspace: Any, u_file: UserFile,
             new_file: UserFile) -> None:
        """Copy the contents of ``u_file`` into ``new_file``."""

    def create(self, workspace: Any, u_file: UserFile) -> None:
        """
        Create a file.

        Creates any non-existant directories in the path.
        """

    def delete(self, workspace: Any,
               u_file: UserFile) -> None:
        """Permanently delete a file or directory."""

    def delete_all(self, workspace: Any) -> None:
        """Delete all files in the workspace."""

    def delete_workspace(self, workspace: Any) -> None:
        """Completely delete a workspace and all of its contents."""

    def get_last_modified(self, workspace: Any,
                          u_file: UserFile) -> datetime:
        """Get the datetime when a file was last modified."""

    def get_path(self, workspace: Any,
                 u_file_or_path: Union[str, UserFile],
                 is_ancillary: bool = False,
                 is_removed: bool = False,
                 is_persisted: bool = False,
                 is_system: bool = False) -> str:
        """Get the absolute path to an :class:`.UserFile`."""

    def get_size_bytes(self, workspace: Any, u_file: UserFile) -> int:
        """Get the size of a file in bytes."""

    def is_safe(self, workspace: Any, path: str,
                is_ancillary: bool = False, is_removed: bool = False,
                is_persisted: bool = False, is_system: bool = False,
                strict: bool = True) -> bool:
        """Determine whether or not a path is safe to use."""

    def is_tarfile(self, workspace: Any, u_file: UserFile) -> bool:
        """Determine whether or not a file can be opened with ``tarfile``."""

    def makedirs(self, workspace: Any, path: str) -> None:
        """Make directories recursively for ``path`` if they don't exist."""

    def move(self, workspace: Any, u_file: UserFile,
             from_path: str, to_path: str) -> None:
        """Move a file from one path to another."""

    @contextmanager
    def open(self, workspace: Any, u_file: UserFile,
             flags: str = 'r', **kwargs: Any) -> Iterator[IO]:
        """
        Get an open file pointer to a file on disk.

        To be used as a context manager. For example:

        .. code-block:: python

           with storage.open(workspace, u_file) as f:
               f.read()

        """

    def open_pointer(self, workspace: Any, u_file: UserFile,
                     flags: str = 'r', **kwargs: Any) -> IO[Any]:
        """Get an open file pointer to a file on disk."""

    def pack_tarfile(self, workspace: Any, u_file: UserFile,
                     path: str) -> UserFile:
        """Pack ``path`` into ``u_file`` as a tarball."""

    def persist(self, workspace: Any, u_file: UserFile) -> None:
        """
        Persist a file.

        The file should be available on subsequent requests.
        """

    def remove(self, workspace: Any, u_file: UserFile) -> None:
        """Remove a file."""

    def set_last_modified(self, workspace: Any,
                          u_file: UserFile, modified: datetime) -> None:
        """Set the modification datetime on a file."""

    def set_permissions(self, workspace: Any,
                        file_mode: int = 0o664, dir_mode: int = 0o775) -> None:
        """Set permissions for files and directories in a workspace."""

    def stash_deleted_log(self, workspace: Any, u_file: UserFile) -> None:
        """Stash the log file ``u_file`` (e.g. when deleting a workspace)."""

    def unpack_tarfile(self, workspace: Any, u_file: UserFile,
                       path: str) -> None:
        """Unpack tarfile ``u_file`` into ``path``."""


@dataclass  # pylint: disable=too-few-public-methods
class _BaseFields:
    upload_id: int
    """Unique ID for the upload workspace."""

    owner_user_id: str
    """User id for owner of workspace."""

    created_datetime: datetime
    """When workspace was created"""

    modified_datetime: datetime
    """When workspace was last modified"""


@dataclass  # pylint: disable=too-few-public-methods
class _BaseFieldsWithDefaults:
    files: FileIndex = field(default_factory=FileIndex)
    """Index of all of the files in this workspace."""

    SOURCE_PREFIX: str = field(default='src')
    """The name of the source directory within the upload workspace."""

    REMOVED_PREFIX: str = field(default='removed')
    """The name of the removed directory within the upload workspace."""

    ANCILLARY_PREFIX: str = field(default='anc')
    """The directory within source directory where ancillary files are kept."""

    _storage: Optional['IStorageAdapter'] = field(default=None)
    """Adapter for persistence."""

    last_upload_start_datetime: Optional[datetime] = field(default=None)
    """When we started processing last upload event."""

    last_upload_completion_datetime: Optional[datetime] = field(default=None)
    """When we completed processing last upload event."""

    last_upload_logs: str = field(default_factory=str)
    """Logs associated with last upload event."""

    last_upload_file_summary: str = field(default_factory=str)
    """Logs associated with last upload event."""


@dataclass  # pylint: disable=too-many-public-methods
class BaseWorkspace(_BaseFieldsWithDefaults, _BaseFields, IBaseWorkspace):
    """
    Base class for upload workspaces.

    Provides a foundational :class:`.FileIndex` at :attr:`.files`, plus some
    core methods that depend on the index.
    """

    @classmethod
    def args_from_dict(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Pluck workspace constructor args from a dict."""
        return {
            'upload_id': data['upload_id'],
            'owner_user_id': data['owner_user_id'],
            'created_datetime': data['created_datetime'],
            'modified_datetime': data['modified_datetime'],
            'last_upload_start_datetime': data.get('last_upload_start_datetime'),
            'last_upload_completion_datetime':
                data.get('last_upload_completion_datetime'),
            'last_upload_logs': data.get('last_upload_logs'),
            'last_upload_file_summary': data.get('last_upload_file_summary')
        }

    @classmethod
    def post_from_dict(cls, workspace: WorkspaceType,
                       data: Dict[str, Any]) -> None:
        """Update the workspace after it has been loaded from a dict."""
        _files = data.get('files')
        if _files:
            workspace.files = FileIndex(
                source={p: UserFile.from_dict(d, workspace)
                        for p, d in _files['source'].items()},
                ancillary={p: UserFile.from_dict(d, workspace)
                        for p, d in _files['ancillary'].items()},
                removed={p: UserFile.from_dict(d, workspace)
                        for p, d in _files['removed'].items()},
                system={p: UserFile.from_dict(d, workspace)
                        for p, d in _files['system'].items()}
            )

    @classmethod
    def to_dict_impl(cls, self: 'BaseWorkspace') -> Dict[str, Any]:
        """Generate a dict representation of the workspace."""
        return {
            'upload_id': self.upload_id,
            'owner_user_id': self.owner_user_id,
            'created_datetime': self.created_datetime,
            'modified_datetime': self.modified_datetime,
            'files': {'source': {p: f.to_dict()
                                 for p, f in self.files.source.items()},
                      'ancillary': {p: f.to_dict()
                                    for p, f in self.files.ancillary.items()},
                      'removed': {p: f.to_dict()
                                  for p, f in self.files.removed.items()},
                      'system': {p: f.to_dict()
                                 for p, f in self.files.system.items()}},
             'last_upload_start_datetime': self.last_upload_start_datetime,
            'last_upload_completion_datetime':
                self.last_upload_completion_datetime,
            'last_upload_logs': self.last_upload_logs,
            'last_upload_file_summary': self.last_upload_file_summary
        }

    @property
    def ancillary_path(self) -> str:
        """Get the path where ancillary files are stored."""
        return os.path.join(self.source_path, self.ANCILLARY_PREFIX)

    @property
    def base_path(self) -> str:
        """Relative base path for this workspace."""
        return str(self.upload_id)

    @property
    def last_modified(self) -> Optional[datetime]:
        """Time of the most recent change to a file in the workspace."""
        files_last_modified = [f.last_modified for f in self.iter_files()]
        if not files_last_modified:
            return None
        _mod: datetime = max(files_last_modified + [self.modified_datetime])
        return _mod

    @property
    def removed_path(self) -> str:
        """Get path where source archive files get moved when unpacked."""
        return os.path.join(self.base_path, self.REMOVED_PREFIX)

    @property
    def size_bytes(self) -> int:
        """Total size of the source content (including ancillary files)."""
        return sum([f.size_bytes for f in self.iter_files()])

    @property
    def source_path(self) -> str:
        """Get the path where source files are deposited."""
        return os.path.join(self.base_path, self.SOURCE_PREFIX)

    @property
    def storage(self) -> 'IStorageAdapter':
        """Get the storage adapter for this workspace."""
        if self._storage is None:
            raise RuntimeError('No storage adapter set on workspace')
        return self._storage

    def is_ancillary_path(self, path: str) -> Tuple[str, bool]:
        """
        Determine whether or not ``path`` is an ancillary path.

        Parameters
        ----------
        path : str
            A (relative) path. Need not refer to a file that already exists in
            the workspace.

        Returns
        -------
        str
            The ``path`` that was passed. If ``path`` is to an ancillary file,
            the ancillary affix is removed.
        bool
            True if ``path`` was ancillary. False otherwise.

        """
        if path.startswith(self.ANCILLARY_PREFIX):
            _, path = path.split(self.ANCILLARY_PREFIX, 1)
            path = path.strip('/')
            return path, True
        return path, False

    def cmp(self, a_file: UserFile,
            b_file: UserFile, shallow: bool = True) -> bool:
        """Compare the contents of two files."""
        return self.storage.cmp(self, a_file, b_file, shallow=shallow)

    def exists(self, path: str, is_ancillary: bool = False,
               is_removed: bool = False, is_system: bool = False) -> bool:
        """Determine whether or not a file exists in this workspace."""
        return self.files.contains(path, is_ancillary=is_ancillary,
                                   is_removed=is_removed,
                                   is_system=is_system)

    def get(self, path: str, is_ancillary: Optional[bool] = None,
            is_removed: bool = False, is_system: bool = False) -> UserFile:
        """Get a file at ``path``."""
        if is_ancillary is None:
            path, is_ancillary = self.is_ancillary_path(path)
        return self.files.get(path, is_ancillary=is_ancillary,
                                    is_removed=is_removed,
                                    is_system=is_system)

    def get_checksum(self, u_file: UserFile) -> str:
        """Get the urlsafe base64-encoded MD5 hash of the file contents."""
        hash_md5 = md5()
        with self.open(u_file, "rb") as f:
            for chunk in iter(lambda: bytes(f.read(4096)), b""):
                hash_md5.update(chunk)
        return urlsafe_b64encode(hash_md5.digest()).decode('utf-8')

    def get_full_path(self, u_file_or_path: Union[str, UserFile],
                      is_ancillary: bool = False,
                      is_removed: bool = False,
                      is_persisted: bool = False,
                      is_system: bool = False) -> str:
        """Get the absolute path to a :class:`.UserFile`."""
        return self.storage.get_path(self, u_file_or_path,
                                     is_ancillary=is_ancillary,
                                     is_removed=is_removed,
                                     is_persisted=is_persisted,
                                     is_system=is_system)

    def get_last_modified(self, u_file: UserFile) -> datetime:
        """Get the datetime when a :class:`.UserFile` was last modified."""
        u_file.last_modified = self.storage.get_last_modified(self, u_file)
        return u_file.last_modified

    def get_path(self, u_file_or_path: Union[str, UserFile],
                 is_ancillary: bool = False, is_removed: bool = False,
                 is_system: bool = False, **kwargs: Any) -> str:
        """Get the path to an :class:`.UserFile` in this workspace."""
        if isinstance(u_file_or_path, UserFile):
            path = self._get_path_from_file(u_file_or_path)
        else:
            path = self._get_path(u_file_or_path, is_ancillary=is_ancillary,
                                  is_removed=is_removed, is_system=is_system)
        return path.lstrip('/')

    def get_public_path(self, u_file: UserFile) -> str:
        """Get the public path for a file in the workspace."""
        if u_file.is_ancillary:
            return os.path.join(self.ANCILLARY_PREFIX, u_file.path)
        return u_file.path

    def get_size_bytes(self, u_file: UserFile) -> int:
        """Get (and update) the size in bytes of a file."""
        size_bytes: int = self.storage.get_size_bytes(self, u_file)
        u_file.size_bytes = size_bytes
        return size_bytes

    def is_safe(self, path: str, is_ancillary: bool = False,
                is_removed: bool = False, is_persisted: bool = False,
                is_system: bool = False, strict: bool = True) -> bool:
        """Determine whether or not a path is safe to use in this workspace."""
        return self.storage.is_safe(self, path, is_ancillary=is_ancillary,
                                    is_removed=is_removed,
                                    is_persisted=is_persisted,
                                    is_system=is_system, strict=strict)

    def is_tarfile(self, u_file: UserFile) -> bool:
        """Determine whether or not a file is a tarfile."""
        return self.storage.is_tarfile(self, u_file)

    def iter_children(self, u_file_or_path: Union[str, UserFile],
                      max_depth: Optional[int] = None,
                      is_ancillary: bool = False,
                      is_removed: bool = False,
                      is_system: bool = False) -> Iterable[Tuple[str,
                                                                 UserFile]]:
        """Get an iterator over (path, :class:`.UserFile`) tuples."""
        # QUESTION: is it really so bad to use non-directories here? Can be
        # like the key-prefix for S3. --Erick 2019-06-11.
        u_file: Optional[UserFile] = None
        if isinstance(u_file_or_path, str) \
                and self.files.contains(u_file_or_path,
                                        is_ancillary=is_ancillary,
                                        is_removed=is_removed,
                                        is_system=is_system):
            u_file = self.files.get(u_file_or_path,
                                    is_ancillary=is_ancillary,
                                    is_removed=is_removed,
                                    is_system=is_system)
        elif isinstance(u_file_or_path, UserFile):
            u_file = u_file_or_path

        if u_file is not None and not u_file.is_directory:
            raise ValueError('Not a directory')

        path: str = str(u_file.path if u_file is not None else u_file_or_path)
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
                   allow_system: bool = False) -> List[UserFile]:
        """Get an iterator over :class:`.UploadFile`s in this workspace."""
        return [f for f in self.files
                if (allow_directories or not f.is_directory)
                and (allow_removed or not f.is_removed)
                and (allow_ancillary or not f.is_ancillary)
                and (allow_system or not f.is_system)]

    @contextmanager
    @modifies_workspace()
    def open(self, u_file: UserFile, flags: str = 'r',
             **kwargs: Any) -> Iterator[IO]:
        """Get a file pointer for a :class:`.UploadFile`."""
        if not self.files.contains(
                u_file.path,
                is_ancillary=u_file.is_ancillary,
                is_system=u_file.is_system,
                is_removed=u_file.is_removed):
            raise ValueError('No such file')
        with self.storage.open(self, u_file, flags, **kwargs) as f:
            yield f
        self.get_size_bytes(u_file)
        self.get_last_modified(u_file)

    def open_pointer(self, u_file: UserFile, flags: str = 'r',
                     **kwargs: Any) -> IO:
        return self.storage.open_pointer(self, u_file, flags, **kwargs)

    def pack_source(self, u_file: UserFile) -> UserFile:
        """Pack the source + ancillary content of a workspace as a tarball."""
        return self.storage.pack_tarfile(self, u_file, self.source_path)

    def set_last_modified(self, u_file: UserFile,
                          modified: Optional[datetime] = None) -> None:
        """Set the last modified time on a :class:`UserFile`."""
        if modified is None:
            modified = datetime.now(UTC)
        self.storage.set_last_modified(self, u_file, modified)

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

    def _get_path_from_file(self, u_file: UserFile) -> str:
        return self._get_path(u_file.path, is_ancillary=u_file.is_ancillary,
                              is_removed=u_file.is_removed,
                              is_system=u_file.is_system)

