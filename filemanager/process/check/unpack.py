"""Unpack compressed files in the workspace."""

import os
import tarfile
import zipfile
from arxiv.base import logging

from ...domain import FileType, UserFile, Workspace, Code
from .base import BaseChecker


logger = logging.getLogger(__name__)
logger.propagate = False


UNPACK_ERROR: Code = "unpack_error"
UNPACK_ERROR_MESSAGE = ("There were problems unpacking '%s'. Please try "
                        "again and confirm your files. Error: %s")

DISALLOWED_FILES: Code = "contains_disallowed_files"
DISALLOWED_MESSAGE = "%s are not allowed. Removing '%s'"


class UnpackCompressedTarFiles(BaseChecker):
    """Unpack any compressed Tar files in a workspace."""

    UNREADABLE_TAR: Code = "tar_file_unreadable"
    UNREADABLE_TAR_MESSAGE = "Unable to read tar '%s': %s"


    def check_TAR(self, workspace: Workspace, u_file: UserFile) \
            -> UserFile:
        """Unpack a Tar file."""
        return self._unpack(workspace, u_file)

    def check_GZIPPED(self, workspace: Workspace, u_file: UserFile) \
            -> UserFile:
        """Unpack a gzipped tar file."""
        return self._unpack(workspace, u_file)

    def check_BZIP2(self, workspace: Workspace, u_file: UserFile) \
            -> UserFile:
        """Unpack a bzip2 file."""
        return self._unpack(workspace, u_file)

    def _warn_disallowed(self, workspace: Workspace, u_file: UserFile,
                         file_type: str, tarinfo: tarfile.TarInfo) -> None:
        workspace.add_warning(u_file, DISALLOWED_FILES,
                              DISALLOWED_MESSAGE % (file_type, tarinfo.name),
                              is_persistant=False)

    def _unpack_file(self, workspace: Workspace, u_file: UserFile,
                     tar: tarfile.TarFile, tarinfo: tarfile.TarInfo) \
            -> UserFile:
        # Extract files and directories for now
        fname = tarinfo.name
        if fname.startswith('./'):
            fname = fname[2:]
        dest = os.path.join(u_file.dir, fname).lstrip('/')

        # Tarfiles may contain relative paths! We must ensure that each file is
        # not going to escape the upload source directory _before_ we extract
        # it.
        if not workspace.is_safe(dest, is_ancillary=u_file.is_ancillary,
                                 is_persisted=u_file.is_persisted):
            logger.error('Member of %s tried to escape workspace', u_file.path)
            workspace.log.info(f'Member of file {u_file.name} tried to escape'
                               ' workspace.')
            return u_file

        # Warn about entities we don't want to see in upload archives. We
        # did not check carefully in legacy system and hard links caused
        # bad things to happen.
        if tarinfo.issym():
            self._warn_disallowed(workspace, u_file, 'Symbolic links', tarinfo)
        elif tarinfo.islnk():
            self._warn_disallowed(workspace, u_file, 'Hard links', tarinfo)
        elif tarinfo.ischr():
            self._warn_disallowed(workspace, u_file, 'Character devices',
                                  tarinfo)
        elif tarinfo.isblk():
            self._warn_disallowed(workspace, u_file, 'Block devices', tarinfo)
        elif tarinfo.isfifo():
            self._warn_disallowed(workspace, u_file, 'FIFO devices', tarinfo)
        elif tarinfo.isdev():
            self._warn_disallowed(workspace, u_file, 'Character devices',
                                  tarinfo)

        # Extract a regular file or directory.
        elif tarinfo.isreg() or tarinfo.isdir():
            parent = workspace.get_full_path(u_file.dir,
                                             is_ancillary=u_file.is_ancillary)
            tar.extract(tarinfo, parent)
            os.utime(parent)  # Update access and modified times to now.
            # If the parent is not explicitly an ancillary file, leave it up
            # to the workspace to infer whether or not the new file is
            # ancillary or not.
            is_ancillary = True if u_file.is_ancillary else None
            if tarinfo.isdir():
                if not dest.endswith('/'):
                    dest += '/'
                workspace.create(dest, touch=False, is_directory=True,
                                 is_ancillary=is_ancillary,
                                 file_type=FileType.DIRECTORY)
            else:
                workspace.create(dest, touch=False,
                                 is_ancillary=is_ancillary)
        return u_file

    def _unpack(self, workspace: Workspace, u_file: UserFile) -> UserFile:
        if not workspace.is_tarfile(u_file):
            workspace.add_error(u_file, self.UNREADABLE_TAR,
                                self.UNREADABLE_TAR_MESSAGE %
                                (u_file.name, 'not a tar file'))
            return u_file

        workspace.log.info(
            f"***** unpack {u_file.file_type.value.lower()} {u_file.path}"
            f" to dir: {os.path.split(u_file.path)[0]}"
        )

        try:
            with workspace.open(u_file, 'rb') as f:
                with tarfile.open(fileobj=f) as tar:
                    for tarinfo in tar:
                        self._unpack_file(workspace, u_file, tar, tarinfo)

        except tarfile.TarError as e:
            # Do something better with as error
            workspace.add_warning(u_file, UNPACK_ERROR,
                                  UNPACK_ERROR_MESSAGE % (u_file.name, e))
            return u_file

        workspace.remove(u_file, f"Removed packed file '{u_file.name}'.")
        workspace.log.info(f'Removed packed file {u_file.name}')
        return u_file


class UnpackCompressedZIPFiles(BaseChecker):
    """Unpack compressed ZIP files."""

    UNPACK_ERROR_MSG = ("There were problems unpacking '%s'. Please try again"
                        " and confirm your files.")

    def check_ZIP(self, workspace: Workspace, u_file: UserFile) \
            -> UserFile:
        """Perform the ZIP extraction."""
        logger.debug("*******Process zip archive: %s", u_file.path)

        workspace.log.info(
            f'***** unpack {u_file.file_type.value.lower()} {u_file.name}'
            f' to dir: {os.path.split(u_file.path)[0]}'
        )
        try:
            with workspace.open(u_file, 'rb') as f:
                with zipfile.ZipFile(f) as zip:
                    for zipinfo in zip.infolist():
                        self._unpack_file(workspace, u_file, zip, zipinfo)
        except zipfile.BadZipFile as e:
            # TODO: Think about warnings a bit. Tar/zip problems currently
            # reported as warnings. Upload warnings allow submitter to continue
            # on to process/compile step.
            workspace.add_warning(u_file, UNPACK_ERROR,
                                  UNPACK_ERROR_MESSAGE % (u_file.name, e))
            return u_file

        # Now move zip file out of way to removed directory
        workspace.remove(u_file, f"Removed packed file '{u_file.name}'.")
        workspace.log.info(f'Removed packed file {u_file.name}')
        return u_file

    def _unpack_file(self, workspace: Workspace, u_file: UserFile,
                     zip: zipfile.ZipFile, zipinfo: zipfile.ZipInfo) -> None:
        fname = zipinfo.filename
        if fname.startswith('./'):
            fname = fname[2:]
        dest = os.path.join(u_file.dir, fname).lstrip('/')

        # Zip files may contain relative paths! We must ensure that each file
        # is not going to escape the upload source directory _before_ we
        # extract it.
        if not workspace.is_safe(dest):
            logger.error('Member of %s tried to escape workspace', u_file.path)
            workspace.log.info(f'Member of file {u_file.name} tried'
                               ' to escape workspace.')
            return

        # If the parent is not explicitly an ancillary file, leave it up
        # to the workspace to infer whether or not the new file is
        # ancillary or not.
        is_ancillary = True if u_file.is_ancillary else None

        full_path = workspace.get_full_path(u_file.dir)
        zip.extract(zipinfo, full_path)
        os.utime(full_path)  # Update access and modified times to now.
        workspace.create(dest, touch=False, is_ancillary=is_ancillary)


# TODO: Add support for compressed files.
class UnpackCompressedZFiles(BaseChecker):
    """Unpack compressed .Z files."""

    def check_COMPRESSED(self, workspace: Workspace,
                         u_file: UserFile) -> UserFile:
        """Uncompress the .Z file (not implemented)."""
        logger.debug("We can't uncompress .Z files yet: %s", u_file.path)
        workspace.log.info('Unable to uncompress .Z file. Not implemented.')
        return u_file
