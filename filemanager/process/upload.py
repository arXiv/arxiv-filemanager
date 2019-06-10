"""Provides functions that sanitizes :class:`.Upload."""

import time
import os
import re
from datetime import datetime

import shutil
import tempfile
import tarfile
import logging
from hashlib import md5
from base64 import urlsafe_b64encode
import io
import mmap
import filecmp
from typing import Optional, Union
import struct

from pytz import UTC


from werkzeug.exceptions import BadRequest, NotFound, SecurityError
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from arxiv.base.globals import get_application_config
from arxiv.base import logging as base_logging

from filemanager.arxiv.file import File as File
from filemanager.utilities.unpack import unpack_archive


UPLOAD_FILE_EMPTY = 'file payload is zero length'
UPLOAD_DELETE_FILE_FAILED = 'unable to delete file'
UPLOAD_DELETE_ALL_FILE_FAILED = 'unable to delete all file'
UPLOAD_FILE_NOT_FOUND = 'file not found'
UPLOAD_WORKSPACE_NOT_FOUND = 'workspcae not found'

# File types unmacify is interested in
PC = 'pc'
MAC = 'mac'

# Types of embedded content
PHOTOSHOP = 'Photoshop'
PREVIEW = 'Preview'
THUMBNAIL = 'Thumbnail'


logger = base_logging.getLogger(__name__)
logger.propagate = False


def _get_base_directory() -> str:
    config = get_application_config()
    return config.get('UPLOAD_BASE_DIRECTORY',
                      '/tmp/filemanagment/submissions')


def is_available() -> bool:
    """Quick check to verify read/write on the filesystem."""
    try:
        with tempfile.TemporaryFile(dir=_get_base_directory()) as f:
            f.write(b'ruok')
            f.seek(0)
            assert f.read() == b'ruok'
    except Exception as e:
        logger.error('Could not read or write filesystem: %s', e)
        return False
    return True


# TODO: we will want to look at where this class is behaving statefully, and
# consider whether + how we can make it less stateful. For example, the method
# has_files() will return different values depending on whether the Upload
# instance has processed files, regardless of whether there are files on disk
# or not.
class Upload:
    """
    Programatic interface to fileystem-based upload workspace.

    Manage uploaded files: extract files from gzipped tar archive, perform a
    wide variety of checks on files and generate a list of warning/errors,
    install files in the correct location, generate content archive for clients
    to download.

    """

    SOURCE_PREFIX = 'src'
    """The name of the source directory within the upload workspace."""

    REMOVED_PREFIX = 'removed'
    """The name of the removed directory within the upload workspace."""

    ANCILLARY_PREFIX = 'anc'
    """The directory within source directory where ancillary files are kept."""

    # # Unnecessary .bib file warning message.
    # bib_with_bbl_warning = (
    #     "We do not run bibtex in the auto - TeXing "
    #     "procedure. We do not run bibtex because the .bib database "
    #     "files can be quite large, and the only thing necessary "
    #     "to make the references for a given paper is the.bbl file."
    # )

    # Missing .bbl file explanation message.


    # # DOC (MS Word) format not accepted warning message.
    # doc_warning = (
    #     "Your submission has been rejected because it contains "
    #     "one or more files with extension .doc, assumed to be "
    #     "MSWord files. Sadly, MSWord is not an acceptable "
    #     "submission format: see <a href=\"/help/submit\">"
    #     "submission help</a> for details of accepted formats. "
    #     "If your document was created using MSWord then it is "
    #     "probably best to submit as PDF (MSWord can produce "
    #     "marginal and/or non-compliant PostScript). If your "
    #     "submission includes files with extension .doc which "
    #     "are not MSWord documents, please rename to a different"
    #     " extension and resubmit."
    # )

    # Revtex warning message.
    # revtex_warning = (
    #     "WILL REMOVE standard revtex4 style files from this "
    #     "submission. revtex4 is now fully supported by arXiv "
    #     "and all its mirrors, for details see the "
    #     "<a href=\"/help/faq/revtex\">RevTeX FAQ</a>. If you "
    #     "have modified these files in any way then you must "
    #     "rename them before attempting to include them with your submission."
    # )

    # Diagrams warning message.
    # diagrams_warning = (
    #     "REMOVING standard style files for Paul Taylor's "
    #     "diagrams package. This package is supported in arXiv's TeX "
    #     "tree and the style files are thus unnecessary. Furthermore, they "
    #     "include 'time-bomb' code which will render submissions that include "
    #     "them unprocessable at some time in the future."
    # )

    # """Missing fonts warning message."""
    # missfont_warning = (
    #     "Removed file 'missfont.log'. Detected 'missfont.log' file in uploaded"
    #     " files. This may indicate a problem with the fonts your submission"
    #     " uses. Please correct any issues with fonts and be sure to examine "
    #     "the fonts in the final preview PDF that our system generates."
    # )


    def __init__(self, upload_id: int):
        """
        Initialize Upload object.

        Parameters
        ----------
        upload_id : int
            Unique identifier for submission workspace.

        """
        self.__upload_id = upload_id

        self.__warnings = []
        self.__errors = []
        self.__files = []
        self.__debug = False

        # total client upload workspace source directory size (in bytes)
        self.__total_upload_size = 0

        self.__log = ''
        self.create_upload_workspace()
        self.create_upload_log()
        # Calculate size just in case client is making request that does
        # not upload or delete files. Those requests update total size.
        self.calculate_client_upload_size()

    # Debug
    def set_debug(self, set: bool) -> None:
        """
        Activate/deactivate debugging.

        Set debug to True to enable debugging.

        Parameters
        ----------
        set : bool
            Set debug to value of 'set' parameter. True turns on
            debugging and False turns it off.

        """
        self.__debug = set

    def debug(self) -> bool:
        """Return value of debug setting. True = on."""
        return self.__debug


    # Files

    def has_files(self) -> bool:
        """Indicates whether files list contains entries."""
        if self.__files:
            return True

        return False

    def has_files_on_disk(self) -> bool:
        """
        Indicates whether there are any files in the workspace on disk.

        This will return True regardless of whether we have processed the files
        in any way.
        """
        for _, _, files in os.walk(self.source_path):
            for _ in files:
                return True
        return False

    # TODO: Need to add test for these last minute additions
    #       get_files, add_files, get_errors, get_warnings.

    def get_files(self) -> list:
        """Return list of files contained in upload."""
        return self.__files

    def add_file(self, file: File) -> None:
        """Add a file to list."""
        self.__files.append(file)

    def clear_file_list(self) -> None:
        """Clear file list."""
        self.__files = []

    def remove_from_list(self, file: File) -> None:
        """Remove file from list."""
        if file in self.__files:
            self.__files.remove(file)

    # Warnings

    def add_warning(self, public_filepath: str, msg: str) -> None:
        """
        Record warning. Adds warning message to list of warning messages.

        Parameters
        ----------
        public_filepath : str
            Optional public filepath intended to be displayed to end user.

        msg : str
            User-friendly warning message. Intended to support corrective action.

        Returns
        -------
        None
        """
        #  TODO: This breaks tests. Don't reformat message for now. Wait until
        #  next sprint.
        self.__log.warning(msg)

        # Add to internal list to make it easier to manipulate
        entry = [public_filepath, msg]
        # self.__warnings.append(msg)
        self.__warnings.append(entry)

    def has_warnings(self) -> int:
        """Indicates whether upload has warnings."""
        return len(self.__warnings)

    def search_warnings(self, search: str) -> bool:
        """
        Search list of warnings for specific warning.

        Useful for verifying tests produced correct warning.

        Parameters
        ----------
        search : str
            String or regex argument will be used to search warnings for
            specific warning.

        Returns
        -------
        bool
            True if warning we are searching for exists. False otherwise.
        """
        for entry in self.__warnings:
            #filename, warning = entry
            _, warning = entry
            if re.search(search, warning):
                return True

        return False

    def get_warnings(self) -> list:
        """Get list of upload warnings."""
        return self.__warnings

    # Errors

    def add_error(self, public_filepath: str, msg: str) -> None:
        """Record error for this upload instance."""
        entry = [public_filepath, msg]
        self.__errors.append(entry)

    def has_errors(self) -> int:
        """Indicates whether upload has errors."""
        return len(self.__errors)

    def search_errors(self, search: str) -> bool:
        """
        Search list of errors for specific error.

        Useful for verifying tests produced correct error.

        Parameters
        ----------
        search : str
            String or regex argument will be used to search errors for
            specific error.

        Returns
        -------
        bool
            True if error we are searching for exists. False otherwise.
        """
        for entry in self.__errors:
            #filename, error = entry
            _, error = entry
            if re.search(search, error):
                return True

        return False

    def clear_warnings_and_errors(self) -> None:
        """
        Clear out warnings, errors, and files.

        Initialize lists that keep track of warnings, errors, and files.

        """
        self.__warnings = []
        self.__errors = []
        self.__files = []

    def get_errors(self) -> list:
        """Get list of upload errors."""
        return self.__errors

    @property
    def upload_id(self) -> int:
        """Return upload identifier.

        The unique identifier for upload.

        """
        return self.__upload_id

    def remove(self, file: File, msg: str) -> None:
        """
        Remove file from source directory.

        Moves specified file to 'removed' directory and marks :class:`File`
        objects state as removed."

        Parameters
        ----------
        file : :class:`File`
            File to be removed from source directory.
        msg
            Message indicating reason for removal.

        Returns
        -------
        None

        """
        # Move file to removed directory
        filepath = file.filepath
        removed_path = os.path.join(self.removed_path, file.name)
        # self.__log.debug("Moving file " + file.name + " to removed dir: " + removed_path)

        if shutil.move(filepath, removed_path):
            # lmsg = "*** File " + file.name + f" has been removed. Reason: {msg} ***"
            if msg:
                lmsg = msg
            else:
                lmsg = f"Removed file '{file.name}'."
            self.add_warning(file.public_filepath, lmsg)

            # Remove file from file list (just in case called from somewhere other than process)
            self.remove_from_list(file)
        else:
            self.add_warning(file.public_filepath,
                             f"*** FAILED to remove file '{filepath}' ***")

        # Add reason for removal to File object
        file.remove(msg)

        # We won't recalculate size here because we know total size will be
        # recalculated after all file checks (uses this routine) are complete.

    def remove_workspace(self) -> bool:
        """Remove upload workspace.

        This request completely removes the upload
        workspace directory. No backup is made here (system backups may have files
        for period of time).

        Returns
        -------
        True if source log was saved and workspace deleted.
        """
        self.log('********** Delete Workspace ************\n')

        # Think about stashing source.log, otherwise any logging is fruitless
        # since we are deleting all files under workspace.

        workspace_directory = self.get_upload_directory()

        # Let's stash a copy of the source.log file (if it exists)
        log_path = os.path.join(self.get_upload_directory(), 'source.log')

        if os.path.exists(log_path):
            # Does directory exist to stash log
            deleted_workspace_logs = os.path.join(_get_base_directory(),
                                                  'deleted_workspace_logs')
            if not os.path.exists(deleted_workspace_logs):
                # Create the directory for deleted workspace logs
                os.makedirs(deleted_workspace_logs, 0o755)

            # Since every source log has the same filename we will prefix
            # upload identifier to log.
            if isinstance(self.__upload_id, int):
                # Format integer as legacy submission id
                padded_id = '{0:07d}'.format(self.__upload_id)
            else:
                # Use string id as-is
                padded_id = self.__upload_id

            new_filename = padded_id + "_source.log"
            deleted_log_path = os.path.join(deleted_workspace_logs, new_filename)
            self.log(f"Move '{log_path} to '{deleted_log_path}'.")
            self.log(f"Delete workspace '{workspace_directory}'.")
            if not shutil.move(log_path, deleted_log_path):
                self.log('Saving source.log failed.')
                return False

        # Now blow away the workspace
        if os.path.exists(workspace_directory):
            shutil.rmtree(workspace_directory)

        return True

    def resolve_public_file_path(self, public_file_path: str) -> File:
        """
        Resolve a relative file path to a arXiv File object.

        Note: We are being very cautious here and spending most of this routine
        checking for deviant relevant file paths.

        Returns
        -------
        Null if file does not exist.
        Otherwise returns fully qualified path to content file.

        """
        # Sanitize file name
        filename = secure_filename(public_file_path)

        # Our UI will never attempt to delete a file path containing components that attempt
        # to escape out of workspace and this would be removed by secure_filename().
        # This error must be propagated to wider notification level beyond source log.
        if re.search(r'^/|^\.\./|\.\./', public_file_path):
            # should never start with '/' or '../' or contain '..' anywhere in path.
            message = f"SECURITY WARNING: file to delete contains illegal " \
                      f"constructs: '{public_file_path}'"
            self.log(message)
            raise SecurityError(message)

        # Secure filename should not change length of valid file path (but it will
        # mess with directory slashes '/')
        # TODO: Come up with better file path checker. We allow subdirectories
        # TODO: and secure_filename strips them (/ => _)
        # The length of file path should not change (need to check secure_filename)
        # so if length changes generate warning.
        if len(public_file_path) != len(filename):
            message = f"SECURITY WARNING: sanitized file is different " \
                      f"length: '{filename}' <=> '{public_file_path}'"
            self.log(message)
            raise SecurityError(message)

        # Resolve relative path of file to filesystem
        source_directory = self.source_path
        file_path = os.path.join(source_directory, filename)

        # secure_filename will eliminate '/' making paths to subdirectories
        # impossible to resolve. Make assumption we caught bad actors with checks above.

        # Check if original path might be subdirectory.
        # We've made it past serious threat checks above.
        if not os.path.exists(file_path) and re.search(r'_', filename) \
                and re.search(r'/', public_file_path):
            if len(filename) == len(public_file_path):
                # May be issue of directory delimiter converted to '_'
                # Check if raw path exists
                check_path = os.path.join(source_directory, public_file_path)
                if os.path.exists(check_path):
                    self.log(f"Path appears to be valid and contain "
                             + f"subdirectory: '{public_file_path}' <=> '{filename}'")
                    # TODO: Can someone hurt us here? Is it now safe to use original
                    # TODO: path or should I edit 'secure' path. I believe what I'm doing is ok.
                    file_path = check_path
                    filename = public_file_path

        # We have a file path that exists
        if os.path.exists(file_path):
            # Build arguments for File object
            file_obj = File(file_path, source_directory)
            return file_obj

        return None

    def client_remove(self, public_file_path: str) -> bool:
        """Delete a single file.

        For a single file deletion we will move file to special 'removed'
        directory.

        Parameters
        ----------
        public_file_path: str
            Relative path of file to be deleted.

        Returns
        -------
        True on success.

        Notes
        -----
        We are logging messages to source log. Warnings are not passed
        back in response for non-upload requests so we skip issuing warnings/errors.

        """
        self.log('********** Delete File ************\n')
        self.remove_content_package()

        # Check whether client is trying to damage system with invalid path

        # TODO: Switch to use resolve relative file path to eliminate duplicate code

        # Sanitize file name
        filename = secure_filename(public_file_path)

        # Our UI will never attempt to delete a file path containing components that attempt
        # to escape out of workspace and this would be removed by secure_filename().
        # This error must be propagated to wider notification level beyond source log.
        if re.search(r'^/|^\.\./|\.\./', public_file_path):
            # should never start with '/' or '../' or contain '..' anywhere in path.
            message = f"SECURITY WARNING: file to delete contains illegal " \
                      f"constructs: '{public_file_path}'"
            self.log(message)
            raise SecurityError(message)

        # Secure filename should not change length of valid file path (but it will
        # mess with directory slashes '/')
        # TODO: Come up with better file path checker. We allow subdirectories
        # TODO: and secure_filename strips them (/ => _)
        # The length of file path should not change (need to check secure_filename)
        # so if length changes generate warning.
        if len(public_file_path) != len(filename):
            message = f"SECURITY WARNING: sanitized file is different " \
                      f"length: '{filename}' <=> '{public_file_path}'"
            self.log(message)
            raise SecurityError(message)

        # Resolve relative path of file to filesystem
        src_directory = self.source_path
        file_path = os.path.join(src_directory, filename)

        # secure_filename will eliminate '/' making paths to subdirectories
        # impossible to resolve. Make assumption we caught bad actors with checks above.

        # Check if original path might be subdirectory.
        # We've made it past serious threat checks above.
        if not os.path.exists(file_path) and re.search(r'_', filename) \
                and re.search(r'/', public_file_path):
            if len(filename) == len(public_file_path):
                # May be issue of directory delimiter converted to '_'
                # Check if raw path exists
                check_path = os.path.join(src_directory, public_file_path)
                if os.path.exists(check_path):
                    self.log(f"Path appears to be valid and contain "
                             + f"subdirectory: '{public_file_path}' <=> '{filename}'")
                    # TODO: Can someone hurt us here? Is it now safe to use original
                    # TODO: path or should I edit 'secure' path. I believe what I'm doing is ok.
                    file_path = check_path
                    filename = public_file_path

        # Need to determine whether file exists
        if os.path.exists(file_path):
            # Let's move it to 'removed' directory.

            # Flatten public path to eliminate directory structure
            clean_public_path = re.sub('/', '_', public_file_path)

            # Generate path in removed directory
            removed_path = os.path.join(self.removed_path, clean_public_path)
            self.log(f"Delete file: '{filename}'")

            if shutil.move(file_path, removed_path):
                self.log(f"Moved file from {file_path} to {removed_path}")
                # Recalculate total upload workspace source directory size
                self.calculate_client_upload_size()
                return True

            self.log(f"*** FAILED to remove file '{file_path}'/{clean_public_path} ***")
            return False

        self.log(f"File to delete not found: '{public_file_path}' '{filename}'")
        raise NotFound(UPLOAD_FILE_NOT_FOUND)

    def client_remove_all_files(self) -> None:
        """Delete all files uploaded by client from specified workspace.

        For client delete requests we assume they have copies of original files and
        therefore do NOT backup files.

        """
        self.log('********** Delete ALL Files ************\n')

        # Cycle through list of files under src directory and remove them.
        #
        # For now we will remove file by moving it to 'removed' directory
        src_directory = self.source_path
        self.log(f"Delete all files under directory '{src_directory}'")

        self.remove_content_package()

        for dir_entry in os.listdir(src_directory):
            file_path = os.path.join(src_directory, dir_entry)
            try:
                if os.path.isfile(file_path):
                    self.log(f"Delete file:'{dir_entry}'")
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    self.log(f"Delete directory:'{dir_entry}'")
                    shutil.rmtree(file_path)
            except Exception as rme:
                self.log(f"Error while removing all files: '{rme}'")
                raise

        # Recalculate total upload workspace source directory size
        self.calculate_client_upload_size()

    def get_upload_directory(self) -> str:
        """
        Get top level workspace directory.

        Returns
        -------
        str
            Top level directory path for upload workspace.
        """
        root_path = _get_base_directory()
        upload_directory = os.path.join(root_path, str(self.upload_id))
        return upload_directory

    def create_upload_directory(self) -> str:
        """Create the base directory for upload workarea."""
        root_path = _get_base_directory()

        if not os.path.exists(root_path):
            # Create path for submissions
            # TODO determine if we need to set owner/modes
            os.makedirs(_get_base_directory(), 0o755)
            # Stick this entry in service log?
            print("Created file management service workarea\n")

        upload_directory = self.get_upload_directory()

        if not os.path.exists(upload_directory):
            # Create path for submissions
            # TODO determine if we need to set owner/modes
            os.makedirs(upload_directory, 0o755)
            self.create_upload_log()
            self.log(f"Created upload workspace: {self.upload_id}")

        return upload_directory

    def get_source_path(self) -> str:
        """Return directory where source files get deposited."""
        return os.path.join(self.get_upload_directory(), self.SOURCE_PREFIX)

    def get_removed_path(self) -> str:
        """Get directory where source archive files get moved when unpacked."""
        return os.path.join(self.get_upload_directory(), self.REMOVED_PREFIX)

    def get_ancillary_path(self) -> str:
        """
        Get directory where ancillary files are stored.

        If the directory does not already exist, it will be created.
        """
        path = os.path.join(self.source_path, self.ANCILLARY_PREFIX)
        if not os.path.exists(path):
            os.mkdir(path)
        return path

    def create_upload_workspace(self) -> str:
        """Create directories for upload work area."""
        # Create main directory
        base_dir = self.create_upload_directory()

        # TODO what directories do we want to carry over from existing upload/submission system
        src_dir = self.source_path

        if not os.path.exists(src_dir):
            # Create path for submissions
            # TODO determine if we need to set owner/modes
            os.makedirs(src_dir, 0o755)
            # print("Created src workarea\n");

        removed_dir = self.removed_path

        if not os.path.exists(removed_dir):
            # Create path for submissions
            # TODO determine if we need to set owner/modes
            os.makedirs(removed_dir, 0o755)
            # print("Created removed workarea\n");

        return base_dir

    def get_upload_source_log_path(self) -> str:
        """Generate path for upload source log."""
        return os.path.join(self.get_upload_directory(), 'source.log')

    def create_upload_log(self) -> None:
        """Create a source log to record activity for this upload."""
        # Grab standard logger and customized it
        logger = logging.getLogger(__name__)
        # log_path = os.path.join(self.get_upload_directory(), 'source.log')
        log_path = self.get_upload_source_log_path()
        file_handler = logging.FileHandler(log_path)

        formatter = logging.Formatter('%(asctime)s %(message)s', '%d/%b/%Y:%H:%M:%S %z')
        file_handler.setFormatter(formatter)
        logger.handlers = []
        logger.addHandler(file_handler)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False

        self.__log = logger

    def log(self, message: str) -> None:
        """Write message to upload log."""
        self.__log.info(message)

    def deposit_upload(self, file: FileStorage, ancillary: bool = False) \
            -> str:
        """
        Deposit uploaded archive/file into workspace source directory.

        Parameters
        ----------
        file : :class:`FileStorage`
            Archive containing one or more files to be added to source files
            for this upload.
        ancillary : bool
            If ``True``, file will be deposited in the ancillary directory.

        Returns
        -------
        str
            Full path of archive file.

        """
        basename = os.path.basename(file.filename)

        # Sanitize file name before saving it
        filename = secure_filename(basename)
        self.log(f"Uploded file '{filename}'.")

        if basename != filename:
            self.log(f'Secured filename: {filename} (basename + )')

        if ancillary:  # Put the file in the ancillary directory.
            src_directory = self.ancillary_path
        else:  # Store uploaded file/archive in source directory
            src_directory = self.source_path

        upload_path = os.path.join(src_directory, filename)
        file.save(upload_path)
        if os.stat(upload_path).st_size == 0:
            # Might be a good to delete zero length file we just deposited
            # in upload workspace.
            os.remove(upload_path)
            raise BadRequest(UPLOAD_FILE_EMPTY)
        return upload_path

    # These messages take parameters

    # def bbl_missing_error(self, basename: str) -> str:
    #     """Missing .bbl file detailed warning message."""
    #     bbl_missing_error_msg = \
    #         (f"Your submission contained {basename}.bib file, "
    #          f"but no {basename}.bbl file (include {basename}.bbl, or "
    #          f"submit without {basename}.bib; and remember to "
    #          f"verify references)."
    #          )
    #     return bbl_missing_error_msg

    # def get_graphic_error_msg(self, format: str) -> str:
    #     """Unsupported graphic format error message."""
    #     graphic_error_msg = \
    #         (f"{format} is not a supported graphics format: most "
    #          "readers do not have the programs needed to view and print "
    #          ".$format figures. Please save your [% format %] "
    #          "figures instead as PostScript, PNG, JPEG, or GIF "
    #          "(PNG/JPEG/GIF files can be viewed and printed with "
    #          "any graphical web browser) -- for more information.")
    #     return graphic_error_msg

    # TODO: once we are happy with the overall behavior of this class, this
    # might be a good place to start refactoring/decomposing. It may make sense
    # to pull the "checks" out into their own standalone classes or functions
    # that can collaborate with the Upload workspace class.
    def check_files(self) -> None:
        """
        Unpack, evaluate, and sanitize uploaded files.

        This is the main loop that goes through the list of files and performs
        a long list of checks that depend on file type, extension, and sometimes file name.

        Returns
        -------
        None
        """
        self.log('\n******** Check Files *****\n\n')

        source_directory = self.source_path

        self.clear_file_list()

        # Since filenames may change during handling (e.g. rename files with
        # illegal characters), we do not want to add them to the workspace
        # (including their warnings and errors) until the final filename is
        # known. We need to do this in several places, hence a function for
        # convenience.
        def _add_file(fpath: str, warnings: list, errors: list) -> File:
            """Add a file to the :class:`Upload` workspace."""
            # Since the filename may have changed, we re-instantiate
            # the File to get the most accurate representation.
            obj = File(fpath, source_directory)

            # Add all files to upload file list as this will hold
            # information about handling of file (removed)
            self.add_file(obj)

            # Add warnings and errors collected above, using the most
            # up-to-date filename.
            for msg in warnings:
                self.add_warning(obj.public_filepath, msg)
            for msg in errors:
                self.add_error(obj.public_filepath, msg)
            return obj

        for root_directory, directories, files in os.walk(source_directory):
            for directory in directories:
                # Need to decide whether we need to do anything to directories
                # in the meantime get rid of lint warning
                path = os.path.join(root_directory, directory)
                obj = File(path, source_directory)
                # self.log(f'{directory} [{obj.type}] in {obj.filepath}')

            for file in files:
                # Hold these until we're done with the file, since file names
                # can change here.
                _warnings = []
                _errors = []

                file_path = os.path.join(root_directory, file)
                obj = File(file_path, source_directory)

                # Convert this to debugging
                # print("  File is : " + file + " Size: " + str(
                #    obj.size) + " File is type: " + obj.type + ":" + obj.type_string + '\n')

                file_type = obj.type
                file_name = obj.name
                file_size = obj.size

                # Update file timestamps

                # Remove zero length files
                # if obj.size == 0:
                #     msg = f"File '{obj.name}' is empty (size is zero)."
                #     self.add_warning(obj.public_filepath, msg)
                #     self.remove(obj, f"Removed file '{obj.name}' [file is empty].")
                #     continue

                # Remove 10240 byte all-null files (bad user tar attempts?)
                # Check of file is 10240 bytes and all are zero

                # Rename Windows file names
                # if re.search(r'^[A-Za-z]:\\', file_name):
                #     # Rename using basename
                #     new_name = re.sub(r'^[A-Za-z]:\\(.*\\)?', '', file_name)
                #     new_file_path = os.path.join(root_directory, new_name)
                #     msg = 'Renaming ' + file_name + ' to ' + new_name + '.'
                #     _warnings.append(msg)
                #     os.rename(file_path, new_file_path)
                #     # fix up local data
                #     file_name = new_name
                #     file_path = new_file_path

                # Keep an eye out for special ancillary 'anc' directory
                # anc_dir = os.path.join(self.source_path,
                #                        self.ANCILLARY_PREFIX)
                # if file_path.startswith(anc_dir):
                #     statinfo = os.stat(file_path)
                #     kilos = statinfo.st_size
                #     warn = "Ancillary file " + file_name + " (" + str(kilos) + ')'
                #     ##self.add_warning(warn)
                #     obj.type = 'ancillary'
                #     # We are done at this point - we do not inspect ancillary files
                #     ##continue

                # Basic file checks

                # We need to check this before tilde character gets translated to undderscore.
                # Otherwise this warning never gets generated properly for .tex~
                # if re.search(, file_name, re.IGNORECASE):
                #     msg = f"File '{file_name}' may be a backup file. Please "\
                #           "inspect and remove extraneous backup files."
                #     _warnings.append(msg)

                # Attempt to rename filenames containing illegal characters

                # # Filename contains illegal characters+,-,/,=,
                # if re.search(r'[^\w\+\-\.\=\,]', file_name):
                #     # Translate bad characters
                #     new_file_name = re.sub(r'[^\w\+\-\.\=\,]', '_', file_name)
                #     _warnings.append(
                #         "We only accept file names containing the characters: "
                #         "a-z A-Z 0-9 _ + - . , ="
                #     )
                #     _warnings.append(
                #         f'Attempting to rename {file_name} to {new_file_name}.'
                #     )
                #     # Do the renaming
                #     new_file_path = os.path.join(root_directory, new_file_name)
                #     try:
                #         os.rename(file_path, new_file_path)
                #     except os.error:
                #         _warnings.append(f'Unable to rename {file_name}')
                #
                #     # fix up local data
                #     file_name = new_file_name
                #     file_path = new_file_path

                # Filename starts with hyphen
                # if file_name.startswith('-'):
                #     # Replace dash (-) with underscore
                #     new_file_name = re.sub('^-', '_', file_name)
                #     _warnings.append(
                #         'We do not accept files starting with a hyphen. '
                #         f'Attempting to rename {file_name} to {new_file_name}.'
                #     )
                #     # Do the renaming
                #     new_file_path = os.path.join(root_directory, new_file_name)
                #     try:
                #         os.rename(file_path, new_file_path)
                #     except os.error:
                #         _warnings.append(f'Unable to rename {file_name}')
                #     # fix up local data
                #     file_name = new_file_name
                #     file_path = new_file_path

                # Filename starts with dot (.)
                # if file_name.startswith('.'):
                #     # Remove files starting with dot
                #     msg = 'Hidden file are not allowed.'
                #     self.add_warning(obj.public_filepath, msg)
                #     self.remove(obj, f"Removed file '{obj.name}' [File not allowed].")
                #     continue

                # Following checks may only occur once in current file
                # as all are tied together with if / elif

                # TeX: Remove hyperlink styles espcrc2 and lamuphys
                # if re.search(r'^(espcrc2|lamuphys)\.sty$', file_name):
                #     obj = _add_file(file_path, _warnings, _errors)
                #     # TeX: styles that conflict with internal hypertex package
                #     msg = f"Found hyperlink-compatible package '{file_name}'. "\
                #           "Will remove and use hypertex-compatible local version"
                #
                #     self.remove(obj, msg)
                # elif re.search(r'^(espcrc2|lamuphys)\.tex$', file_name):
                #     # TeX: source files that conflict with internal hypertex package
                #     # I'm not sure why this is just a warning
                #     _warnings.append(
                #         f"Possible submitter error. Unwanted '{file_name}'"
                #     )


                # elif file_name == 'uufiles' or file_name == 'core' or file_name == 'splread.1st':
                #     # Remove these files
                #     msg = f"Removed the file '{file_name}' [File not allowed]."
                #     self.remove(obj, msg)
                # elif re.search(r'^xxx\.(rsrc$|finfo$|cshrc$|nfs)', file_name) \
                #         or re.search(r'\.[346]00gf$', file_name) \
                #         or (re.search(r'\.desc$', file_name) and file_size < 10):
                #     # Remove these files
                #     msg = f"Removed file '{obj.name}' [File not allowed]."
                #     self.remove(obj, msg)

                # elif re.search(r'(.*)\.bib$', file_name, re.IGNORECASE):
                #     # New modified handling of .bib without .bbl.
                #     # We no longer delete .bib UNLESS we detect .bbl file
                #     # Generate error until we have .bbl
                #     obj = _add_file(file_path, _warnings, _errors)
                #
                #     # Create path to bbl file - assume uses same basename as .bib
                #     filebase, _ = os.path.splitext(file_name)
                #     bbl_file = filebase + ".bbl"
                #     bbl_path = os.path.join(source_directory, bbl_file)
                #
                #     if os.path.exists(bbl_path):
                #         # If .bbl exists we go ahead and delete .bib file and
                #         # warn submitter of this action
                #
                #         # Present general warning to user.
                #         msg = Upload.bib_with_bbl_warning
                #         _warnings.append(msg)
                #         self.add_warning(obj.public_filepath, msg)
                #         msg = f"Removed the file '{file_name}'. Using '{bbl_file}' for references."
                #         self.remove(obj, msg)
                #     else:
                #         # Missing .bbl (potential missing references)
                #         # Generate an error and DO NOT DELETE .bib file
                #         # Note: We are using .bib as flag until .bbl exists
                #         _warnings.append(Upload.bib_no_bbl_warning)
                #         _errors.append(self.bbl_missing_error(filebase))

                # elif re.search(r'^(10pt\.rtx|11pt\.rtx|12pt\.rtx|aps\.rtx|'
                #                + r'revsymb\.sty|revtex4\.cls|rmp\.rtx)$',
                #                file_name):
                #     # TeX: submitter is including file already included
                #     # in TeX Live release
                #     # TODO: get revtex() warning message ???
                #     msg = Upload.revtex_warning
                #     self.remove(obj, msg)
                # elif re.search(, file_name):
                #     obj = _add_file(file_path, _warnings, _errors)
                #     # TeX: diagrams package contains a time bomb and stops
                #     # working after a specified date. Use internal version
                #     # with time bomb disable.
                #
                #     # TODO: get diagrams warning
                #     msg = Upload.diagrams_warning
                #     self.remove(obj, msg)
                # elif file_name == 'aa.dem':
                #     # TeX: Check for aa.dem
                #     # This is demo file that authors seem to include with
                #     # their submissions.
                #     self.add_warning \
                #         (obj.public_filepath,
                #          f"Removing file '{file_name}' on the assumption that it is "
                #          'the example file for the Astronomy and Astrophysics '
                #          'macro package aa.cls.'
                #          )
                #     self.remove(obj, "")
                # elif file_name == 'missfont.log':
                #     msg = Upload.missfont_warning
                #     self.remove(obj, msg)
                # elif re.search(r'\.synctex$', file_name):
                #     # .synctex files are generated by different TeX engine that we
                #     # do not use. We do not use.
                #     msg = f"Removed file '{file_name}'. SyncTeX files are not used by our" \
                #           " system and may be large."
                #     self.remove(obj, msg)
                # elif re.search(r'(.+)\.(log|aux|out|blg|dvi|ps|pdf)$', file_name,
                #                re.IGNORECASE):
                #     # TeX: Check for TeX processed output files (log, aux,
                #     # blg, dvi, ps, pdf, etc.)
                #     # Detect naming conflict, warn, remove offending files.
                #     # Check if certain source files exist
                #     filebase, _ = os.path.splitext(file_name)
                #     tex_file = os.path.join(root_directory, filebase + '.tex')
                #     upper_case_tex_file = os.path.join(root_directory, filebase + '.TEX')
                #
                #     if os.path.exists(tex_file) or os.path.exists(upper_case_tex_file):
                #         # Potential conflict / corruption by including TeX
                #         # generated files in submission
                #         msg = f"Removed file '{obj.public_filepath}' due to name conflict."
                #         self.remove(obj, msg)
                # elif re.search(r'[^\w\+\-\.\=\,]', file_name):
                #     # File name contains unwanted bad characters - this is an Error
                #     # We attempted to fix file_names with bad characters at
                #     # beginning of this routine
                #     _errors.append(
                #         f'Filename "{file_name}" contains unwanted bad '
                #         'character "$&", only allowed are '
                #         'a-z A-Z 0-9 _ + - . , ='
                #     )
                # elif re.search(r'([\.\-]t?[ga]?z)$', file_name):
                #     # Fix filename
                #     new_file_name = re.sub(r'([\.\-]t?[ga]?z)$', '', file_name,
                #                            re.IGNORECASE)
                #     new_file_path = os.path.join(root_directory, new_file_name)
                #     try:
                #         os.rename(file_path, new_file_path)
                #         msg = "Renaming '" + file_name + "' to '" \
                #               + new_file_name + "'."
                #         _warnings.append(msg)
                #         file_name = new_file_name
                #         file_path = new_file_path
                #     except os.error:
                #         _warnings.append(f'Unable to rename {file_name}')
                # elif re.search(r'\.doc$', file_name, re.IGNORECASE) and file_type == 'failed':
                #     # Doc warning
                #     msg = Upload.doc_warning
                #
                #     #_errors.append(msg)
                #     self.add_error(obj.public_filepath, msg)
                #     self.remove(obj, "")
                #

                # Finished basic file checks

                # We are done if file was marked as removed,
                # otherwise continue with additional type checks below
                if obj.removed:
                    continue

                # Placeholder for future checks/notes

                # TeX: Files that indicate user error
                # TODO: Investigate misfont.log error - possibly move handling here

                # TODO: diagrams detection script (does not exist in legacy system)
                # TeX: Detect various diagrams files where user changes name
                # of package. Implement at some point - just thinking of this
                # given recent failures.

                # Check for individual types if/elif/else

                # TeX: If dvi file is present we ask for TeX source
                #   Do we need to do this is TeX was also included???????
                # if file_type == 'dvi':
                #     msg = file_name + ' is a TeX-produced DVI file. ' \
                #           + ' Please submit the TeX source instead.'
                #     _errors.append(msg)

                # # Clean up any html
                # elif file_type == 'html':
                #     self.unmacify(obj)

                # Postscript - must check and clean up postscript
                #   unmacify, check_ps, ???
                # elif file_type == 'postscript' \
                #         or (file_type == 'failed' \
                #             and re.search(r'\.e?psi?$', file_name, re.IGNORECASE)):
                #     # unmacify
                #     if file_type == 'postscript':
                #         self.unmacify(obj)
                #
                #     # Check postscript for unwanted inclusions and inspect
                #     # unidentified files that appear to be Postscript
                #     self.check_postscript(obj, "")
                #
                #     # TODO: Sets type to postscript regardless of what
                #     # TODO: happens in check_postscript.
                #     # TODO: Should we at least warn? Or should we try to
                #     # TODO: check to see if type failed turned to postscript
                #     # TODO: after fixing up file in check_postscript?
                #     #
                    # TODO: Find example and test

                # # TeX: Check form of source for latex and latex2e
                # elif file_type == 'latex' or file_type == 'latex2e':
                #     # Check to see if preprint documentstyle is used
                #     self.formcheck(obj)

                # TeX: Check for image types that are not accepted
                # elif file_type == 'image' \
                #         and re.search(r'\.(pcx|bmp|wmf|opj|pct|tiff?)$',
                #                       file_name, re.IGNORECASE):
                #     self.graphics_error(obj)

                # # Uuencode file: decode uuencoded file
                # elif file_type == 'uuencoded':
                #     # I don't believe we are going to implement this unless
                #     # I discover evidence this is used in recent submissions.
                #     pass

                # File types we don't accept

                # RAR
                # elif file_type == 'rar':
                #     msg = "We do not support 'rar' files. Please use 'zip' or 'tar'."
                #     _errors.append(msg)

                # unmacify files of type PC and MAC
                # elif file_type == 'pc' or file_type == 'mac':
                #     self.unmacify(obj)

                # Repair files of type PS_PC
                # elif file_type == 'ps_pc':
                #     # TODO: Implement repair_ps
                #     # Seeing very few of this type in recent submissions
                #     # leer.eps header repaired to: %!PS-Adobe-2.0 EPSF-2.0
                #     self.repair_postscript(obj)

                # Repair dos eps
                # elif file_type == 'dos_eps':
                #     # Let's be specific about what we are doing.
                #     fixed = self.repair_dos_eps(obj)
                #     if fixed:
                #         # stripped TIFF
                #         if re.search('leading', fixed):
                #             msg = f"leading TIFF preview stripped"
                #         if re.search('trailing', fixed):
                #             msg = f"trailing TIFF preview stripped"
                #         self.add_warning(obj.public_filepath, msg)
                #     else:
                #         msg = "Failed to strip TIFF preview"
                #         self.add_warning(obj.public_filepath, msg)
                #         self.repair_postscript(obj)

                # TeX: If file is identified as core TeX type then we need to
                # unmacify
                # # check if file contains raw postscript
                # elif obj.is_tex_type:
                #     self.unmacify(obj)
                #     # TODO: Check if TeX source file contains raw Postscript
                #     self.extract_uu(file_name, file_type)

                obj = _add_file(file_path, _warnings, _errors)
                # End of file type checks


    # def check_file_termination(self, file_obj: File) -> None:
    #     r"""
    #     Check for unwanted characters at end of file.
    #
    #     The original unmacify/unpcify routine attemtps to cleanup the last few
    #     characters in a file regardless or whether the file is pc/mac generated.
    #     For that reason I have refactored the code into a seperate routine for
    #     ease of testing. This also simplifies the unmacify routine.
    #
    #     This code basically seeks to the end of file and removes any end of file \377,
    #     end of transmission ^D (\004), or  characters ^Z (\032).
    #
    #     At the current time this routine will get called anytime unmacify routine
    #     is called.
    #
    #     Parameters
    #     ----------
    #     file_obj : File
    #         File object containing details about file to unmacify.
    #
    #     """
    #     # Check for special characters at end of file.
    #     # Remove EOT/EOF
    #
    #     # Get the absolute file path
    #     filepath = file_obj.filepath
    #
    #     if self.debug():
    #         self.log(f"Checking file termination for {filepath}.")
    #
    #     if not os.path.exists(filepath):
    #         self.log(f"Check termination: File '{filepath}' doesn't exist.")
    #         return
    #
    #     with open(filepath, "rb+") as f:
    #
    #         # Seek to last two bytes of file
    #         f.seek(-2, 2)
    #
    #         # Examine bytes for characters we want to strip.
    #         input_bytes = f.read(2)
    #
    #         if self.debug():
    #             print(f"\nRead '{input_bytes}' from {file_obj.name}\n")
    #
    #         byte_found = False
    #         if input_bytes[0] == 0x01A or input_bytes[0] == 0x4 \
    #                 or input_bytes[0] == 0xFF:
    #             byte_found = True
    #
    #             f.seek(-2, 2)
    #             fsize = f.tell()
    #             f.truncate(fsize)
    #         elif input_bytes[1] == 0x01A or input_bytes[1] == 0x4 \
    #                 or input_bytes[1] == 0xFF:
    #             byte_found = True
    #             f.seek(-1, 2)
    #             fsize = f.tell()
    #             f.truncate(fsize)
    #
    #         if byte_found:
    #             msg = ""
    #
    #             if input_bytes[0] == 0x01A or input_bytes[1] == 0x01A:
    #                 msg += "trailing ^Z "
    #             if input_bytes[0] == 0x4 or input_bytes[1] == 0x4:
    #                 msg += "trailing ^D "
    #             if input_bytes[0] == 0xFF or input_bytes[1] == 0xFF:
    #                 msg += "trailing =FF "
    #             if input_bytes[1] == 0x0A:
    #                 self.log(f"{file_obj.public_filepath} [stripped newline] ")
    #
    #             self.add_warning(file_obj.public_filepath,
    #                              f"{msg}stripped from {file_obj.public_filepath}.")
    #
    #         # Check of last character of file is newline character
    #         # Seek to last two bytes of file
    #         f.seek(-1, 2)
    #         last_byte = f.read(1)
    #         if last_byte != b'\n':
    #             self.add_warning(file_obj.public_filepath,
    #                              (f"File '{file_obj.public_filepath}' does "
    #                               "not end with newline (\\n), TRUNCATED?."))
    #
    #
    # def unmacify(self, file_obj: File) -> None:
    #     """
    #     Cleans up files containing carriage returns and line feeds.
    #
    #     Files generated on Macs and Windows machines frequently have carriage
    #     returns that we must clean up prior to compilation.
    #
    #     Jake informs me there is a bug in the Perl unmacify routine.
    #
    #     Parameters
    #     ----------
    #     file_obj : File
    #         File object containing details about file to unmacify.
    #
    #     """
    #     # Determine type of file we are dealing with PC or MAC
    #     file_type = MAC
    #
    #     # Get the absolute file path
    #     filepath = file_obj.filepath
    #
    #     # Check whether file contains '\r\n' sequence
    #     with open(filepath, 'rb', 0) as file, \
    #         mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ) as s:
    #         if s.find(b"\r\n") != -1:
    #             file_type = PC
    #
    #     # Fix up carriage returns and newlines.
    #     self.log(f'Un{file_type}ify file {file_obj.filepath}')
    #
    #     # Open file and look for carriage return.
    #     #
    #     new_filepath = filepath + ".new"
    #     with open(filepath, 'rb', 0) as infile, \
    #         open(new_filepath, 'wb', 0) as outfile, \
    #             mmap.mmap(infile.fileno(), 0, access=mmap.ACCESS_READ) as s:
    #
    #         if file_type == PC:
    #             outfile.write(re.sub(b"\r\n", b"\n", s.read()))
    #         elif file_type == MAC:
    #             outfile.write(re.sub(b"\r\n?", b"\n", s.read()))
    #
    #         new_file_obj = File(new_filepath, os.path.dirname(new_filepath))
    #
    #         # Check if file was changed
    #         is_same = filecmp.cmp(filepath, new_filepath, shallow=False)
    #
    #         if is_same:
    #             os.remove(new_filepath)
    #         else:
    #             shutil.copy(new_filepath, filepath)
    #             os.remove(new_filepath)
    #
    #         # Check for unwanted termination character
    #         self.check_file_termination(file_obj)


    # def strip_tiff(self, file_obj: File) -> None:
    #     """
    #     Strip non-compliant embedded TIFF bitmaps from Postscript file.
    #
    #     Parameters
    #     ----------
    #     file_obj : File
    #         File with TIFF to be stripped.
    #
    #     Returns
    #     -------
    #         Need to decide if we need to return anything.
    #
    #     """
    #     self.log(f"checking '{file_obj.public_filepath}' for TIFF")
    #
    #     filepath = file_obj.filepath
    #
    #     # Check for embedded TIFF and truncate file if we find one.
    #
    #     # Adobe_level2_AI5 / terminate get exec
    #     # %%EOF
    #     # II *???
    #
    #     # Marker for end of Postscript file
    #     eof_marker = br'^%%EOF$'
    #     # Marker for TIFF image - little or big endian
    #     lb_marker = rb'^(II\*\000|MM\000\*)'
    #
    #     with open(filepath, 'rb+', 0) as infile:
    #
    #         lastnw = ""
    #         end = 0
    #
    #         # Read each line
    #         for line in infile:
    #
    #             # Find Postscript EOF
    #             if re.search(eof_marker, line):
    #                 pos = infile.tell()
    #
    #                 next_bytes = infile.readline(4)
    #
    #                 # Locate start of TIFF
    #                 if re.search(lb_marker, next_bytes):
    #                     end = pos
    #
    #                 # all set, we are done
    #                 break
    #
    #             # Find TIFF marker
    #             if re.search(lb_marker, line):
    #
    #                 offset = len(line)
    #                 end = infile.tell() - offset
    #                 infile.seek(end, 1)
    #
    #                 msg = f"No %%EOF, but truncate at {end} bytes, " \
    #                       f"lastnonwhitespace was {lastnw}  untruncated " \
    #                       f"version moved to $scratch_file"
    #                 self.log(msg)
    #
    #             # In the exception case, where Postscript %%EOF marker is not
    #             # detected before we detect TIFF bitmap, we will log last line
    #             # containing stuff before TIFF bitmap. TIFF is stripped.
    #             if re.search(rb'\S', line):
    #                 lastnw = line
    #
    #
    #         # Truncate file after EOF marker
    #         if end:
    #             infile.truncate(end)
    #
    #             msg = f"Non-compliant attached TIFF removed from '{file_obj.name}'"
    #             self.add_warning(file_obj.name, msg)


    # def strip_preview(self, file_obj: File, what_to_strip: str) -> None:
    #     """
    #     Remove embedded preview from Postscript file.
    #
    #     Parameters
    #     ----------
    #     file_obj : File
    #         File to strip embedded preview from.
    #     what_to_strip : str
    #         The type of inclusion that we are seeking to remove [Thumbnail,
    #         Preview, Photoshop]
    #     """
    #     if self.debug():
    #         self.log(f"Strip embedded '{what_to_strip}' from file '{file_obj.name}'.")
    #
    #     # Set start and end delimiters of preview.
    #
    #     if what_to_strip == PHOTOSHOP:
    #         start_re = b'^%BeginPhotoshop'
    #         end_re = b'^%EndPhotoshop'
    #     elif what_to_strip == PREVIEW:
    #         start_re = b'^%%BeginPreview'
    #         end_re = b'^%%EndPreview'
    #     elif what_to_strip == THUMBNAIL:
    #         start_re = b'Thumbnail'
    #         end_re = b'^%%EndData'
    #
    #     # Open a file to store stripped contents
    #     base_dir = file_obj.base_dir
    #     original_filepath = file_obj.filepath
    #     stripped_filename = file_obj.name + '.stripped'
    #     stripped_filepath = os.path.join(base_dir, stripped_filename)
    #
    #     if self.debug():
    #         self.log(f"File:{file_obj.name} in dir {base_dir} save to "
    #                  f"{stripped_filename} at {stripped_filepath}")
    #
    #     with open(original_filepath, 'rb', 0) as infile, \
    #             open(stripped_filepath, 'wb', 0) as outfile:
    #
    #         # Default is to retain all lines
    #         retain = True
    #         line_no = 1
    #         strip_warning = ''
    #
    #         # Read each line
    #         for line in infile:
    #
    #             # Check line for start pattern
    #             if retain and re.search(start_re, line):
    #                 strip_warning = f"Unnecessary {what_to_strip} removed "\
    #                                 + f"from '{file_obj.name}' from line {line_no}"
    #                 retain = False
    #
    #             if retain:
    #                 outfile.write(line)
    #
    #             # Check for end pattern
    #             if not retain and re.search(end_re, line):
    #                 strip_warning = strip_warning + f" to line {line_no},"
    #                 retain = True
    #                 # Handle bug in certain files
    #                 # AI bug %%EndData^M%%EndComments
    #                 if re.search(b'.*\r%/%', line):
    #                     outfile.write(line)
    #
    #             line_no = line_no + 1
    #
    #         infile.close()
    #         outfile.close()
    #
    #         # Generate some warnings
    #         if retain and strip_warning:
    #             orig_size = os.path.getsize(original_filepath)
    #             strip_size = os.path.getsize(stripped_filepath)
    #             shutil.copy(stripped_filepath, original_filepath)
    #             os.remove(stripped_filepath)
    #
    #             msg = f" reduced from {orig_size} bytes to {strip_size} bytes "\
    #                   + "(see http://arxiv.org/help/sizes)"
    #             strip_warning = strip_warning + msg
    #         else:
    #             if strip_warning:
    #                 msg = f"{file_obj.name} had unpaired $strip"
    #                 strip_warning = strip_warning + msg
    #             # Removed failed attempt to strip Postscript
    #             os.remove(stripped_filepath)
    #
    #         self.add_warning(file_obj.public_filepath, strip_warning)
    #
    # def repair_dos_eps(self, file_obj: File) -> str:
    #     """
    #     Look for leading/trailing TIFF bitmaps and remove them.
    #
    #     ADD MORE HERE
    #
    #     Parameters
    #     ----------
    #     file_obj : File
    #         File we are repairing.
    #
    #     Returns
    #     -------
    #         String message indicates that something was done and message details what was done.
    #
    #     Notes
    #     -----
    #         DOS EPS Binary File Header
    #
    #         0-3   Must be hex C5D0D3C6 (byte 0=C5).
    #         4-7   Byte position in file for start of PostScript language code section.
    #         8-11  Byte length of PostScript language section
    #         12-15 Byte position in file for start of Metafile screen representation.
    #         16-19 Byte length of Metafile section (PSize).
    #         20-23 Byte position of TIFF representation.
    #         24-27 Byte length of TIFF section.
    #
    #     """
    #     ps_filepath = file_obj.filepath
    #
    #     if not os.path.exists(ps_filepath):
    #         self.log(f"{file_obj.public_filepath}: File not found")
    #         return ""
    #
    #     with open(ps_filepath, 'r+b', 0) as infile:
    #
    #         # Read past ESP file marker (C5D0D3C6)
    #         infile.seek(4, 0)
    #
    #         # Read header bytes we are interested in
    #         header = infile.read(24)
    #         pb = struct.pack('24s', header)
    #
    #         # Extract offsets/lengths for Postscript and TIFF
    #         (psoffset, pslength, _, _, tiffoffset,
    #          tifflength) = struct.unpack('6i', pb)
    #
    #         #(f"psoffset:{psoffset} len:{pslength} tiffoffset:{tiffoffset}"
    #         # f"len:{tifflength}")
    #
    #         if not (psoffset > 0 and pslength > 0 and tiffoffset > 0
    #                 and tifflength > 0):
    #             # Encapsulated Postscript does not contain embedded TIFF
    #             return ""
    #
    #         # Extract Postscript
    #
    #         if psoffset > tiffoffset:
    #             # Postscript follows TIFF so we will seek
    #             # to Postscript and extract (eliminate header and TIFF)
    #
    #             # Seek to postscript
    #             infile.seek(psoffset, 0)
    #
    #             # Look for start of Postscript
    #             first_line = infile.readline()
    #
    #             if not re.search(b'^%!PS-', first_line):
    #                 # Issue a warning.
    #                 self.log(f"{file_obj.public_filepath}: Couldn't find "
    #                          f"beginning of Postscript section")
    #                 return ""
    #
    #             fixed_ps_filepath = os.path.join(file_obj.dir,
    #                                              file_obj.name + ".fixed")
    #             #print(f"Write fixed file:{fixed_ps_filepath}")
    #             with open(fixed_ps_filepath, 'wb', 0) as outfile:
    #                 # write out first line
    #                 outfile.write(first_line)
    #
    #                 # Read each line
    #                 for line in infile:
    #                     outfile.write(line)
    #
    #                 # Move repaired file into place
    #                 shutil.copy(fixed_ps_filepath, ps_filepath)
    #                 os.remove(fixed_ps_filepath)
    #
    #                 # Indicate we stripped header and leading TIFF
    #                 return f"stripped {psoffset} leading bytes"
    #
    #         elif psoffset < tiffoffset:
    #             # truncate the trailing TIFF image
    #             # strip off eps header leaving Postscript
    #
    #             # save a copy of original file before we hack it to death
    #             backup_filename = file_obj.name + ".original"
    #             backup_filepath = os.path.join(file_obj.dir, backup_filename)
    #             shutil.copy(ps_filepath, backup_filepath)
    #
    #             # Let's get rid of TIFF first
    #             infile.seek(tiffoffset, 0)
    #             offset = infile.tell()
    #             # truncate TIFF
    #             infile.truncate(offset)
    #
    #             # Seek to postscript
    #             infile.seek(psoffset, 0)
    #
    #             # Look for start of Postscript
    #             first_line = infile.readline()
    #
    #             if not re.search(b'^%!PS-', first_line):
    #                 # Issue a warning.
    #                 self.log(f"{file_obj.public_filepath}: Couldn't find "
    #                          f"beginning of Postscript section")
    #                 # remove backup file
    #                 os.remove(backup_filepath)
    #                 return ""
    #
    #             fixed_ps_filepath = os.path.join(file_obj.dir,
    #                                              file_obj.name + ".fixed")
    #
    #             with open(fixed_ps_filepath, 'wb', 0) as outfile:
    #                 # write out first line
    #                 outfile.write(first_line)
    #
    #                 # Read each line
    #                 for line in infile:
    #                     outfile.write(line)
    #
    #                 # Move repaired file into place
    #                 shutil.copy(fixed_ps_filepath, ps_filepath)
    #                 os.remove(fixed_ps_filepath)
    #
    #                 # Add warning about backup file we created
    #                 backup_obj = File(backup_filepath, file_obj.dir)
    #                 msg = (f"Modified file {file_obj.public_filepath}."
    #                        f"Saving original to {backup_obj.public_filepath}."
    #                        f"You may delete this file."
    #                        )
    #                 self.add_warning(backup_obj.public_filepath, msg)
    #
    #                 # Indicate we stripped header and trailing TIFF
    #                 return (f"stripped trailing tiff at {tiffoffset} bytes "
    #                         f"and {psoffset} leading bytes")


    # def repair_postscript(self, file_obj: File) -> str:
    #     """
    #     Repair simple corruptions at the beginning of Postscript file.
    #
    #     When repairs are made existing file is replacing with repaired file.
    #
    #     Parameters
    #     ----------
    #     file_obj : File
    #         Postscipt file we are cleaning up.
    #
    #     Returns
    #     -------
    #         Returns repaired first line of Postscipt file.
    #
    #     """
    #     # Check first 10 lines of Postscript file for corrupted statements
    #     broken_filepath = file_obj.filepath
    #     fixed_filepath = os.path.join(file_obj.dir, file_obj.name + '.fixed')
    #     orig_type = file_obj.type
    #     first_line = "%!\n"
    #
    #     with open(broken_filepath, 'rb', 0) as infile, \
    #             open(fixed_filepath, 'wb', 0) as outfile:
    #
    #         line = ''
    #         line_no = 0
    #         fixed = False
    #         stripped = b""
    #         message = ""
    #
    #         # Read each line
    #         for line in infile:
    #             line_no = line_no + 1
    #
    #             # Attempt to identify problems and repair
    #             if re.search(rb'^\%*\004\%\!', line):
    #                 # Case 1: special character 004
    #                 fixed = True
    #                 line = re.sub(br'^%*\004%!', br'%!', line)
    #                 message = message + "Removed carriage return from PS header. "
    #
    #             if re.search(rb'^\%\%\!', line):
    #                 # Case 2: extra '%' in header
    #                 fixed = True
    #                 line = re.sub(br'^%%!', br'%!', line)
    #                 message = message + "Removed extra '%' from PS header. "
    #
    #             if re.search(rb'.*(%!PS-Adobe-)', line):
    #                 # Case 3: characters in front of PS tag
    #                 fixed = True
    #                 # Clean up the line
    #                 line = re.sub(br'.*(%!PS-Adobe-)', br'\1', line)
    #                 message = message + "Removed extraneous characters before PS header. "
    #
    #             if re.search(b'^%!', line) or line_no > 10:
    #                 # we can stop searching
    #                 # If we haven't made any fixes then quit
    #                 break
    #
    #             # Keep track of what we are stripping off the front
    #             stripped = stripped + line
    #
    #         # Done with initial cleanup
    #
    #         if re.search(b'^%!', line):
    #             # Save stripped content
    #             if stripped:
    #                 cleaned_filepath = os.path.join(file_obj.dir, file_obj.name
    #                                                 + '.cleaned')
    #                 with open(cleaned_filepath, 'wb', 0) as cleanfile:
    #                     cleanfile.write(stripped)
    #                     cleanfile.close()
    #                 message = message + "Removed extraneous lines in front of PS header. "
    #
    #             # We are at start of Postscript file
    #             outfile.write(line)
    #             first_line = line
    #         else:
    #             # Reset to beginnng of broken file
    #             infile.seek(0, 0)
    #             # Otherwise insert start indicator
    #             outfile.write(b"%!\n")
    #
    #         # Write out the rest of file
    #         for line in infile:
    #             outfile.write(line)
    #
    #         if fixed:
    #             # Move repaired file into place
    #             shutil.copy(fixed_filepath, broken_filepath)
    #             os.remove(fixed_filepath)
    #
    #             # Check that type of file has changed to 'postscript' (new)
    #             # This also sets type of File object correctly for subsequent
    #             # processing
    #             file_obj.initialize_type()
    #             check_type = file_obj.type
    #
    #             if orig_type != check_type and check_type == 'postscript':
    #                 lm = f"Repaired Postscript file '{file_obj.name}': {message}'"
    #             else:
    #                 lm = f"Attempted repairs on Postscript file '{file_obj.name}': {message}'"
    #
    #             # Make note of the repair in log
    #             self.add_warning(file_obj.public_filepath, lm)
    #         else:
    #             # cleanup
    #             os.remove(fixed_filepath)
    #
    #         # Return first line
    #         return first_line[0:75]

    # def check_postscript(self, file_obj: File, tiff_flag: Union[str, None]) -> str:
    #     """
    #     Check Postscript file for unwanted inclusions.
    #
    #     Calls 'strip_preview' to preview, thumbnails, and photoshop.
    #
    #     Calls 'strip_tif' to remove non-compliant embedded TIFF bitmaps.
    #
    #     This set of routines (strip_preview, strip_tiff) may modify file by
    #     removing offending preview/thumbnail/photoshop/tiff bitmap.
    #
    #     This routine also deals with detecting imbedded fonts in Postscript
    #     files.
    #
    #     Parameters
    #     ----------
    #     file_type: str
    #         type of file as identified bu file_guess method.
    #     file_obj: File
    #         File we are checking and potentially cleaning up.
    #     tiff_flag: str
    #         ?? This might end up as a boolean flag.
    #
    #     Returns
    #     -------
    #         Nothing when routine runs to completion.
    #
    #     """
    #     file_type = file_obj.type
    #
    #     # This code had the incorrect type specified and never actually ran
    #     # Cleans up Postscript files file extraneous characters that cause
    #     # failure to identify file as Postscript.
    #     if file_type == 'failed':
    #         # This code has been not executing for many years. May have
    #         # resulted in more admin interventions to manually fix.
    #         header = self.repair_postscript(file_obj)
    #
    #         msg = f"File '{file_obj.public_filepath}' did not have proper "\
    #               + f"Postscript header, repaired to '{header}'."
    #         self.add_warning(file_obj.public_filepath, msg)
    #
    #     # Determine whether Postscript file contains preview, photoshop. fonts,
    #     # or resource.
    #
    #     # Scan Postscript file
    #
    #     # Get the absolute file path
    #     filepath = file_obj.filepath
    #
    #     pattern = re.compile(rb'Thumbnail:|BeginPreview|BeginPhotoshop|'
    #                          + rb'BeginFont|BeginResource: font',
    #                          re.DOTALL | re.IGNORECASE | re.MULTILINE)
    #
    #     if self.debug():
    #         self.log(f"\nCheck Postscript: '{file_obj.name}'")
    #
    #     # Check whether file contains '\r\n' sequence
    #     with open(filepath, 'rb', 0) as file, \
    #             mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ) as s:
    #
    #         # Search file for embedded preview markers
    #         results = pattern.findall(s)
    #
    #         if results:
    #             for match in results:
    #                 if match == b'BeginPhotoshop':
    #                     self.strip_preview(file_obj, PHOTOSHOP)
    #                 elif match == b'BeginPreview':
    #                     self.strip_preview(file_obj, PREVIEW)
    #                 elif match == b'Thumbnail:':
    #                     self.strip_preview(file_obj, THUMBNAIL)
    #
    #         # clean up open file descriptors
    #         file.close()
    #         s.close()
    #
    #     # TODO: Scan Postscript file for embedded fonts - need seperate ticket
    #     # We warn when user includes standard system fonts in their
    #     # Postscript files.
    #
    #     # TODO: Check for TIFF (need another ticket to tackle this task)
    #
    #     tiff_found = 0 # Some search of file for TIFF markers
    #
    #     if tiff_found:
    #         self.strip_tiff(file_obj)


    # def formcheck(self, file_obj: File) -> None:
    #     """
    #     Check whether submission is using preprint document style.
    #
    #     Adds warning if preprint style used in certain context.
    #
    #     Parameters
    #     ----------
    #     file_obj
    #
    #     """
    #     msg = "NOT IMPLEMENTED: formcheck routine needs to be implemented."
    #     #self.add_warning(file_obj.public_filepath, msg)
    #     self.log(file_obj.public_filepath + msg)

    # def graphic_error(self, file_obj: File) -> None:
    #     """
    #     Issue error for graphics that are not supported by arXiv.
    #
    #     Issue this error once due to possibility submission may contain
    #     dozens of invalid graphics files that we do not accept.
    #
    #     Parameters
    #     ----------
    #     file_obj : File
    #         File we do not accept.
    #
    #     """
    #     msg = self.get_graphic_error_msg("TIFF") # pylint
    #     msg = "NOT IMPLEMENTED: graphic error routine needs to be implemented."
    #     self.add_warning(file_obj.public_filepath, msg)

    # def extract_uu(self, file_name: str, file_type: str) -> None:
    #     """Extract uuencode content from file."""
    #     self.log(f'Looking for uu attachment in {file_name} of type {file_type}')
    #     self.log(f"I'm sorry Dave I'm afraid I can't do that. uu extract not implemented YET.")

    @property
    def total_upload_size(self) -> int:
        """
        Total size of client's uploaded content.

        This only refers to client
        files stored in workspace source subdirectory. This does not include
        backups, removed files/archives, or log files.

        Returns
        -------
        Total upload workspace in bytes.
        """
        return self.__total_upload_size

    @total_upload_size.setter
    def total_upload_size(self, total_size: int) -> None:
        """
        Set total submission size.

        Parameters
        ----------
        total_size in bytes

        """
        self.__total_upload_size = total_size

    def calculate_client_upload_size(self) -> None:
        """
        Calculate total size of client's upload workspace source files.

        Note
        ----
        This does not include system generated files (source.log, generated
        formats, or removed files.
        """
        # Calculate total upload workspace source directory size.
        source_directory = self.source_path

        total_upload_size = 0

        for root_directory, _, files in os.walk(source_directory):
            for file in files:
                path = os.path.join(root_directory, file)
                obj = File(path, source_directory)

                total_upload_size += obj.size

        total_upload_size_kb = total_upload_size / 1024.0
        total_upload_size_kb_str = '{:.2f}'.format(total_upload_size_kb)
        self.log(f'Total upload workspace size is {total_upload_size_kb_str} KB.')

        # Record total submission size
        self.total_upload_size = total_upload_size

    def create_file_list(self) -> list:
        """Create list of File objects."""
        # Make sure file list creation is working in check files before enabling.
        #
        # Not ready to enable.
        # Note: check files adds all files in upload archive. If this
        # routine is called elsewhere or (later) without processing upload the
        # list will not contain the files that have been removed.

        # Need to think about this a little since I'd like the UI
        # receive a list of ALL files including those which are
        # removed or rejected (but only for upload files action).

        source_directory = self.source_path

        self.__files = []
        self.log("File List:")
        for root_directory, directories, files in os.walk(source_directory):
            for directory in directories:
                # Need to decide whether we need to do anything to directories
                # in the meantime get rid of lint warning
                path = os.path.join(root_directory, directory)
                obj = File(path, source_directory)
                self.log(f'{directory} [{obj.type}] in {obj.filepath}')

            for file in files:
                path = os.path.join(root_directory, file)
                obj = File(path, source_directory)
                self.__files.append(obj)  # silence lint error

                # Create log entry containing file, type, dir
                log_msg = f'{obj.name} \t[{obj.type}] in {obj.dir}'
                self.log(log_msg)

        return self.__files

    def create_file_upload_summary(self) -> list:
        """
        Generate a list of files with details [dict].

        Maybe be generated when upload
        is processed or when run against existing upload directory.

        Return list of files created during upload processing or from list of
        files in directory.

        Generates a list of files in the upload source directory.

        Note: The detailed of regenerating the file list is still being worked out since
              the list generated during processing upload (includes removed files) may be
              different than the list generated against an existing source directory.

        Returns
        -------
        List of files where each entry is a dictionary containing details about
        file.
        """
        file_list = []

        if self.has_files():

            # TODO: Do we want count in response? Don't really need it but would
            # TODO: need to process list of files.
            # count = len(uploadObj.get_files())
            self.log("File Summary")
            for fileObj in self.get_files():
                # Temp debug
                #print("\tFile:" + fileObj.name + "\tFilePath: " + fileObj.public_filepath
                #     + "\tRemoved: " + str(fileObj.removed) + " Size: " + str(fileObj.size))

                # Collect details we would like to return to client
                file_details = {
                    'name': fileObj.name,
                    'public_filepath': fileObj.public_filepath,
                    'size': fileObj.size,
                    'type': fileObj.type_string,
                    'modified_datetime': fileObj.modified_datetime
                }

                if not fileObj.removed:
                    log_msg = f'{fileObj.name} \t[{fileObj.type}] in {fileObj.dir}'
                    self.log(log_msg)
                    file_list.append(file_details)

            return file_list
        return file_list

    def set_file_permissions(self) -> None:
        """
        Set the file permissions for all uploaded files and directories.

        Applies to files and directories in submitter's upload source
        directory.
        """
        # Start at directory containing source files
        source_directory = self.source_path

        # Set permissions on all directories and files
        for root_directory, directories, files in os.walk(source_directory):
            for file in files:
                file_path = os.path.join(root_directory, file)
                os.chmod(file_path, 0o664)
            for dir in directories:
                dir_path = os.path.join(root_directory, dir)
                os.chmod(dir_path, 0o775)

    def fix_top_level_directory(self) -> None:
        """
        Eliminate single top-level directory.

        Intended for case where submitter creates archive with all
        uploaded files in a subdirectory.
        """
        source_directory = self.source_path

        entries = os.listdir(source_directory)

        # If all of the upload content is within a single top-level directory,
        # move everything up one level and remove the directory. But don't
        # clobber the ancillary directory!
        if (len(entries) == 1
                and os.path.isdir(os.path.join(source_directory, entries[0]))
                and entries[0] != self.ANCILLARY_PREFIX):

            self.add_warning(entries[0], "Removing top level directory")
            single_directory = os.path.join(source_directory, entries[0])

            # Save copy in removed directory
            save_filename = os.path.join(self.removed_path,
                                         'move_source.tar.gz')
            with tarfile.open(save_filename, "w:gz") as tar:
                tar.add(single_directory, arcname=os.path.sep)

            # Remove existing directory
            if os.path.exists(single_directory):
                shutil.rmtree(single_directory)

            # Replace files
            if os.path.exists(save_filename):
                tar = tarfile.open(save_filename)
                # untar file into source directory
                tar.extractall(path=source_directory)
                tar.close()
            else:
                self.add_error('', 'Failed to remove top level directory.')

            # Set permissions
            self.set_file_permissions()

            # Rebuild file list
            self.create_file_list()

    def finalize_upload(self) -> None:
        """
        Checks to be performed after files are uploaded and sanitized.

        For file type checks that cannot be performed until all files
        are uploaded.

        Build final list of files contained in upload.

        Remove single top level directory.
        """
        # Only do this if we haven't generated list already
        if not self.has_files():
            self.create_file_list()

        # Eliminate top directory when only single directory
        self.fix_top_level_directory()

    def process_upload(self, file: FileStorage, ancillary: bool = False) \
            -> None:
        """
        Main entry point for processing uploaded files.

        Parameters
        ----------
        file : :class:`FileStorage`
            File object received from flask request.
        ancillary : bool
            If ``True``, file will be deposited in the ancillary directory.

        Returns
        -------
        None

        Notes
        -----
        This upload processing logic is originally derived/translated from the
        legacy system's Perl upload code. In order avoid breaking downstream
        clients this Python version faithfully implements as much of the
        original upload logic.

        Backward compatible improvements have been made to existing checks and
        new checks have been created. Existing legacy upload tests are included
        in test suite with many new and missing tests added.

        References
        ----------
        Original Perl code is located in Upload.pm (in arXivLib/lib/arXiv/Submit)
        """
        start = time.time()
        print('processing upload')
        # Upload_id and filename exists
        # Move this to log
        # print("\n---> Upload id: " + str(self.upload_id) + " FilenamePath: " + file.filename
        #      + " FilenameBase: " + os.path.basename(file.filename)
        #      + " Mime: " + file.mimetype + '\n')
        self.log('\n********** File Upload ************\n\n')

        # Move uploaded archive/file to source directory
        self.deposit_upload(file, ancillary=ancillary)
        print('processing upload: deposited upload at', time.time() - start)

        self.log('\n******** File Upload Processing *****\n\n')

        # Clear out any old warnings and errors from previous run
        self.clear_warnings_and_errors()

        # Unpack upload archive (if necessary). Completes minor cleanup.
        unpack_archive(self)
        print('processing upload: archive unpacked at', time.time() - start)

        # Build list of files
        self.create_file_list()
        print('processing upload: file list created at', time.time() - start)

        # Check files
        self.check_files()
        print('processing upload: files checked at', time.time() - start)

        # Check total file size
        self.calculate_client_upload_size()
        print('processing upload: size calculated at', time.time() - start)

        # Final cleanup
        self.finalize_upload()
        print('processing upload: finalized at', time.time() - start)

        self.log('\n******** File Upload Finished *****\n\n')

        self.log(f'\n******** Errors: {self.has_errors()} *****\n\n')

    # Content package routines

    def get_content_path(self) -> str:
        """
        Get the path for the packed content tarball.

        Note that the tarball itself may or may not exist yet.
        """
        return os.path.join(self.get_upload_directory(),
                            f'{self.upload_id}.tar.gz')

    def remove_content_package(self) -> None:
        """Delete the content package tarball."""
        if os.path.exists(self.get_content_path()):
            os.unlink(self.get_content_path())

    def pack_content(self) -> str:
        """Pack the entire source directory into a tarball."""
        if not self.has_files_on_disk():
            raise FileNotFoundError('No content to pack')
        self.remove_content_package()
        with tarfile.open(self.get_content_path(), "w:gz") as tar:
            tar.add(self.source_path, arcname=os.path.sep)
        return self.get_content_path()

    @property
    def last_modified(self) -> datetime:
        """Time of the most recent change to a file in the workspace."""
        most_recent = max(os.path.getmtime(root) for root, _, _
                          in os.walk(self.source_path))
        return datetime.fromtimestamp(most_recent, tz=UTC)

    def get_content(self) -> io.BufferedReader:
        """Get a file-pointer for the packed content tarball."""
        if not self.has_files_on_disk():
            raise FileNotFoundError('No content to get')
        if not self.content_package_exists or \
                (self.content_package_exists and self.content_package_stale):
            self.pack_content()
        return open(self.get_content_path(), 'rb')

    @property
    def content_package_exists(self) -> bool:
        """Return True if content package exists."""
        return os.path.exists(self.get_content_path())

    @property
    def content_package_modified(self) -> datetime:
        """Return modify datetime of content package."""
        return datetime.fromtimestamp(
            os.path.getmtime(self.get_content_path()),
            tz=UTC
        )

    @property
    def content_package_size(self) -> int:
        """
        Get the size of the compressed source package.

        Will build the package if it does not already exist.

        Returns
        -------
        int
            Total size in bytes of the compressed source package.

        """
        try:
            if not self.content_package_exists or self.content_package_stale:
                self.pack_content()
        except FileNotFoundError:
            return 0
        return os.path.getsize(self.get_content_path())

    @property
    def content_package_stale(self) -> bool:
        """
        Check whether source has been modified since content package creation.

        Returns
        -------
        bool
            True if content package is stale and needs to be regenerated.

        """
        if not os.path.exists(self.get_content_path()):
            return True
        return self.last_modified > self.content_package_modified

    def content_checksum(self) -> Optional[str]:
        """
        Return b64-encoded MD5 hash of the packed content tarball.

        Triggers building content package when pre-existing package is not
        found or stale relative to source files.
        """
        if not self.has_files_on_disk():
            return None
        if not self.content_package_exists or self.content_package_stale:
            self.pack_content()
        return self._get_checksum(self.get_content_path())

    def _get_checksum(self, path: str) -> str:
        hash_md5 = md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return urlsafe_b64encode(hash_md5.digest()).decode('utf-8')


    # Content file routines

    def content_file_path(self, public_file_path: str) -> str:
        """
        Return the absolute path of content file given relative pointer.

        Parameters
        ----------
        public_file_path : str
            Public file path relative to directory containing uploaded files.

        Returns
        -------
        Null if file does not exist.
        """
        file_obj = self.resolve_public_file_path(public_file_path)

        if file_obj is not None:
            return file_obj.filepath

        return ""

    def content_file_exists(self, public_file_path: str) -> bool:
        """
        Indicate whether files exists.

        Parameters
        ----------
        public_file_path : str
           Public file path relative to directory containing uploaded files.

        Returns
        -------
        True if file exists, False otherwise.

        """
        file_obj = self.resolve_public_file_path(public_file_path)

        if file_obj is not None:
            return os.path.exists(file_obj.filepath)

        return False

    def content_file_size(self, public_file_path: str) -> int:
        """
        Return size of specified file.

        Parameters
        ----------
        public_file_path

        Returns
        -------
        Size in bytes.
        """
        file_obj = self.resolve_public_file_path(public_file_path)

        if file_obj is not None:
            return file_obj.size

        return 0

    def content_file_checksum(self, public_file_path: str) -> str:
        """
        Generic routine to calculate checksum for arbitrary file argument.

        Parameters
        ----------
        public_file_path : str
            Public file path relative to directory containing uploaded files.

        Returns
        -------
        Returns Null string if file does not exist otherwise
        return b64-encoded MD5 hash of the specified file.

        """
        file_obj = self.resolve_public_file_path(public_file_path)

        if file_obj is not None:
            return file_obj.checksum

        return ""

    def content_file_pointer(self, public_file_path: str) -> io.BytesIO:
        """
        Open specified file and return file pointer.

        Parameters
        ----------
        public_file_path : str
            Public file path relative to directory containing uploaded files.

        Returns
        -------
        File pointer or Null string when filepath does not exist.

        """
        file_obj = self.resolve_public_file_path(public_file_path)

        if file_obj is not None and os.path.exists(file_obj.filepath):
            return open(file_obj.filepath, 'rb')

        return ""

    def content_file_last_modified(self, public_file_path: str) -> datetime:
        """
        Return last modified time for specified file/package.

        Parameters
        ----------
        public_file_path: str
            Public file path relative to directory containing uploaded files.

        Returns
        -------
        Last modified date string.
        """
        file_obj = self.resolve_public_file_path(public_file_path)

        print(f"File modified: {file_obj.modified_datetime}")
        dt = datetime.utcfromtimestamp(os.path.getmtime(file_obj.filepath))
        print(f"New File modified: {dt}")
        return datetime.utcfromtimestamp(os.path.getmtime(file_obj.filepath))

    # Source log methods

    @property
    def source_log_exists(self) -> bool:
        """
        Indicate whether source log exists.

        Returns
        -------
        True if source log file exists, otherwise returns False.

        """
        source_log_path = self.get_upload_source_log_path()

        return os.path.exists(source_log_path)

    @property
    def source_log_size(self) -> int:
        """
        Return size of source log.

        Returns
        -------
        Size in bytes.

        """
        source_log_path = self.get_upload_source_log_path()
        return os.path.getsize(source_log_path)

    @property
    def source_log_last_modified(self) -> str:
        """
        Last modified date of source log (UTC).

        Returns
        -------
        Last modified date string.
        """
        source_log_path = self.get_upload_source_log_path()
        return datetime.utcfromtimestamp(os.path.getmtime(source_log_path))

    @property
    def source_log_checksum(self) -> str:
        """
        Return checksum for source log.

        Returns
        -------
        Returns Null string if file does not exist otherwise
        return b64-encoded MD5 hash of the specified file.

        """
        source_log_path = self.get_upload_source_log_path()

        if os.path.exists(source_log_path):
            hash_md5 = md5()
            with open(source_log_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return urlsafe_b64encode(hash_md5.digest()).decode('utf-8')

        return ""

    def source_log_file_pointer(self) -> io.BytesIO:
        """Get a file-pointer for source log."""
        source_log_path = self.get_upload_source_log_path()

        if os.path.exists(source_log_path):
            return open(source_log_path, 'rb')

        return ""

    # def count_file_types(self) -> dict:
    #     """
    #     Count the number of files for each file format.
    #
    #     This routine simply creates a dictionary with file format name as
    #     key and number of files of this format type as value.
    #
    #     Returns
    #     -------
    #         Returns dictionary containing type in key and count for each type
    #         as value.
    #     """
    #     # Initialize file type accumulators and counters
    #     format_list = {'ancillary':0, 'all_files':0, 'directory':0, 'docx':0,
    #                    'html':0, 'image':0, 'ignore':0, 'include':0, 'odf':0,
    #                    'invalid':0, 'pdf':0, 'postscript':0, 'readme':0, 'texaux':0}
    #
    #     file_list = self.create_file_list()
    #
    #     for file in file_list:
    #         # Keep track of total number of files (includes ancillary)
    #         format_list['all_files'] = format_list['all_files'] + 1
    #
    #         if re.search('^anc/', file.public_filepath):
    #             # For our current purposes we will ignore ancillary files when
    #             # determining source format.
    #             file.type = 'ancillary'
    #
    #         if file.type not in format_list:
    #             format_list[file.type] = 1
    #         else:
    #             format_list[file.type] = format_list[file.type] + 1
    #
    #     # Calculate number of files in submission source (excludes ancillary files)
    #     format_list['files'] = format_list['all_files'] - format_list['ancillary']
    #
    #     self.log(f"All Files: {format_list['all_files']} files: "
    #              f"{format_list['files']} ancillary: {format_list['ancillary']}")
    #
    #     return format_list

    # def get_single_file(self) -> Optional[File]:
    #     """
    #     Return File object for single-file submission.
    #
    #     This routine is intended for submission that are composed
    #     of a single content file.
    #
    #     Single file can't be type 'ancillary'. Single ancillary file
    #     is invalid submission and generates an error.
    #
    #     Returns
    #     -------
    #         Single File object. Returns None when submission has more than
    #         one file.
    #     """
    #     if self.__files and len(self.__files) == 1:
    #         if self.__files[0].type != 'ancillary' and \
    #                 self.__files[0].type != 'always_ignore':
    #             return self.__files[0]
    #
    #         # This is an error, can't have submission that is composed
    #         # of ancillary single file
    #         obj = self.__files[0]
    #         msg = f"Found single ancillary file. Invalid submissiomn."
    #         self.add_error(obj.public_filepath, msg)
    #     elif self.__files and len(self.__files) > 1:
    #         # This should never happen
    #         msg = "Found more than 1 file in single file context"
    #         self.add_error("", msg)
    #     else:
    #         msg = "No file found."
    #         self.add_error("", msg)
    #
    #     return None


    # def fix_file_ext(self, file_obj: File, new_extension: str) -> Optional[File]:
    #     """
    #     Rename a file on disk to have the specified extension.
    #
    #     The current file object is dropped and a new file object is created.
    #
    #     There are different extensions for files of the same
    #     type. This routine normalizes all files of the same type to
    #     have the same file extension.
    #
    #     Parameters
    #     ----------
    #     file : File
    #         File object to 'fix' file extension.
    #     new_extension
    #         Desired extension for file name.
    #
    #     Returns
    #     -------
    #         Returns a File object when extension is already correct or new File
    #         object if the file is renamed. Returns None when there is an Error.
    #
    #     """
    #     # Return if file already has desired extension.
    #     if re.search(r'\.' + re.escape(new_extension) + '$', file_obj.filepath):
    #         return file_obj
    #
    #     # Otherwise rename file and update file object in list of files.
    #     filebase, _ = os.path.splitext(file_obj.name)
    #     new_file = filebase + f".{new_extension}"
    #     new_path = os.path.join(file_obj.base_dir, new_file)
    #
    #     # Rename the file
    #     try:
    #         if shutil.move(file_obj.filepath, new_path):
    #             msg = f"Renamed file '{file_obj.name}' to {new_file}."
    #             self.add_warning(file_obj.public_filepath, msg)
    #
    #             # Remove file from file list (just in case called from somewhere
    #             # other than process)
    #             self.remove_from_list(file_obj)
    #
    #             # Create new file onject and add to list
    #             file_path = os.path.join(file_obj.base_dir, new_file)
    #             new_file_obj = File(file_path, file_obj.base_dir)
    #             self.add_file(new_file_obj)
    #             return new_file_obj
    #     except FileNotFoundError as nf:
    #         self.add_error(file_obj.name, f"File '{file_obj.name}' to fix extension not found:"
    #                        f"Error:{nf}")
    #     except Exception as ce:
    #         self.add_error(file_obj.name, f"renaming file '{file_obj.name}' to have proper "
    #                        f"'.{new_extension}' extension failed: "
    #                        f"[{new_file}]: Error:{ce}")
    #
    #     # Update counts (assumine we are at point where counts are important)
    #     # Since we removed and added a file of same type I don't believe we need to
    #     # update counts like old code did.
    #     # TODO: Check if there is use case where type changes.
    #
    #     return None

    # @property
    # def source_format(self) -> str:
    #     """
    #     Determine high level format of all files in upload workspace.
    #
    #     This routine uses a hueristic to make best attempt to determine source
    #     format. Workspace may contain files of multiple formats. This routine
    #     makes best guess at primary/dominant format.
    #
    #     May return source format of "Unknown" in case where there are no files
    #     in workspace or we are not able to determine source format.
    #
    #     Returns
    #     -------
    #         String identifying source format. May be HTML, PDF, Postscript,
    #         TeX, Unknown.
    #     """
    #     # Analyze files formats in user upload workspace
    #     formats = self.count_file_types()
    #     source_format = 'invalid'
    #
    #     # if formats['files'] == formats['invalid']:
    #     #     # Were all files have been identified as type 'invalid'
    #     #     msg = ("All files are auto-ignore. If you intended to withdraw the"
    #     #            " article, please use the 'withdraw' function from the list"
    #     #            "of articles on your account page.")
    #     #     self.add_warning("", msg)
    #     #     source_format = 'invalid'
    #     # elif formats['all_files'] == 0:
    #     #     # No files detected, were all files removed? did user clear out
    #     #     # files? Since users are allowed to remove all files we won't
    #     #     # generate a message here. If system deletes all uploaded
    #     #     # files there will be warnings associated with those actions.
    #     #     source_format = 'invalid'
    #     # elif formats['all_files'] > 0 and formats['files'] == 0:
    #     #     # No source files detected, extra ancillary files may be present
    #     #     # User may have deleted main document source.
    #     #     source_format = 'invalid'
    #
    #     # Submission is single file (PDF/PS/HTML/etc.)
    #     elif formats['files'] == 1:
    #         # The submission is composed of only one file, or submitter has
    #         # not finished uploading files (piecemeal)
    #         # Retrieve File object since we'll need name, type, filepath,
    #         # and public_filepath
    #         obj = self.get_single_file()
    #         name = obj.name
    #         file_type = obj.type
    #         public_file_path = obj.public_filepath

            # Handle all cases where submission source format is single file.

            # if formats['docx'] > 0:
            #     # We no longer accept docx
            #     msg = ("Submissions in docx are no longer supported. Please "
            #            "create a PDF file and submit that instead. Server "
            #            "side conversion of .docx to PDF may lead to incorrect "
            #            "font substitutions, among other problems, and your own "
            #            "PDF is likely to be more accurate.")
            #     source_format = 'invalid'
            #     self.add_error(public_file_path, msg)
            # elif formats['odf'] > 0:
            #     # ODF not supportedf
            #     msg = ("Unfortunately arXiv does not support ODF. "
            #            "Please submit PDF instead.")
            #     source_format = 'invalid'
            #     self.add_error(public_file_path, msg)
            # # Check for invalid formats
            # elif re.search(r'\.eps$', name, re.IGNORECASE):
            #     # Single file ending n .eps
            #     # ? Have users actually tried to submit .eps file ?
            #     msg = f"'{public_file_path}' appears to be a single encapsulated PostScript file"
            #     source_format = 'invalid'
            #     self.add_error(public_file_path, msg)
            # elif formats['files'] == formats['texaux']:
            #     # texaux file by itself
            #     msg = f"'{public_file_path}' appears to be a single auxiliary TeX file"
            #     source_format = 'invalid'
            #     self.add_error(public_file_path, msg)
            # elif file_type == 'postscript':
            #     # The logic for Postscript format actually verifies that the format
            #     # is valid Postscript by running Ghostscript
            #     # Rename
            #     new_file_obj = self.fix_file_ext(obj, 'ps')
            #     # TODO: This rename should eventually move to check routine
            #     if new_file_obj is not None:
            #         obj = new_file_obj
            #         # TODO: NEED TO PERFORM LIVE PS FORMAT CHECK
            #         # TODO: Do we want to do something else when Postscript
            #         # TODO: file fails to validate? We currently generate
            #         # TODO: warning AND set format to 'ps' (as if it's
            #         # TODO: possible to continue.
            #         source_format = 'ps'
            #     else:
            #         # TODO: What to do here? 'None' indicates error. This is
            #         # TODO: internal error. Error has been registered. Not
            #         # TODO: much user can do.
            #         pass
            # elif file_type == 'pdf':
            #     # Rename
            #     # TODO: This rename should eventually move to check routine
            #     new_file_obj = self.fix_file_ext(obj, 'pdf')
            #     if new_file_obj is not None:
            #         obj = new_file_obj
            #         source_format = 'pdf'
            #         # TODO: Check whether we need filename
            #     else:
            #         # TODO: What to do here? 'None' indicates error. This is
            #         # TODO: internal error. Error has been registered. Not
            #         # TODO: much user can do.
            #         pass
            # elif file_type == 'html':
            #     # Rename
            #     # TODO: This rename should eventually move to check routine
            #     new_file_obj = self.fix_file_ext(obj, 'html')
            #     if new_file_obj is not None:
            #         obj = new_file_obj
            #         source_format = 'html'
            #     else:
            #         # TODO: What to do here?  'None' indicates error. This is
            #         # TODO: internal error. Error has been registered. Not
            #         # TODO: much user can do.
            #         pass
            # elif file_type == 'failed':
            #     msg = f"Could not determine type of file '{public_file_path}'"
            #     source_format = 'invalid'
            #     self.add_error(public_file_path, msg)
            # Check whether type is TeX
            # elif obj.is_tex_type:
            #     # Single file TeX submission
            #     source_format = 'tex'
            # else:
            #     source_format = 'invalid'
            #     self.add_error(public_file_path, "Unable to determine submission type.")

        # # Multiple file submissions
        # elif formats['html'] > 0 and \
        #     formats['files'] == (formats['html'] + formats['image'] +
        #                          formats['include'] +
        #                          formats['postscript'] + formats['pdf'] +
        #                          formats['directory'] + formats['readme']):
        #     # HTML submissions may contain the above formats
        #     source_format = 'html'
        # elif formats['postscript'] > 0 and \
        #     formats['files'] == (formats['postscript'] + formats['pdf'] +
        #                          formats['ignore'] + formats['directory'] +
        #                          formats['image']):
        #     # Postscript submission may be composed of several other formats
        #     source_format = 'ps'
        # else:
        #     # Default source type is TEX
        #     source_format = 'tex'
        #
        # return source_format
