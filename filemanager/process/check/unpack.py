"""Unpack compressed files in the workspace."""

import os
import tarfile
import zipfile
from arxiv.base import logging

from ...domain import FileType, UploadedFile, UploadWorkspace
from .base import BaseChecker


logger = logging.getLogger(__name__)
logger.propagate = False


class UnpackCompressedTarFiles(BaseChecker):
    """Unpack any compressed Tar files in a workspace."""

    UNPACK_ERROR_MSG = ("There were problems unpacking '%s'. Please try again"
                        " and confirm your files.")

    def check_TAR(self, workspace: UploadWorkspace, u_file: UploadedFile) \
            -> UploadedFile:
        return self._unpack(workspace, u_file)

    def check_GZIPPED(self, workspace: UploadWorkspace, u_file: UploadedFile) \
            -> UploadedFile:
        return self._unpack(workspace, u_file)

    def check_BZIP2(self, workspace: UploadWorkspace, u_file: UploadedFile) \
            -> UploadedFile:
        return self._unpack(workspace, u_file)

    def _unpack_file(self, workspace: UploadWorkspace, u_file: UploadedFile,
                     tar: tarfile.TarFile, tarinfo: tarfile.TarInfo) -> None:
        # Extract files and directories for now
        dest = os.path.join(u_file.dir, tarinfo.name).lstrip('/')

        # Tarfiles may contain relative paths! We must ensure that each file is
        # not going to escape the upload source directory _before_ we extract
        # it.
        if not workspace.is_safe(dest):
            logger.error('Member of %s tried to escape workspace', u_file.path)
            workspace.log(f'Member of file {u_file.name} tried to escape'
                          ' workspace.')
            return u_file

        # Warn about entities we don't want to see in upload archives. We
        # did not check carefully in legacy system and hard links caused
        # bad things to happen.
        msg = '%s are not allowed. ' + f'Removing {tarinfo.name}'
        if tarinfo.issym():  # sym link
            workspace.add_warning(u_file, msg % 'Symbolic links')
        elif tarinfo.islnk():  # hard link
            workspace.add_warning(u_file, msg % 'Hard links')
        elif tarinfo.ischr():
            workspace.add_warning(u_file, msg % 'Character devices')
        elif tarinfo.isblk():
            workspace.add_warning(u_file, msg % 'Block devices')
        elif tarinfo.isfifo():
            workspace.add_warning(u_file, msg % 'FIFO devices')
        elif tarinfo.isdev():
            workspace.add_warning(u_file, msg % 'Character devices')

        # Extract a regular file or directory.
        elif tarinfo.isreg() or tarinfo.isdir():
            parent = workspace.get_full_path(u_file.dir,
                                             is_ancillary=u_file.is_ancillary)
            tar.extract(tarinfo, parent)
            logger.debug('Unpacked to %s', parent)

            os.utime(parent)  # Update access and modified times to now.
            if tarinfo.isdir():
                if not dest.endswith('/'):
                    dest += '/'
                workspace.create(dest, touch=False, is_directory=True,
                                 is_ancillary=u_file.is_ancillary,
                                 file_type=FileType.DIRECTORY)
            else:
                workspace.create(dest, touch=False,
                                 is_ancillary=u_file.is_ancillary)

    def _unpack(self, workspace: UploadWorkspace, u_file: UploadedFile) \
            -> UploadedFile:
        if not workspace.is_tarfile(u_file):
            workspace.add_error(u_file, f'Unable to read tar {u_file.name}')
            return u_file

        workspace.log(f"***** unpack {u_file.file_type.value} {u_file.path}"
                      f" to dir: {os.path.split(u_file.path)[0]}")

        try:
            with workspace.open(u_file, 'rb') as f:
                with tarfile.open(fileobj=f) as tar:
                    for tarinfo in tar:
                        self._unpack_file(workspace, u_file, tar, tarinfo)

        except tarfile.TarError as e:
            # Do something better with as error
            workspace.add_warning(u_file, self.UNPACK_ERROR_MSG % u_file.name)
            workspace.add_warning(u_file, f'Tar error message: {e}')
            return u_file

        workspace.remove(u_file, f"Removed packed file '{u_file.name}'.",
                         keep_refs=False)
        workspace.log(f'Removed packed file {u_file.name}')
        return u_file


class UnpackCompressedZIPFiles(BaseChecker):

    UNPACK_ERROR_MSG = ("There were problems unpacking '%s'. Please try again"
                        " and confirm your files.")

    def check_ZIP(self, workspace: UploadWorkspace, u_file: UploadedFile) \
            -> UploadedFile:
        logger.debug("*******Process zip archive: %s", u_file.path)

        workspace.log(f'***** unpack {u_file.file_type} {u_file.name}'
                      f' to dir: {os.path.split(u_file.path)[0]}')
        try:
            with workspace.open(u_file, 'rb') as f:
                with zipfile.ZipFile(f) as zip:
                    for zipinfo in zip.infolist():
                        self._unpack_file(workspace, u_file, zip, zipinfo)
        except zipfile.BadZipFile as e:
            # TODO: Think about warnings a bit. Tar/zip problems currently
            # reported as warnings. Upload warnings allow submitter to continue
            # on to process/compile step.
            workspace.add_warning(u_file, self.UNPACK_ERROR_MSG % u_file.name)
            workspace.add_warning(u_file, f'Zip error message: {e}')
            return u_file

        # Now move zip file out of way to removed directory
        workspace.remove(u_file, f"Removed packed file '{u_file.name}'.",
                         keep_refs=False)
        workspace.log(f'Removed packed file {u_file.name}')
        return u_file

    def _unpack_file(self, workspace: UploadWorkspace, u_file: UploadedFile,
                     zip: zipfile.ZipFile, zipinfo: zipfile.ZipInfo) -> None:
        dest = os.path.join(u_file.dir, zipinfo.filename).lstrip('/')
        # Zip files may contain relative paths! We must ensure that each file
        # is not going to escape the upload source directory _before_ we
        # extract it.
        if not workspace.is_safe(dest):
            logger.error('Member of %s tried to escape workspace', u_file.path)
            workspace.log(f'Member of file {u_file.name} tried'
                          ' to escape workspace.')
            return

        full_path = workspace.get_full_path(u_file.dir)
        zip.extract(zipinfo, full_path)
        os.utime(full_path)  # Update access and modified times to now.
        workspace.create(dest, touch=False)


# TODO: Add support for compressed files.
class UnpackCompressedZFiles(BaseChecker):
    """Unpack compressed .Z files."""

    def check_COMPRESSED(self, workspace: UploadWorkspace,
                         u_file: UploadedFile) -> UploadedFile:
        logger.debug("We can't uncompress .Z files yet: %s", u_file.path)
        workspace.log('Unable to uncompress .Z file. Not implemented yet.')
        return u_file
