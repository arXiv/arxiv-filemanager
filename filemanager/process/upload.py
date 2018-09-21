"""Provides functions that sanitizes :class:`.Upload."""

import os
import re
from datetime import datetime
from pytz import UTC
import shutil
import tarfile
import logging
from hashlib import md5
from base64 import b64encode
import io

from werkzeug.exceptions import BadRequest, NotFound, SecurityError
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from arxiv.base.globals import get_application_config
from filemanager.arxiv.file import File as File
from filemanager.utilities.unpack import unpack_archive

UPLOAD_FILE_EMPTY = 'file payload is zero length'
UPLOAD_DELETE_FILE_FAILED = 'unable to delete file'
UPLOAD_DELETE_ALL_FILE_FAILED = 'unable to delete all file'
UPLOAD_FILE_NOT_FOUND = 'file not found'
UPLOAD_WORKSPACE_NOT_FOUND = 'workspcae not found'


def _get_base_directory() -> str:
    config = get_application_config()
    return config.get('UPLOAD_BASE_DIRECTORY',
                      '/tmp/filemanagment/submissions')


class Upload:
    """Handle uploaded files: unzipping, putting in the right place, doing
various file checks that might cause errors to be displayed to the
submitter."""

    SOURCE_PREFIX = 'src'
    """The name of the source directory within the upload workspace."""

    REMOVED_PREFIX = 'removed'
    """The name of the removed directory within the upload workspace."""

    ANCILLARY_PREFIX = 'anc'
    """The directory within source directory where ancillary files are kept."""

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

        # total client upload workspace source directory size (in bytes)
        self.__total_upload_size = 0

        self.__log = ''
        self.create_upload_workspace()
        self.create_upload_log()
        # Calculate size just in case client is making request that does
        # not upload or delete files. Those requests update total size.
        self.calculate_client_upload_size()

    # Files

    def has_files(self) -> bool:
        """Indicates whether files list contains entries."""
        if self.__files:
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

    # Warnings

    def add_warning(self, public_filepath: str, msg: str) -> None:
        """
        Record and log warning for this upload instance."
        Parameters
        ----------
        msg
            User-friendly warning message. Intended to support corrective action.

        Returns
        -------
        None

        """

        # print('Warning: ' + msg) # temporary, until logging implemented
        # Log warning
        ##msg = 'Warning: ' + msg
        #  TODO: This breaks tests. Don't reformat message for now. Wait until next sprint.
        self.__log.warning(msg)

        # Add to internal list to make it easier to manipulate
        entry = [public_filepath, msg]
        # self.__warnings.append(msg)
        self.__warnings.append(entry)

    def has_warnings(self):
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
            # Turn this into debugging
            # print("Look for '" + search + '\' in \n\t \'' + warning +"'")
            # print("ret: " + str(re.search(search, warning)))

            filename, warning = entry
            if re.match(search, warning):
                return True

        return False

    def get_warnings(self) -> list:
        """Get list of upload warnings."""
        return self.__warnings

    # Errors

    def add_error(self, public_filepath: str, msg: str) -> None:
        """Record error for this upload instance."""
        print('Error: ' + msg)
        entry = [public_filepath, msg]
        self.__errors.append(entry)

    def has_errors(self):
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
            # Turn this into debugging
            # print("Look for '" + search + '\' in \n\t \'' + warning +"'")
            # print("ret: " + str(re.search(search, warning)))

            filename, error = entry
            if re.match(search, error):
                return True

        return False

    def get_errors(self) -> list:
        """Get list of upload errors."""
        return self.__errors

    @property
    def upload_id(self) -> int:
        """Return upload identifier.

        The unique identifier for upload.

        """
        return self.__upload_id

    def remove_file(self, file: File, msg: str) -> bool:
        """
        Remove file from source directory.

        Moves specified file to 'removed' directory and marks File
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

        Notes
        -----

        """

        # Move file to removed directory
        filepath = file.filepath
        removed_path = os.path.join(self.get_removed_directory(), file.name)
        # self.__log.debug("Moving file " + file.name + " to removed dir: " + removed_path)

        if shutil.move(filepath, removed_path):
            # lmsg = "*** File " + file.name + f" has been removed. Reason: {msg} ***"
            lmsg = f"Removed hidden file {file.name}."
            self.add_warning(file.public_filepath, lmsg)
        else:
            self.add_warning("*** FAILED to remove file " + filepath + " ***")

        # Add reason for removal to File object
        file.remove(msg)

        # We won't recalculate size here because we know total size will be
        # recalculated after all file checks (uses this routine) are complete.

    def remove_workspace(self) -> bool:
        """Remove upload workspace. This request completely removes the upload
        workspace directory. No backup is made here (system backups may have files
        for period of time).

        Returns
        -------

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
            padded_id = '{0:07d}'.format(self.__upload_id)
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

    def resolve_public_file_path(self, public_file_path: str) -> str:
        """
        Resolve a relative file path to an absolute file path.

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
            message = f"SECURITY WARNING: file to delete contains illegal constructs: '{public_file_path}'"
            self.log(message)
            raise SecurityError(message)

        # Secure filename should not change length of valid file path (but it will
        # mess with directory slashes '/')
        # TODO: Come up with better file path checker. We allow subdirectories
        # TODO: and secure_filename strips them (/ => _)
        # The length of file path should not change (need to check secure_filename)
        # so if length changes generate warning.
        if len(public_file_path) != len(filename):
            message = f"SECURITY WARNING: sanitized file is different length: '{filename}' <=> '{public_file_path}'"
            self.log(message)
            raise SecurityError(message)

        # Resolve relative path of file to filesystem
        src_directory = self.get_source_directory()
        file_path = os.path.join(src_directory, filename)

        # secure_filename will eliminate '/' making paths to subdirectories
        # impossible to resolve. Make assumption we caught bad actors with checks above.

        # Check if original path might be subdirectory.
        # We've made it past serious threat checks above.
        if not os.path.exists(file_path) and re.search(r'_', filename) and re.search(r'/', public_file_path):
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

        if os.path.exists(file_path):
            return file_path
        else:
            return ""


    def client_remove_file(self, public_file_path: str) -> bool:
        """Delete a single file.

        For a single file delete we will move it to 'removed' directory.

        Parameters
        ----------
        public_file_path: str
            Relative path of file to be deleted.

        Returns
        -------

        True on success.

        Notes
        _____
        We are logging messages to source log. Warnings are not passed
        back in response for non-upload requests so we skip issuing warnings/errors.

        """

        self.log('********** Delete File ************\n')

        # Check whether client is trying to damage system with invalid path

        # TODO: Switch to use resolve relative file path to eliminate duplicate code

        # Sanitize file name
        filename = secure_filename(public_file_path)

        # Our UI will never attempt to delete a file path containing components that attempt
        # to escape out of workspace and this would be removed by secure_filename().
        # This error must be propagated to wider notification level beyond source log.
        if re.search(r'^/|^\.\./|\.\./', public_file_path):
            # should never start with '/' or '../' or contain '..' anywhere in path.
            message = f"SECURITY WARNING: file to delete contains illegal constructs: '{public_file_path}'"
            self.log(message)
            raise SecurityError(message)

        # Secure filename should not change length of valid file path (but it will
        # mess with directory slashes '/')
        # TODO: Come up with better file path checker. We allow subdirectories
        # TODO: and secure_filename strips them (/ => _)
        # The length of file path should not change (need to check secure_filename)
        # so if length changes generate warning.
        if len(public_file_path) != len(filename):
            message = f"SECURITY WARNING: sanitized file is different length: '{filename}' <=> '{public_file_path}'"
            self.log(message)
            raise SecurityError(message)

        # Resolve relative path of file to filesystem
        src_directory = self.get_source_directory()
        file_path = os.path.join(src_directory, filename)

        # secure_filename will eliminate '/' making paths to subdirectories
        # impossible to resolve. Make assumption we caught bad actors with checks above.

        # Check if original path might be subdirectory.
        # We've made it past serious threat checks above.
        if not os.path.exists(file_path) and re.search(r'_', filename) and re.search(r'/', public_file_path):
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
            removed_path = os.path.join(self.get_removed_directory(), clean_public_path)
            self.log(f"Delete file: '{filename}'")

            if shutil.move(file_path, removed_path):
                self.log(f"Moved file from {file_path} to {removed_path}")
                return True
            else:
                self.log(f"*** FAILED to remove file '{file_path}'/{clean_public_path} ***")
                return False

            # Recalculate total upload workspace source directory size
            self.calculate_client_upload_size()

        else:
            self.log(f"File to delete not found: '{public_file_path}' '{filename}'")
            raise NotFound(UPLOAD_FILE_NOT_FOUND)

    def client_remove_all_files(self) -> bool:
        """Delete all files uploaded by client from specified workspace.

        For client delete requests we assume they have copies of original files and
        therefore do NOT backup files.

        Returns
        -------

        """

        self.log('********** Delete ALL Files ************\n')

        # Cycle through list of files under src directory and remove them.
        #
        # For now we will remove file by moving it to 'removed' directory
        src_directory = self.get_source_directory()
        self.log(f"Delete all files under directory '{src_directory}'")

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
        Get top level workspace directory for submission."

        Returns
        -------
        str
            Top level directory path for upload workspace.
        """

        root_path = _get_base_directory()
        upload_directory = os.path.join(root_path, str(self.upload_id))
        return upload_directory

    def create_upload_directory(self):
        """Create the base directory for upload workarea"""

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

    def get_source_directory(self) -> str:
        """Return directory where source files get deposited."""
        return os.path.join(self.get_upload_directory(), self.SOURCE_PREFIX)

    def get_removed_directory(self) -> str:
        """Get directory where source archive files get moved when unpacked."""
        return os.path.join(self.get_upload_directory(), self.REMOVED_PREFIX)

    def get_ancillary_directory(self) -> str:
        """
        Get directory where ancillary files are stored.

        If the directory does not already exist, it will be created.
        """
        path = os.path.join(self.get_source_directory(), self.ANCILLARY_PREFIX)
        if not os.path.exists(path):
            os.mkdir(path)
        return path

    def create_upload_workspace(self):
        """Create directories for upload work area."""
        # Create main directory
        base_dir = self.create_upload_directory()

        # TODO what directories do we want to carry over from existing upload/submission system
        src_dir = self.get_source_directory()

        if not os.path.exists(src_dir):
            # Create path for submissions
            # TODO determine if we need to set owner/modes
            os.makedirs(src_dir, 0o755)
            # print("Created src workarea\n");

        removed_dir = self.get_removed_directory()

        if not os.path.exists(removed_dir):
            # Create path for submissions
            # TODO determine if we need to set owner/modes
            os.makedirs(removed_dir, 0o755)
            # print("Created removed workarea\n");

        return base_dir

    def get_upload_source_log_path(self):
        """Generate path for upload source log."""
        return os.path.join(self.get_upload_directory(), 'source.log')

    def create_upload_log(self):
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

    def log(self, message: str):
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
        print('.', filename)

        if basename != filename:
            self.log(f'Secured filename: {filename} (basename + )')

        if ancillary:  # Put the file in the ancillary directory.
            src_directory = self.get_ancillary_directory()
        else:  # Store uploaded file/archive in source directory
            src_directory = self.get_source_directory()

        upload_path = os.path.join(src_directory, filename)
        file.save(upload_path)
        if os.stat(upload_path).st_size == 0:
            raise BadRequest(UPLOAD_FILE_EMPTY)
        return upload_path

    def check_files(self) -> None:
        """
        This is the main loop that goes through the list of files and performs
        a long list of checks that depend on file type, extension, and sometimes file name.

        Returns
        -------
        None
        """

        self.log('\n******** Check Files *****\n\n')

        source_directory = self.get_source_directory()

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
                if obj.size == 0:
                    msg = obj.name + " is empty (size is zero)"
                    # self.add_warning(obj.public_filepath, msg)
                    _warnings.append(msg)
                    obj = _add_file(file_path, _warnings, _errors)
                    self.remove_file(obj, f"Removed: {msg}")
                    continue

                # Remove 10240 byte all-null files (bad user tar attempts?)
                # Check of file is 10240 bytes and all are zero

                # Rename Windows file names
                if re.search(r'^[A-Za-z]:\\', file_name):
                    # Rename using basename
                    new_name = re.sub(r'^[A-Za-z]:\\(.*\\)?', '', file_name)
                    new_file_path = os.path.join(root_directory, new_name)
                    msg = 'Renaming ' + file_name + ' to ' + new_name + '.'
                    _warnings.append(msg)
                    os.rename(file_path, new_file_path)
                    # fix up local data
                    file_name = new_name
                    file_path = new_file_path

                # Keep an eye out for special ancillary 'anc' directory
                anc_dir = os.path.join(self.get_source_directory(),
                                       self.ANCILLARY_PREFIX)
                if file_path.startswith(anc_dir):
                    statinfo = os.stat(file_path)
                    kilos = statinfo.st_size
                    warn = "Ancillary file " + file_name + " (" + str(kilos) + ')'
                    ##self.add_warning(warn)
                    obj.type = 'ancillary'
                    # We are done at this point - we do not inspect ancillary files
                    ##continue

                # Basic file checks

                # Attempt to rename filenames containing illegal characters

                # Filename contains illegal characters+,-,/,=,
                if re.search(r'[^\w\+\-\.\=\,]', file_name):
                    # Translate bad characters
                    new_file_name = re.sub(r'[^\w\+\-\.\=\,]', '_', file_name)
                    _warnings.append(
                        "We only accept file names containing the characters: "
                        "a-z A-Z 0-9 _ + - . , ="
                    )
                    _warnings.append(
                        f'Attempting to rename {file_name} to {new_file_name}.'
                    )
                    # Do the renaming
                    new_file_path = os.path.join(root_directory, new_file_name)
                    try:
                        os.rename(file_path, new_file_path)
                    except os.error:
                        _warnings.append(f'Unable to rename {file_name}')

                    # fix up local data
                    file_name = new_file_name
                    file_path = new_file_path

                # Filename starts with hyphen
                if file_name.startswith('-'):
                    # Replace dash (-) with underscore
                    new_file_name = re.sub('^-', '_', file_name)
                    _warnings.append(
                        'We do not accept files starting with a hyphen. '
                        f'Attempting to rename {file_name} to {new_file_name}.'
                    )
                    # Do the renaming
                    new_file_path = os.path.join(root_directory, new_file_name)
                    try:
                        os.rename(file_path, new_file_path)
                    except os.error:
                        _warnings.append(f'Unable to rename {file_name}')
                    # fix up local data
                    file_name = new_file_name
                    file_path = new_file_path

                # Filename starts with dot (.)
                if file_name.startswith('.'):
                    obj = _add_file(file_path, _warnings, _errors)

                    # Remove files starting with dot
                    msg = 'Removed hidden file'
                    # self.add_warning(msg)
                    self.remove_file(obj, msg)

                    continue

                # Following checks can only occur once in current file
                # all are tied together with if / elif

                # TeX: Remove hyperlink styles espcrc2 and lamuphys
                if re.search(r'^(espcrc2|lamuphys)\.sty$', file_name):
                    obj = _add_file(file_path, _warnings, _errors)
                    # TeX: styles that conflict with internal hypertex package
                    print("Found hyperlink-compatible package\n")
                    # TODO: Check the error/warning messaging for this check.
                    self.remove_file(obj, msg)
                    _warnings.append(
                        '   -- instead using hypertex-compatible local version'
                    )
                elif re.search(r'^(espcrc2|lamuphys)\.tex$', file_name):
                    # TeX: source files that conflict with internal hypertex package
                    # I'm not sure why this is just a warning
                    _warnings.append(
                        f"Possible submitter error. Unwanted '{file_name}'"
                    )
                elif file_name == 'uufiles' or file_name == 'core' or file_name == 'splread.1st':
                    obj = _add_file(file_path, _warnings, _errors)
                    # Remove these files
                    msg = 'File not allowed.'
                    self.remove_file(obj, msg)
                elif re.search(r'^xxx\.(rsrc$|finfo$|cshrc$|nfs)', file_name) \
                        or re.search(r'\.[346]00gf$', file_name) \
                        or (re.search(r'\.desc$', file_name) and file_size < 10):
                    obj = _add_file(file_path, _warnings, _errors)
                    # Remove these files
                    msg = 'File not allowed.'
                    self.remove_file(obj, msg)
                elif re.search(r'(.*)\.bib$', file_name, re.IGNORECASE):
                    obj = _add_file(file_path, _warnings, _errors)
                    # TeX: Remove bib file since we do not run BibTeX
                    # TODO: Generate bib warning bib()??
                    msg = 'Removing ' + file_name \
                          + ". Please upload .bbl file instead."
                    self.remove_file(obj, msg)
                elif re.search(r'^(10pt\.rtx|11pt\.rtx|12pt\.rtx|aps\.rtx|'
                               + r'revsymb\.sty|revtex4\.cls|rmp\.rtx)$',
                               file_name):
                    obj = _add_file(file_path, _warnings, _errors)
                    # TeX: submitter is including file already included
                    # in TeX Live release
                    # TODO: get revtex() warning message ???
                    self.remove_file(obj, msg)
                elif re.search(r'^diagrams\.(sty|tex)$', file_name):
                    obj = _add_file(file_path, _warnings, _errors)
                    # TeX: diagrams package contains a time bomb and stops
                    # working after a specified date. Use internal version
                    # with time bomb disable.

                    # TODO: get diagrams warning
                    msg = ''
                    self.remove_file(obj, msg)
                elif file_name == 'aa.dem':
                    obj = _add_file(file_path, _warnings, _errors)
                    # TeX: Check for aa.dem
                    # This is demo file that authors seem to include with
                    # their submissions.
                    self.remove_file(obj, msg)
                    _warnings.append(
                        f'REMOVING {file_name} on the assumption that it is '
                        'the example file for the Astronomy and Astrophysics '
                        'macro package aa.cls.'
                    )
                elif re.search(r'(.+)\.(log|aux|blg|dvi|ps|pdf)$', file_name,
                               re.IGNORECASE):
                    # TeX: Check for TeX processed output files (log, aux,
                    # blg, dvi, ps, pdf, etc.)
                    # Detect naming conflict, warn, remove offending files.
                    # Check if certain source files exist
                    filebase, file_extension = os.path.splitext(file_name)
                    tex_file = os.path.join(root_directory, filebase, '.tex')
                    upper_case_tex_file = os.path.join(root_directory, filebase, '.TEX')
                    if os.path.exists(tex_file) or os.path.exists(upper_case_tex_file):
                        self.add_file(obj)  # Adding to preserve behavior.
                        # Potential conflict / corruption by including TeX
                        # generated files in submission
                        _warnings.append(' REMOVING $fn due to name conflict')
                        self.remove_file(obj, msg)
                elif re.search(r'[^\w\+\-\.\=\,]', file_name):
                    # File name contains unwanted bad characters - this is an Error
                    # We attempted to fix file_names with bad characters at
                    # beginning of this routine
                    _errors.append(
                        f'Filename "{file_name}" contains unwanted bad '
                        'character "$&", only allowed are '
                        'a-z A-Z 0-9 _ + - . , ='
                    )
                elif re.search(r'([\.\-]t?[ga]?z)$', file_name):
                    # Fix filename
                    new_file_name = re.sub(r'([\.\-]t?[ga]?z)$', '', file_name,
                                           re.IGNORECASE)
                    new_file_path = os.path.join(root_directory, new_file_name)
                    try:
                        os.rename(file_path, new_file_path)
                        msg = "Renaming '" + file_name + "' to '" \
                              + new_file_name + "'."
                        _warnings.append(msg)
                        file_name = new_file_name
                        file_path = new_file_path
                    except os.error:
                        _warnings.append(f'Unable to rename {file_name}')
                elif file_name.endswith('.doc') and type == 'failed':
                    obj = _add_file(file_path, _warnings, _errors)
                    # Doc warning
                    # TODO: Get doc warning from message class
                    msg = ''
                    # TODO: need to log error
                    _errors.append(msg)
                    self.remove_file(obj, msg)

                # Finished basic file checks

                # We are done if file was marked as removed,
                # otherwise continue with additional type checks below
                if obj.removed:
                    print("File was removed -- skipping to next file\n")
                    continue

                # Placeholder for future checks/notes

                # TeX: Files that indicate user error
                # TODO: Investigate missfont.log error - possibly move handling here

                # TODO: diagrams detection script (does not exist in legacy system)
                # TeX: Detect various diagrams files where user changes name
                # of package. Implement at some point - just thinking of this
                # given recent failures.

                # Check for individual types if/elif/else

                # TeX: If dvi file is present we ask for TeX source
                #   Do we need to do this is TeX was also included???????
                if file_type == 'dvi':
                    msg = file_name + ' is a TeX-produced DVI file. ' \
                          + ' Please submit the TeX source instead.'
                    _errors.append(msg)

                # Clean up any html
                elif file_type == 'html':
                    pass

                # Postscript - must check and clean up postscript
                #   unmacify, check_ps, ???
                elif file_type == 'postscript' \
                        or (file_type == 'failed' \
                            and re.search(r'\.e?psi?$', file_name, re.IGNORECASE)):
                    pass

                # TeX: Check form of source for latex and latex2e
                elif file_type == 'latex' or file_type == 'latex2e':
                    pass

                # TeX: Check for image types that are not accepted
                elif file_type == 'image' \
                        and re.search(r'\.(pcx|bmp|wmf|opj|pct|tiff?)$',
                                      file_name, re.IGNORECASE):
                    pass

                # Uuencode file: decode uuencoded file
                elif file_type == 'uuencoded':
                    pass

                # File types we don't accept

                # RAR
                elif file_type == 'rar':
                    msg = "We do not support 'rar' files. Please use 'zip' or 'tar'."
                    _errors.append(msg)

                # unmacify files of type PC and MAC
                elif file_type == 'pc' or file_type == 'mac':
                    pass

                # Repair files of type PS_PC
                elif file_type == 'ps_pc':
                    # TODO: Implenent repair_ps
                    pass

                # Repair dos eps
                elif file_type == 'dos_eps':
                    # TODO: Implement repair_dos_eps
                    pass

                # TeX: If file is identified as core TeX type then we need to
                # unmacify
                # check if file contains raw postscript
                elif obj.is_tex_type:
                    # TODO: Implement unmacify
                    print(f'File {obj.name} is TeX type. Needs further inspection. ***')
                    self.unmacify(file_name)
                    self.extract_uu(file_name, file_type)
                    pass

                obj = _add_file(file_path, _warnings, _errors)
                # End of file type checks

    def unmacify(self, file_name: str):
        """Fix up carriage returns and newlines."""
        self.log(f'Unmacify file {file_name}')
        self.log(f"I'm sorry Dave I'm afraid I can't do that. unmacify not implemented YET.")

    def extract_uu(self, file_name: str, file_type: str):
        """Extract uuencode content from file."""
        self.log(f'Looking for uu attachment in {file_name} of type {file_type}')
        self.log(f"I'm sorry Dave I'm afraid I can't do that. uu extract not implemented YET.")

    @property
    def total_upload_size(self) -> int:
        """
        Total size of client's uploaded content. This only refers to client
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

    def calculate_client_upload_size(self):
        """
        Calculate total size of client's upload workspace source files.


        Returns
        -------

        """

        # Calculate total upload workspace source directory size.
        source_directory = self.get_source_directory()

        total_upload_size = 0

        list = []
        for root_directory, directories, files in os.walk(source_directory):
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
        """Create list of File objects with details of each file in
        upload package."""
        # TODO: implement create file list

        # TODO: Cleanup and test.
        # Make sure file list creation is working in check files before enabling.
        #
        # Not ready to enable.
        # Note: check files adds all files in upload archive. If this
        # routine is called elsewhere or (later) without processing upload the
        # list will not contain the files that have been removed.

        # Need to think about this a little since I'd like the UI
        # receive a list of ALL files including those which are
        # removed or rejected (but only for upload files action).

        source_directory = self.get_source_directory()

        list = []
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
                list.append(obj)  # silence lint error

                # Create log entry containing file, type, dir
                log_msg = f'{obj.name} \t[{obj.type}] in {obj.dir}'
                self.log(log_msg)

        return list

    def create_file_upload_summary(self) -> list:
        """Returns a list files with details [dict]. Maybe be generated when upload
        is processed or when run against existing upload directory.

        Return list of files created during upload processing or from list of
        files in directory.

        Generates a list of files in the upload source directory.

        Note: The detailed of regenerating the file list is still being worked out since
              the list generated during processing upload (includes removed files) may be
              different than the list generated against an existing source directory.

        """

        file_list = []

        if self.has_files():

            # TODO: Do we want count in response? Don't really need it but would
            # TODO: need to process list of files.
            # count = len(uploadObj.get_files())

            for fileObj in self.get_files():

                # print("\tFile:" + fileObj.name + "\tFilePath: " + fileObj.public_filepath
                #      + "\tRemoved: " + str(fileObj.removed) + " Size: " + str(fileObj.size))

                # Collect details we would like to return to client
                file_details = {}
                file_details = {
                    'name': fileObj.name,
                    'public_filepath': fileObj.public_filepath,
                    'size': fileObj.size,
                    'type': fileObj.type_string,
                    'modified_datetime': fileObj.modified_datetime
                }

                if not fileObj.removed:
                    file_list.append(file_details)

            return file_list
        return file_list

    def set_file_permissions(self) -> None:
        """Set the file permissions for all files and directories in upload."""

        # Start at directory containing source files
        source_directory = self.get_source_directory()

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

        Intended for case where submitter creates archive with submission
        files in subdirectory.
        """
        source_directory = self.get_source_directory()

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
            save_filename = os.path.join(self.get_removed_directory(),
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
                self.add_error('Failed to remove top level directory.')

            # Set permissions
            self.set_file_permissions()

            # Rebuild file list
            self.create_file_list()

    def finalize_upload(self):
        """For file type checks that cannot be done until all files
        are uploaded, including total submission size.

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

        # Upload_id and filename exists
        # Move this to log
        # print("\n---> Upload id: " + str(self.upload_id) + " FilenamePath: " + file.filename
        #      + " FilenameBase: " + os.path.basename(file.filename)
        #      + " Mime: " + file.mimetype + '\n')

        self.log('\n********** File Upload ************\n\n')

        # Move uploaded archive/file to source directory
        self.deposit_upload(file, ancillary=ancillary)

        self.log('\n******** File Upload Processing *****\n\n')

        # Unpack upload archive (if necessary). Completes minor cleanup.
        unpack_archive(self)

        # Build list of files
        self.create_file_list()

        # Check files
        self.check_files()

        # Check total file size
        self.calculate_client_upload_size()

        # Final cleanup
        self.finalize_upload()

        self.log('\n******** File Upload Finished *****\n\n')

        self.log(f'\n******** Errors: {self.has_errors()} *****\n\n')

    # Content

    def get_content_path(self) -> str:
        """
        Get the path for the packed content tarball.

        Note that the tarball itself may or may not exist yet.
        """
        return os.path.join(self.get_upload_directory(),
                            f'{self.upload_id}.tar.gz')

    def get_content_file_path(self, public_file_path: str) -> str:
        """
        Return the absolute path of content file given relative pointer.

        Returns
        -------
        Null if file does not exist.
        """
        return self.resolve_public_file_path(public_file_path)

    def pack_content(self) -> str:
        """Pack the entire source directory into a tarball."""
        with tarfile.open(self.get_content_path(), "w:gz") as tar:
            tar.add(self.get_source_directory(), arcname=os.path.sep)
        return self.get_content_path()

    @property
    def last_modified(self):
        """The time of the most recent change to a file in the workspace."""
        most_recent = max(os.path.getmtime(root)
                          for root, _, _
                          in os.walk(self.get_source_directory()))
        return datetime.fromtimestamp(most_recent, tz=UTC)

    def get_content(self) -> io.BytesIO:
        """Get a file-pointer for the packed content tarball."""
        if not os.path.exists(self.get_content_path()):
            self.pack_content()
        return open(self.get_content_path(), 'rb')

    @property
    def content_package_exists(self) -> bool:
        return os.path.exists(self.get_content_path())

    @property
    def content_package_modified(self) -> datetime:
        return datetime.fromtimestamp(
            os.path.getmtime(self.get_content_path()),
            tz=UTC
        )

    @property
    def content_package_stale(self) -> bool:
        return self.last_modified > self.content_package_modified

    def content_checksum(self) -> str:
        """Return b64-encoded MD5 hash of the packed content tarball.

        Triggers building content package when pre-existing package is not found or stale
        relative to source files."""
        if not self.content_package_exists or self.content_package_stale:
            self.pack_content()

        hash_md5 = md5()
        with open(self.get_content_path(), "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return b64encode(hash_md5.digest()).decode('utf-8')

    @classmethod
    def checksum(cls, filepath: str):
        """
        Generic routine to calculate checksum for arbitrary file argument.

        Parameters
        ----------
        filepath: str
            Path to file we want to generate checksum for.

        Returns
        -------
        Returns Null string if file does not exist otherwise
        return b64-encoded MD5 hash of the specified file.

        """
        if os.path.exists(filepath):
            hash_md5 = md5()
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return b64encode(hash_md5.digest()).decode('utf-8')
        else:
            return ""

    @classmethod
    def get_open_file_pointer(cls, filepath: str):
        """
        Open specified file and return file pointer.

        Parameters
        ----------
        filepath : str

        Returns
        -------
        File pointer or Null string when filepath does not exist.

        """
        if os.path.exists(filepath):
            return open(filepath, 'rb')
        else:
            return ""

    @classmethod
    def last_modified_file(cls, filepath: str) -> datetime:
        """
        Return last modified time for specified file/package.
        Parameters
        ----------
        filepath

        Returns
        -------

        """
        return datetime.utcfromtimestamp(os.path.getmtime(filepath))
