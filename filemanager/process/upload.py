"""Provides functions that sanitizes :class:`.Upload."""

import os
import os.path
import re
import shutil
import tarfile
import logging

from werkzeug.exceptions import BadRequest, NotFound, SecurityError
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from filemanager.arxiv.file import File

UPLOAD_FILE_EMPTY = {'file payload is zero length'}
UPLOAD_DELETE_FILE_FAILED = {'unable to delete file'}
UPLOAD_DELETE_ALL_FILE_FAILED = {'unable to delete all file'}
UPLOAD_FILE_NOT_FOUND = {'file not found'}
UPLOAD_WORKSPACE_NOT_FOUND = {'workspcae not found'}

# TODO: Need to move to config file
UPLOAD_BASE_DIRECTORY = '/tmp/filemanagment/submissions'


class Upload:
    """Handle uploaded files: unzipping, putting in the right place, doing
various file checks that might cause errors to be displayed to the
submitter."""

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
        self.__log = ''
        self.create_upload_workspace()
        self.create_upload_log()

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
        #self.__warnings.append(msg)
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
        file : File
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

        if not os.path.exists(workspace_directory):
            raise NotFound(UPLOAD_WORKSPACE_NOT_FOUND)

        # Let's stash a copy of the source.log file (if it exists)
        log_path = os.path.join(self.get_upload_directory(), 'source.log')

        if os.path.exists(log_path):
            # Does directory exist to stash log
            deleted_workspace_logs = os.path.join(UPLOAD_BASE_DIRECTORY,
                                                  'deleted_workspace_logs')
            if not os.path.exists(deleted_workspace_logs):
                # Create the directory for deleted workspace logs
                os.makedirs(deleted_workspace_logs, 0o755)

            # Since every source log has the same filename we will prefix
            # upload identifier to log.

            new_filename = str(self.__upload_id) + "_source.log"
            deleted_log_path = os.path.join(deleted_workspace_logs, new_filename)
            self.log(f"Move '{log_path} to '{deleted_log_path}'.")
            if not shutil.move(log_path, deleted_log_path):
                self.log('Saving source.log failed.')
                return False

        # Now blow away the workspace

        return True



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

        # Resolve reletive path of file to filesystem
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
                # lmsg = "*** File " + file.name + f" has been removed. Reason: {msg} ***"
                #lmsg = f"Removed hidden file {file.name}."
                #self.add_warning(file.public_filepath, lmsg)
                self.log(f"Moved file from {file_path} to {removed_path}")
                return True
            else:
                self.log(f"*** FAILED to remove file '{file_path}'/{clean_public_path} ***")
                return False
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


    def get_upload_directory(self) -> str:
        """
        Get top level workspace directory for submission."

        Returns
        -------
        str
            Top level directory path for upload workspace.
        """

        root_path = UPLOAD_BASE_DIRECTORY
        upload_directory = os.path.join(root_path, str(self.upload_id))
        return upload_directory

    def create_upload_directory(self):
        """Create the base directory for upload workarea"""

        root_path = UPLOAD_BASE_DIRECTORY

        if not os.path.exists(root_path):
            # Create path for submissions
            # TODO determine if we need to set owner/modes
            os.makedirs(UPLOAD_BASE_DIRECTORY, 0o755)
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

        base = self.get_upload_directory()
        src_dir = os.path.join(base, 'src')
        return src_dir

    def get_removed_directory(self) -> str:
        """Return directory where source archive files get moved after unpacking."""
        base = self.get_upload_directory()
        rem_dir = os.path.join(base, 'removed')
        return rem_dir

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

    def create_upload_log(self):
        """Create a source log to record activity for this upload."""

        # Grab standard logger and customized it
        logger = logging.getLogger(__name__)
        log_path = os.path.join(self.get_upload_directory(), 'source.log')
        file_handler = logging.FileHandler(log_path)

        formatter = logging.Formatter('%(asctime)s %(message)s', '%d/%b/%Y:%H:%M:%S %z')
        file_handler.setFormatter(formatter)
        logger.handlers = []
        logger.addHandler(file_handler)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False

        self.__log = logger

    def log(self, message: str):
        """Write message to upload log"""
        self.__log.info(message)

    def deposit_upload(self, file: FileStorage) -> str:
        """
        Deposit uploaded archive/file into workspace source directory.

        Parameters
        ----------
        file
            Archive containing one or more files to be added to source files
            for this upload.

        Returns
        -------
        str
            Full path of archive file.

        """

        basename = os.path.basename(file.filename)

        # Sanitize file name before saving it
        filename = secure_filename(basename)

        if basename != filename:
            self.log(f'Secured filename: {filename} (basename + )')

        # Store uploaded file/archive in source directory
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

        for root_directory, directories, files in os.walk(source_directory):
            for directory in directories:
                # Need to decide whether we need to do anything to directories
                # in the meantime get rid of lint warning
                path = os.path.join(root_directory, directory)
                obj = File(path, source_directory)
                # self.log(f'{directory} [{obj.type}] in {obj.filepath}')

            for file in files:
                path = os.path.join(root_directory, file)
                obj = File(path, source_directory)
                # Add all files to upload file list as this will hold
                # information about handling of file (removed)
                self.add_file(obj)

                # Convert this to debugging
                # print("  File is : " + file + " Size: " + str(
                #    obj.size) + " File is type: " + obj.type + ":" + obj.type_string + '\n')

                file_type = obj.type
                file_name = obj.name
                file_path = os.path.join(root_directory, file)
                file_size = obj.size

                # Update file timestamps

                # Remove zero length files
                if obj.size == 0:
                    msg = obj.name + " is empty (size is zero)"
                    self.add_warning(obj.public_filepath, msg)
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
                    self.add_warning(obj.public_filepath, msg)
                    os.rename(file_path, new_file_path)
                    # fix up local data
                    file_name = new_name
                    file_path = new_file_path

                # Keep an eye out for special ancillary 'anc' directory
                anc_dir = os.path.join(self.get_source_directory(), 'anc')
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
                    self.add_warning(obj.public_filepath, "We only accept file names containing the characters: "
                                     + "a-z A-Z 0-9 _ + - . , =")
                    self.add_warning(obj.public_filepath, 'Attempting to rename ' + file_name
                                     + ' to ' + new_file_name + '.')
                    # Do the renaming
                    new_file_path = os.path.join(root_directory, new_file_name)
                    try:
                        os.rename(file_path, new_file_path)
                    except os.error:
                        self.add_warning(obj.public_filepath, 'Unable to rename ' + file_name)

                    # fix up local data
                    file_name = new_file_name
                    file_path = new_file_path

                # Filename starts with hyphen
                if file_name.startswith('-'):
                    # Replace dash (-) with underscore
                    new_file_name = re.sub('^-', '_', file_name)
                    self.add_warning(obj.public_filepath, 'We do not accept files starting with a hyphen. '
                                     + 'Attempting to rename \"' + file_name + '\" to \"'
                                     + new_file_name + '\".')
                    # Do the renaming
                    new_file_path = os.path.join(root_directory, new_file_name)
                    try:
                        os.rename(file_path, new_file_path)
                    except os.error:
                        self.add_warning(obj.public_filepath, 'Unable to rename ' + file_name)
                    # fix up local data
                    file_name = new_file_name
                    file_path = new_file_path

                # Filename starts with dot (.)
                if file_name.startswith('.'):
                    # Remove files starting with dot
                    msg = 'Removed hidden file'
                    # self.add_warning(msg)
                    self.remove_file(obj, msg)

                    continue

                # Following checks can only occur once in current file
                # all are tied together with if / elif

                # TeX: Remove hyperlink styles espcrc2 and lamuphys
                if re.search(r'^(espcrc2|lamuphys)\.sty$', file_name):
                    # TeX: styles that conflict with internal hypertex package
                    print("Found hyperlink-compatible package\n")
                    # TODO: Check the error/warning messaging for this check.
                    self.remove_file(obj, msg)
                    self.add_warning(obj.public_filepath, '    -- instead using hypertex-compatible local version')
                elif re.search(r'^(espcrc2|lamuphys)\.tex$', file_name):
                    # TeX: source files that conflict with internal hypertex package
                    # I'm not sure why this is just a warning
                    self.add_warning(obj.public_filepath, f"Possible submitter error. Unwanted '{file_name}'")
                elif file_name == 'uufiles' or file_name == 'core' or file_name == 'splread.1st':
                    # Remove these files
                    msg = 'File not allowed.'
                    self.remove_file(obj, msg)
                elif re.search(r'^xxx\.(rsrc$|finfo$|cshrc$|nfs)', file_name) \
                        or re.search(r'\.[346]00gf$', file_name) \
                        or (re.search(r'\.desc$', file_name) and file_size < 10):
                    # Remove these files
                    msg = 'File not allowed.'
                    self.remove_file(obj, msg)
                elif re.search(r'(.*)\.bib$', file_name, re.IGNORECASE):
                    # TeX: Remove bib file since we do not run BibTeX
                    # TODO: Generate bib warning bib()??
                    msg = 'Removing ' + file_name \
                          + ". Please upload .bbl file instead."
                    self.remove_file(obj, msg)
                elif re.search(r'^(10pt\.rtx|11pt\.rtx|12pt\.rtx|aps\.rtx|'
                               + r'revsymb\.sty|revtex4\.cls|rmp\.rtx)$',
                               file_name):
                    # TeX: submitter is including file already included
                    # in TeX Live release
                    # TODO: get revtex() warning message ???
                    self.remove_file(obj, msg)
                elif re.search(r'^diagrams\.(sty|tex)$', file_name):
                    # TeX: diagrams package contains a time bomb and stops
                    # working after a specified date. Use internal version
                    # with time bomb disable.

                    # TODO: get diagrams warning
                    msg = ''
                    self.remove_file(obj, msg)
                elif file_name == 'aa.dem':
                    # TeX: Check for aa.dem
                    # This is demo file that authors seem to include with
                    # their submissions.
                    self.remove_file(obj, msg)
                    self.add_warning(obj.public_filepath, 'REMOVING ' + file_name
                                     + ' on the assumption that it is the example '
                                     + 'file for the Astronomy and '
                                     + 'Astrophysics macro package aa.cls.')
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
                        # Potential conflict / corruption by including TeX
                        # generated files in submission
                        self.add_warning(obj.public_filepath, ' REMOVING $fn due to name conflict')
                        self.remove_file(obj, msg)
                elif re.search(r'[^\w\+\-\.\=\,]', file_name):
                    # File name contains unwanted bad characters - this is an Error
                    # We attempted to fix file_names with bad characters at
                    # beginning of this routine
                    self.add_error(obj.public_filepath, 'Filename \"' + file_name
                                   + '\" contains unwanted bad character \"$&\", '
                                   + 'only allowed are a-z A-Z 0-9 _ + - . , =')
                elif re.search(r'([\.\-]t?[ga]?z)$', file_name):
                    # Fix filename
                    new_file_name = re.sub(r'([\.\-]t?[ga]?z)$', '', file_name,
                                           re.IGNORECASE)
                    new_file_path = os.path.join(root_directory, new_file_name)
                    try:
                        os.rename(file_path, new_file_path)
                        msg = "Renaming '" + file_name + "' to '" \
                              + new_file_name + "'."
                        self.add_warning(obj.public_filepath, msg)
                    except os.error:
                        self.add_warning(obj.public_filepath, 'Unable to rename ' + file_name)
                elif file_name.endswith('.doc') and type == 'failed':
                    # Doc warning
                    # TODO: Get doc warning from message class
                    msg = ''
                    # TODO: need to log error
                    self.add_error(obj.public_filepath, msg)
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
                    self.add_error(obj.public_filepath, msg)

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
                    self.add_error(obj.public_filepath, msg)

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

                # End of file type checks

    def unmacify(self, file_name: str):
        """Fix up carriage returns and newlines."""
        self.log(f'Unmacify file {file_name}')
        self.log(f"I'm sorry Dave I'm afraid I can't do that. unmacify not implemented YET.")

    def extract_uu(self, file_name: str, file_type: str):
        """Extract uuencode content from file."""
        self.log(f'Looking for uu attachment in {file_name} of type {file_type}')
        self.log(f"I'm sorry Dave I'm afraid I can't do that. uu extract not implemented YET.")

    def check_size(self):
        """Check the uploaded files against individual and aggregate size limitations."""
        self.log('Coming soon! Check total file size is not implemented yet!')

    def create_file_list(self) -> None:
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

                # self.add_file(obj)

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
                }
                #if fileObj.removed:
                #    file_details['removed'] = fileObj.removed

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

    def fix_top_level_directory(self):
        """
        Eliminate single top-level directory. Intended for case where submitter
        creates archive with submission files in subdirectory.

        Returns
        -------

        """

        source_directory = self.get_source_directory()

        entries = os.listdir(source_directory)

        if len(entries) == 1:

            if os.path.isdir(os.path.join(source_directory, entries[0])):

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

    def process_upload(self, file: FileStorage) -> None:
        """
        Main entry point for processing uploaded files.

        Parameters
        ----------
        file
            File object received from flask request.

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
        self.deposit_upload(file)

        self.log('\n******** File Upload Processing *****\n\n')

        from filemanager.utilities.unpack import unpack_archive
        # Unpack upload archive (if necessary). Completes minor cleanup.
        unpack_archive(self)

        # Build list of files
        self.create_file_list()

        # Check files
        self.check_files()

        # Check total file size
        self.check_size()

        # Final cleanup
        self.finalize_upload()

        self.log('\n******** File Upload Finished *****\n\n')

        self.log(f'\n******** Errors: {self.has_errors()} *****\n\n')
