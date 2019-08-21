"""Adds checkpoint functionality to the upload workspace."""

import os
from contextlib import contextmanager
from datetime import datetime
from json import dump, load
from typing import IO, List, TypeVar, Type, Iterable, Any, Optional, Dict, \
    Callable, Iterator, cast

from dataclasses import dataclass, field
from typing_extensions import Protocol

# Not sure why we're running into issues with namespace packages here.
from arxiv.users.domain import User  # pylint: disable=no-name-in-module
from arxiv.util.serialize import ISO8601JSONEncoder, ISO8601JSONDecoder  # pylint: disable=no-name-in-module

from .base import IBaseWorkspace
from .exceptions import UploadFileSecurityError, NoSourceFilesToCheckpoint
from ..error import Error, Severity
from ..uploaded_file import UserFile

UPLOAD_WORKSPACE_IS_EMPTY = 'workspace is empty'
UPLOAD_FILE_NOT_FOUND = 'file not found'
UPLOAD_CHECKPOINT_FILE_NOT_FOUND = 'checkpoint file not found'

T = TypeVar('T')

class ILog(Protocol):
    def info(self, message: str) -> None:
        ...


class IFiles(Protocol):
    source: Dict[str, UserFile]
    ancillary: Dict[str, UserFile]


class IStorage(Protocol):
    def unpack_tarfile(self, workspace: 'Checkpointable',
                       u_file: UserFile, path: str) -> None:
        """Unpack tarfile ``u_file`` into ``path``."""
        ...


class IWorkspace(IBaseWorkspace, Protocol):
    """
    Workspace API required for :class:`.Checkable`.

    This incorporates the base API and any additional structures that require
    implementation by other components of the workspace.
    """

    errors: List[Error]
    log: ILog

    def add_warning_non_file(self, msg: str,
                             is_persistant: bool = False) -> None:
        """Add a warning for the workspace that is not specific to a file."""

    def add_error_non_file(self, msg: str, severity: Severity = Severity.FATAL,
                           is_persistant: bool = True) -> None:
        """Add an error for the workspace that is not specific to a file."""

    def create(self, path: str, is_system: bool = False,
               is_persisted: bool = False, touch: bool = True) -> UserFile:
        """Create a new :class:`.UserFile` at ``path``."""

    def to_dict(self) -> Dict[str, Any]:
        """Generate a dict representation of a workspace."""

    def delete(self, u_file: UserFile) -> None:
        """Completely delete a file."""

    def delete_all_files(self) -> None:
        """Delete all source and ancillary files in the workspace."""


class ICheckpointable(Protocol):
    """Interface for checkpointable behavior."""

    @property
    def checkpoint_directory(self) -> str:
        """Get directory where checkpoint archive files live."""

    def checkpoint_file_exists(self, checksum: str) -> bool:
        """Indicate whether checkpoint files exists."""

    def create_checkpoint(self, user: User) -> str:
        """Create a chckpoint (backup) of workspace source files."""

    def delete_all_checkpoints(self, user: User) -> None:
        """Remove all checkpoints."""

    def delete_checkpoint(self, checksum: str, user: User) -> None:
        """Remove specified checkpoint."""

    def get_checkpoint_file(self, checksum: str) -> UserFile:
        """Get a checkpoint file."""

    def get_checkpoint_file_last_modified(self, checksum: str) -> datetime:
        """Return last modified time for specified file/package."""

    def get_checkpoint_file_pointer(self, checksum: str) -> IO[bytes]:
        """Open specified file and return file pointer."""

    def get_checkpoint_file_size(self, checksum: str) -> int:
        """Return size of specified checkpoint file."""

    def list_checkpoints(self, user: User) -> List[UserFile]:
        """Generate a list of checkpoints."""


class ICheckpointableWorkspace(IWorkspace, ICheckpointable, Protocol):
    """Structure of a workspace with checkpointable behavior."""


@dataclass
class Checkpointable(ICheckpointable):
    """
    Adds checkpoint routines to the workspace.

    Manage creating, viewing, removing, and restoring checkpoints.

    checksum might be useful as key to identify specific checkpoint.

    TODO: Should we support admin provided description of checkpoint?
    """

    CHECKPOINT_PREFIX: str = field(default='checkpoint')
    """The name of the checkpoint directory within the upload workspace."""

    # Allow maximum number of checkpoints (100?)
    MAX_CHECKPOINTS: int = field(default=10)  # Use 10 for testing

    __internal_api = None

    def __api_init__(self, api: IWorkspace) -> None:
        """Register the workspace API."""
        if hasattr(super(Checkpointable, self), '__api_init__'):
            super(Checkpointable, self).__api_init__(api)   # type: ignore
        self.__internal_api = api

    @property
    def __api(self) -> IWorkspace:
        assert self.__internal_api is not None
        return self.__internal_api

    @classmethod
    def from_dict(cls: Type[T], upload_data: dict) -> T:
        raise NotImplementedError('Must be combined with seomthing that'
                                  ' implements from_dict')

    @property
    def checkpoint_directory(self) -> str:
        """Get directory where checkpoint archive files live."""
        return os.path.join(self.__api.base_path, self.CHECKPOINT_PREFIX)

    def checkpoint_file_exists(self, checksum: str) -> bool:
        """
        Indicate whether checkpoint files exists.

        Parameters
        ----------
        checksum : str
            Checksum that uniquely identifies checkpoint.

        Returns
        -------
        bool
            True if file exists, False otherwise.

        """
        try:
            self._get_checkpoint(checksum)
            return True
        except FileNotFoundError:
            return False

    def create_checkpoint(self, user: User) -> str:
        """
        Create a chckpoint (backup) of workspace source files.

        Returns
        -------
        checksum : str
            Checksum for checkpoint tar gzipped archive we just created.

        """
        # Make sure there are files before we bother to create a checkpoint.
        if self._all_file_count == 0:
            raise NoSourceFilesToCheckpoint(UPLOAD_WORKSPACE_IS_EMPTY)

        self.__api.log.info(
            "Creating checkpoint." + (f"['{user.user_id}']" if user else "")
        )

        # Create a new unique filename for checkpoint
        count = self._get_checkpoint_count(user)
        if count >= self.MAX_CHECKPOINTS:
            return ''   # TODO: Need to throw an error here?

        checkpoint = self.__api.create(self._make_path(user, count + 1),
                                       is_system=True, is_persisted=True,
                                       touch=True)
        self.__api.pack_source(checkpoint)

        metadata = self.__api.create(self._make_metadata_path(user, count + 1),
                                     is_system=True, is_persisted=True,
                                     touch=True)
        with self.__api.open(metadata, 'w') as f:
            dump(self.__api.to_dict(), f, cls=ISO8601JSONEncoder)
        return checkpoint.checksum

    def delete_all_checkpoints(self, user: User) -> None:
        """Remove all checkpoints."""
        for checkpoint in self.list_checkpoints(user):
            self.__api.delete(checkpoint)

        log_msg = f"Deleted ALL checkpoints"
        log_msg += f": ['{user.username}']." if user else "."
        self.__api.log.info(log_msg)

    def delete_checkpoint(self, checksum: str, user: User) -> None:
        """Remove specified checkpoint."""
        try:
            checkpoint = self._get_checkpoint(checksum)
        except FileNotFoundError:
            log_msg = f"ERROR: Checkpoint not found: {checksum}"
            log_msg += f"['{user.username}']" if user else "."
            self.__api.log.info(log_msg)
            raise

        self.__api.delete(checkpoint)
        log_msg = f"Deleted checkpoint: {checkpoint.name}"
        log_msg += f"['{user.username}']." if user else "."
        self.__api.log.info(log_msg)

    def get_checkpoint_file(self, checksum: str) -> UserFile:
        """
        Get a checkpoint file.

        Parameters
        ----------
        checksum : str
            Checksum that uniquely identifies checkpoint.

        Returns
        -------
        :class:`.UserFile`

        """
        return self._get_checkpoint(checksum)

    def get_checkpoint_file_last_modified(self, checksum: str) -> datetime:
        """
        Return last modified time for specified file/package.

        Parameters
        ----------
        checksum : str
            Checksum that uniquely identifies checkpoint.

        Returns
        -------
        Last modified date string.
        """
        return self._get_checkpoint(checksum).last_modified

    def get_checkpoint_file_pointer(self, checksum: str) -> IO[bytes]:
        """
        Open specified file and return file pointer.

        Parameters
        ----------
        checksum : str
            Checksum that uniquely identifies checkpoint.

        Returns
        -------
        io.BytesIO
            File pointer or exception string when filepath does not exist.

        """
        return self.__api.open_pointer(self._get_checkpoint(checksum), 'rb')

    def get_checkpoint_file_size(self, checksum: str) -> int:
        """
        Return size of specified file.

        Parameters
        ----------
        checksum : str
            Checksum that uniquely identifies checkpoint.

        Returns
        -------
        Size in bytes.
        """
        u_file = self._get_checkpoint(checksum)
        if u_file is not None:
            return int(u_file.size_bytes)
        raise FileNotFoundError(UPLOAD_CHECKPOINT_FILE_NOT_FOUND)

    def list_checkpoints(self, user: User) -> List[UserFile]:
        """
        Generate a list of checkpoints.

        Returns
        -------
        list
            list of checkpoint files, includes date/time checkpoint was
            created and checksum key.

        TODO: include description? or make one up on the fly?

        """
        if user:
            log_msg = f'Created list of checkpoints [{user.username}].'
        else:
            log_msg = 'Created list of checkpoints.'
        self.__api.log.info(log_msg)
        return [u for u in self.__api.iter_files(allow_system=True)
                if u.is_system
                and u.path.startswith(self.CHECKPOINT_PREFIX)
                and u.path.endswith('.tar.gz')]

    def restore_checkpoint(self, checksum: str, user: User) -> None:
        """
        Restore a previous checkpoint.

        First we delete all existing files under workspace source directory.

        Next we unpack chackpoint file into src directory.

        TODO: Decide whether to checkpoint source we are restoring over.
        TODO: Probably not. Maybe should checkpoint if someone other than owner
        TODO: is uploading file (forget to select checkpoint) but only if
        TODO: previous upload was by owner.

        """
        # We probably need to remove all existing source files before we
        # extract files from checkpoint zipped tar archive.
        self.__api.delete_all_files()

        # Locate the checkpoint we are interested in.
        try:
            checkpoint = self._get_checkpoint(checksum)
        except FileNotFoundError:
            self.__api.add_error_non_file(
                'Unable to restore checkpoint. Not found.'
            )
            raise
        if self.__api.storage is None:
            raise RuntimeError('Storage not available')
        self.__api.storage.unpack_tarfile(self, checkpoint,
                                          self.__api.source_path)

        # Restore fileindex and errors from previous metadata.
        meta_path = os.path.join(checkpoint.path.replace('.tar.gz', '.json'))
        u_chex_file = self.__api.get(meta_path, is_system=True)
        with self.__api.open(u_chex_file) as f_meta:
            loaded = self.from_dict(load(f_meta, cls=ISO8601JSONDecoder))
            self._update_from_checkpoint(cast(IWorkspace, loaded))

        log_msg = f'Restored checkpoint: {checkpoint.name}'
        log_msg += f' [{user.username}].' if user else '.'
        self.__api.log.info(log_msg)

    @property
    def _all_file_count(self) -> int:
        return len(self.__api.iter_files(allow_ancillary=True))

    def _get_checkpoint_count(self, user: User) -> int:
        count = 0
        while True:
            _path = self._make_path(user, count + 1)
            if not self.__api.exists(_path, is_system=True):
                break
            count += 1
        return count

    def _get_checkpoint_file_path(self, checksum: str) -> str:
        """
        Return the absolute path of content file given relative pointer.

        Parameters
        ----------
        checksum : str
            Checksum that uniquely identifies checkpoint.

        Returns
        -------
        Path to checkpoint specified by unique checksum.

        """
        u_file = self._get_checkpoint(checksum)
        if u_file is not None:
            return u_file.path

        raise FileNotFoundError(UPLOAD_FILE_NOT_FOUND)

    def _is_checkpoint_file(self, u_file: UserFile) -> bool:
        return bool(u_file.is_system
                    and u_file.path.startswith(self.CHECKPOINT_PREFIX))

    def _make_metadata_path(self, user: User, count: int) -> str:
        user_string = f'_{user.username}' if user else ''
        return os.path.join(self.CHECKPOINT_PREFIX,
                            f'checkpoint_{count}{user_string}.json')

    def _make_path(self, user: User, count: int) -> str:
        user_string = f'_{user.username}' if user else ''
        return os.path.join(self.CHECKPOINT_PREFIX,
                            f'checkpoint_{count}{user_string}.tar.gz')

    def _get_checkpoint(self, checksum: str) -> UserFile:
        for u_file in self.__api.iter_files(allow_system=True):
            if not self._is_checkpoint_file(u_file):
                continue
            if u_file.checksum == checksum:
                return u_file
        raise FileNotFoundError(UPLOAD_FILE_NOT_FOUND)

    def _update_from_checkpoint(self, workspace: IWorkspace) -> None:
        self.__api.files.source = workspace.files.source
        self.__api.files.ancillary = workspace.files.ancillary
        for u_file in self.__api.iter_files():
            u_file.workspace = cast(IWorkspace, self)
        self._errors = {(e.path, e.code): e for e in workspace.errors}
