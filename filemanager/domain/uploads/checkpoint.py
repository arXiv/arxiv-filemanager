"""Adds checkpoint functionality to the upload workspace."""

import os
from json import dump, load
from datetime import datetime
from typing import IO, List

from arxiv.users import domain as auth_domain
from arxiv.util.serialize import ISO8601JSONEncoder, ISO8601JSONDecoder

from .file_mutations import FileMutationsWorkspace
from .exceptions import UploadFileSecurityError, NoSourceFilesToCheckpoint
from ..uploaded_file import UploadedFile

UPLOAD_WORKSPACE_IS_EMPTY = 'workspace is empty'
UPLOAD_FILE_NOT_FOUND = 'file not found'
UPLOAD_CHECKPOINT_FILE_NOT_FOUND = 'checkpoint file not found'


class CheckpointWorkspace(FileMutationsWorkspace):
    """
    Adds checkpoint routines to the workspace.

    Manage creating, viewing, removing, and restoring checkpoints.

    checksum might be useful as key to identify specific checkpoint.

    TODO: Should we support admin provided description of checkpoint?
    """

    CHECKPOINT_PREFIX = 'checkpoint'
    """The name of the checkpoint directory within the upload workspace."""

    # Allow maximum number of checkpoints (100?)
    MAX_CHECKPOINTS = 10  # Use 10 for testing

    @property
    def checkpoint_directory(self) -> str:
        """Get directory where checkpoint archive files live."""
        return os.path.join(self.base_path, self.CHECKPOINT_PREFIX)

    def _is_checkpoint_file(self, u_file: UploadedFile) -> bool:
        return bool(u_file.is_system
                    and u_file.path.startswith(self.CHECKPOINT_PREFIX))

    def _resolve_checkpoint_file(self, checksum: str) -> UploadedFile:
        for u_file in self.iter_files(allow_system=True):
            if not self._is_checkpoint_file(u_file):
                continue
            if u_file.checksum == checksum:
                return u_file
        raise FileNotFoundError(UPLOAD_FILE_NOT_FOUND)

    def get_checkpoint_file(self, checksum: str) -> UploadedFile:
        """
        Get a checkpoint file.

        Parameters
        ----------
        checksum : str
            Checksum that uniquely identifies checkpoint.

        Returns
        -------
        :class:`.UploadedFile`

        """
        return self._resolve_checkpoint_file(checksum)

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
        u_file = self._resolve_checkpoint_file(checksum)
        if u_file is not None:
            return u_file.path

        raise FileNotFoundError(UPLOAD_FILE_NOT_FOUND)


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
            self._resolve_checkpoint_file(checksum)
            return True
        except FileNotFoundError:
            return False

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
        u_file = self._resolve_checkpoint_file(checksum)
        if u_file is not None:
            return int(u_file.size_bytes)
        raise FileNotFoundError(UPLOAD_CHECKPOINT_FILE_NOT_FOUND)

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
        return self.open_pointer(self._resolve_checkpoint_file(checksum), 'rb')

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
        return self._resolve_checkpoint_file(checksum).last_modified

    @property
    def _all_file_count(self) -> int:
        return len(self.iter_files(allow_ancillary=True))

    def _make_path(self, user: auth_domain.User, count: int) -> str:
        user_string = f'_{user.username}' if user else ''
        return os.path.join(self.CHECKPOINT_PREFIX,
                            f'checkpoint_{count}{user_string}.tar.gz')

    def _make_metadata_path(self, user: auth_domain.User, count: int) -> str:
        user_string = f'_{user.username}' if user else ''
        return os.path.join(self.CHECKPOINT_PREFIX,
                            f'checkpoint_{count}{user_string}.json')

    def _get_checkpoint_count(self, user: auth_domain.User) -> int:
        count = 0
        while True:
            _path = self._make_path(user, count + 1)
            if not self.exists(_path, is_system=True):
                break
            count += 1
        return count

    def create_checkpoint(self, user: auth_domain.User) -> str:
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

        self.add_non_file_warning(
            "Creating checkpoint." + (f"['{user.user_id}']" if user else "")
        )

        # Create a new unique filename for checkpoint
        count = self._get_checkpoint_count(user)
        if count >= self.MAX_CHECKPOINTS:
            # TODO: Need to throw an error here?
            return ''

        checkpoint = self.create(self._make_path(user, count + 1),
                                 is_system=True, is_persisted=True, touch=True)
        self.pack_source(checkpoint)

        metadata = self.create(self._make_metadata_path(user, count + 1),
                               is_system=True, is_persisted=True, touch=True)
        with self.open(metadata, 'w') as f:
            dump(self.to_dict(), f, cls=ISO8601JSONEncoder)
        # Determine checksum for new checkpoint file
        return checkpoint.checksum

    def list_checkpoints(self, user: auth_domain.User) -> List[UploadedFile]:
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
        self.log.info(log_msg)
        return [u for u in self.iter_files(allow_system=True)
                if u.is_system
                and u.path.startswith(self.CHECKPOINT_PREFIX)
                and u.path.endswith('.tar.gz')]

    def delete_checkpoint(self, checksum: str, user: auth_domain.User) -> None:
        """Remove specified checkpoint."""
        try:
            checkpoint = self._resolve_checkpoint_file(checksum)
        except FileNotFoundError:
            log_msg = f"ERROR: Checkpoint not found: {checksum}"
            log_msg += f"['{user.username}']" if user else "."
            self.log.info(log_msg)
            raise

        self.delete(checkpoint)
        log_msg = f"Deleted checkpoint: {checkpoint.name}"
        log_msg += f"['{user.username}']." if user else "."
        self.log.info(log_msg)

    def delete_all_checkpoints(self, user: auth_domain.User) -> None:
        """Remove all checkpoints."""
        for checkpoint in self.list_checkpoints(user):
            self.delete(checkpoint)

        log_msg = f"Deleted ALL checkpoints"
        log_msg += f": ['{user.username}']." if user else "."
        self.log.info(log_msg)

    def _update_from_checkpoint(self, workspace: 'CheckpointWorkspace') \
            -> None:
        self.files.source = workspace.files.source
        self.files.ancillary = workspace.files.ancillary
        for u_file in self.iter_files():
            u_file.workspace = self
        self._errors = workspace.errors

    def restore_checkpoint(self, checksum: str,
                           user: auth_domain.User) -> None:
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
        self.delete_all_files()

        # Locate the checkpoint we are interested in.
        try:
            checkpoint = self._resolve_checkpoint_file(checksum)
        except FileNotFoundError:
            self.add_non_file_error('Unable to restore checkpoint. Not found.')
            raise
        if self.storage is None:
            raise RuntimeError('Storage not available')
        self.storage.unpack_tarfile(self, checkpoint, self.source_path)

        # Restore fileindex and errors from previous metadata.
        meta_path = os.path.join(checkpoint.path.replace('.tar.gz', '.json'))
        with self.open(self.get(meta_path, is_system=True)) as f_meta:
            self._update_from_checkpoint(
                self.from_dict(load(f_meta, cls=ISO8601JSONDecoder)))

        log_msg = f'Restored checkpoint: {checkpoint.name}'
        log_msg += f' [{user.username}].' if user else '.'
        self.log.info(log_msg)
