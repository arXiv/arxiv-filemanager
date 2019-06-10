"""Unpack compressed files in the workspace."""

import os
import tarfile
from arxiv.base import logging

from ...domain import FileType, UploadedFile, UploadWorkspace
from .base import BaseChecker


logger = logging.getLogger(__name__)


class UnpackCompressedTarFiles(BaseChecker):
    """Unpack any compressed Tar files in a workspace."""

    UNPACK_ERROR_MSG = ("There were problems unpacking '%s'. Please try again"
                        " and confirm your files.")

    def check_TAR(self, workspace: UploadWorkspace,
                  u_file: UploadedFile) -> None:
        self._unpack(workspace, u_file)

    def check_GZIPPED(self, workspace: UploadWorkspace,
                      u_file: UploadedFile) -> None:
        self._unpack(workspace, u_file)

    def check_BZIP2(self, workspace: UploadWorkspace,
                    u_file: UploadedFile) -> None:
        self._unpack(workspace, u_file)

    def _unpack_file(workspace: UploadWorkspace, u_file: UploadedFile,
                     target_dir: str, tar: tarfile.TarFile,
                     tarinfo: tarfile.TarInfo) -> None:
        # Extract files and directories for now
        dest = os.path.join(target_dir, tarinfo.name)
        # Tarfiles may contain relative paths! We must ensure that each file is
        # not going to escape the upload source directory _before_ we extract
        # it.
        if target_dir not in os.path.normpath(dest):
            upload.add_log_entry(f'Member of file {u_file.name} tried'
                                 ' to escape workspace.')
            return

        if tarinfo.isreg() or tarinfo.isdir():
            tar.extract(tarinfo, target_dir)    # log this? ("Reg File")
            os.utime(dest)  # Update access and modified times to now.
        else:
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

    def _unpack(self, workspace: UploadWorkspace,
                u_file: UploadedFile) -> None:
        if not tarfile.is_tarfile(workspace.get_full_path(u_file)):
            workspace.add_error(u_file, f'Unable to read tar {u_file.name}')
            return

        parent_dir, _ = os.path.split(u_file.path)
        target_dir = os.path.join(workspace.source_path, parent_dir)
        workspace.add_log_entry(f"***** unpack {u_file.file_type.value}"
                                f" {u_file.path} to dir: {target_dir}")

        try:
            with tarfile.open(u_file.path) as tar:
                for tarinfo in tar:
                    self._unpack_file(workspace, u_file, target_dir,
                                      tar, tarinfo)

        except tarfile.TarError as e:
            # Do something better with as error
            workspace.add_warning(u_file, self.UNPACK_ERROR_MSG % u_file.name)
            workspace.add_warning(u_file, f'Tar error message: {e}')
            return

        workspace.remove(u_file, f"Removed packed file '{u_file.name}'.")
        workspace.add_log_entry(f'Removed packed file {u_file.name}')


class UnpackCompressedZIPFiles(BaseChecker):

    UNPACK_ERROR_MSG = ("There were problems unpacking '%s'. Please try again"
                        " and confirm your files.")

    def check_ZIP(self, workspace: UploadWorkspace,
                  u_file: UploadedFile) -> None:
        parent_dir, _ = os.path.split(u_file.path)
        target_dir = os.path.join(workspace.source_path, parent_dir)
        logger.debug("*******Process zip archive: %s", u_file.path)

        workspace.add_log_entry(f'***** unpack {u_file.file_type}'
                                f' {u_file.name} to dir: {target_dir}')
        try:
            with zipfile.ZipFile(path, "r") as zip:
                for zipinfo in zip.infolist():
                    self._unpack_file(workspace, u_file, target_dir,
                                      zip, zipinfo)
        except zipfile.BadZipFile as e:
            # TODO: Think about warnings a bit. Tar/zip problems currently
            # reported as warnings. Upload warnings allow submitter to continue
            # on to process/compile step.
            workspace.add_warning(u_file, self.UNPACK_ERROR_MSG % u_file.name)
            workspace.add_warning(u_file, f'Zip error message: {e}')
            return

        # Now move zip file out of way to removed directory
        workspace.remove(u_file, f"Removed packed file '{u_file.name}'.")
        workspace.add_log_entry(f'Removed packed file {u_file.name}')

    def _unpack_file(workspace: UploadWorkspace, u_file: UploadedFile,
                     target_dir: str, zip: zipfile.ZipFile,
                     zipinfo: zipfile.ZipInfo) -> None:
        dest = os.path.join(target_dir, tarinfo.name)
        # Zip files may contain relative paths! We must ensure that each file
        # is not going to escape the upload source directory _before_ we
        # extract it.
        if target_dir not in os.path.normpath(dest):
            upload.add_log_entry(f'Member of file {u_file.name} tried'
                                 ' to escape workspace.')
            return
        zip.extract(zipinfo, target_dir)



# TODO: Add support for compressed files.
class UnpackCompressedZFiles(BaseChecker):
    """Unpack compressed .Z files."""

    def check_COMPRESSED(self, workspace: UploadWorkspace,
                         u_file: UploadedFile) -> None:
        logger.debug("We can't uncompress .Z files yet.")
        workspace.add_log_entry(f'***** unpack {u_file.file_type}'
                                f' {u_file.name} to dir: {target_dir}')
        workspace.add_log_entry('Unable to uncompress .Z file. Not implemented'
                                ' yet.')
