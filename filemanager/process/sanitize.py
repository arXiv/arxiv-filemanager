"""Provides functions that sanitizes :class:`.Upload."""

import os
import os.path
import re
import shutil
import tarfile

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from filemanager.arXiv.File import File

# TODO MOVE TO CONFIG FILE
from filemanager.utilities.upload_size import check_upload_file_size_limit

UPLOAD_BASE_DIRECTORY = '/tmp/a/b/submissions'


class Upload:
    """Handle uploaded files: unzipping, putting in the right place, doing
various file checks that might cause errors to be displayed to the
submitter."""

    def __init__(self, upload_id: int):
        self.__upload_id = upload_id

        self.__warnings = []
        self.__errors = []

    def add_warning(self, msg: str) -> None:
        print('Warning: ' + msg)
        self.__warnings.append(msg)

    def has_warnings(self):
        return len(self.__warnings)

    def search_warnings(self, search:str) -> bool:
        #if search in self.__warnings:
        for warning in self.__warnings:
            # Turn this into debugging
            #print("Look for '" + search + '\' in \n\t \'' + warning +"'")
            #print("ret: " + str(re.search(search, warning)))

            if re.match(search, warning):
                #print("Found Match!")
                return True
        return False

    def add_error(self, msg: str) -> None:
        print('Error: ' + msg)
        self.__errors.append(msg)



    @property
    def upload_id(self) -> int:
        return self.__upload_id

    def remove_file(self, file: File, msg: str) -> bool:
        # Move file to removed directory
        filepath = file.filepath
        removed_path = os.path.join(self.get_removed_directory(), file.name)
        print("Move file " + file.name + " to removed dir: " + removed_path)
        if shutil.move(filepath, removed_path):
            self.add_warning("*** File " + file.name + " has been removed ***")
        else:
            self.add_warning("*** FAILED to remove file " + filepath + " ***")
        file.remove()



    def get_upload_directory(self) -> str:
        """Get top level workspace directory for submission."""
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
            print("Created file management service workarea\n");

        upload_directory = self.get_upload_directory()

        if not os.path.exists(upload_directory):
            # Create path for submissions
            # TODO determine if we need to set owner/modes
            os.makedirs(upload_directory, 0o755)
            # print("Created upload workarea\n");

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

    def deposit_upload(self, file: FileStorage) -> str:
        """Deposit upload archive/file into workspace source directory."""

        basename = os.path.basename(file.filename)

        # Sanitize file name before saving it
        filename = secure_filename(basename)
        if basename != filename:
            self.add_warning("Cleaned filename: " + filename + '(' + basename + ')')

        # TODO Do we need to do anything else to filename?
        src_directory = self.get_source_directory()
        upload_path = os.path.join(src_directory, filename)
        file.save(upload_path)
        return upload_path



    def check_files(self) -> None:
        """This is the main loop that goes through the list of files and does a long
        list of checks that depend on file type, extension, and sometimes file name."""

        source_directory = self.get_source_directory()

        for a, b, c in os.walk(source_directory):
            for file in c:
                path = os.path.join(a, file)
                obj = File(path, source_directory)

                # Convert this to debugging
                #print("  File is : " + file + " Size: " + str(
                #   obj.size) + " File is type: " + obj.type + ":" + obj.type_string + '\n')

                file_type = obj.type
                file_name = obj.name
                file_dir = obj.dir
                file_path = os.path.join(a, file)
                file_size = obj.size

                # Update file timestamps

                # Remove zero length files
                if obj.size == 0:
                    msg = obj.name + " is empty (size is zero)"
                    self.add_warning(msg)
                    self.remove_file(obj, msg)
                    continue

                # Remove 10240 byte all-null files (bad user tar attempts?)
                # Check of file is 10240 bytes and all are zero


                # Rename Windows file names
                if re.search(r'^[A-Za-z]:\\', file_name):
                    # Rename using basename
                    new_name = re.sub (r'^[A-Za-z]:\\(.*\\)?', '', file_name)
                    new_file_path = os.path.join(a, new_name)
                    msg = 'Renaming ' + file_name + ' to ' + new_name + '.'
                    self.add_warning(msg)
                    os.rename (file_path, new_file_path)
                    # fix up local data
                    file_name = new_name
                    file_path = new_file_path

                # Keep an eye out for special ancillary 'anc' directory
                anc_dir = os.path.join(self.get_source_directory(), 'anc')
                if file_path.startswith(anc_dir):
                    statinfo = os.stat(file_path)
                    kilos = statinfo.st_size
                    warn = "Ancillary file " + file_name + " (" + str(kilos) + ')'
                    self.add_warning(warn)
                    obj.type = 'ancillary'
                    # We are done at this point - we do not inspect ancillary files
                    continue

                # Basic file checks

                # Attempt to rename filenames containing illegal characters

                # Filename contains illegal characters+,-,/,=,
                if re.search('[^\w\+\-\.\=\,]', file_name):
                    # Translate bad characters
                    new_file_name = re.sub('[^\w\+\-\.\=\,]', '_', file_name)
                    self.add_warning("We only accept file names containing the characters: "
                                   + "a-z A-Z 0-9 _ + - . , =")
                    self.add_warning('Attempting to rename ' + file_name + ' to '+ new_file_name +'.')
                    # Do the renaming
                    new_file_path = os.path.join(a, new_file_name)
                    try:
                        os.rename(file_path, new_file_path)
                    except os.error:
                        self.add_warning('Unable to rename ' + file_name)

                    # fix up local data
                    file_name = new_file_name
                    file_path = new_file_path


                # Filename starts with hyphen
                if file_name.startswith('-'):
                    # Replace dash (-) with underscore
                    new_file_name = re.sub('^-', '_', file_name)
                    self.add_warning('We do not accept files starting with a hyphen. '
                                   + 'Attempting to rename \"'+ file_name + '\" to \"'
                                   + new_file_name + '\".')
                    # Do the renaming
                    new_file_path = os.path.join(a, new_file_name)
                    try:
                        os.rename(file_path, new_file_path)
                    except os.error:
                        self.add_warning('Unable to rename ' + file_name)
                    # fix up local data
                    file_name = new_file_name
                    file_path = new_file_path

                # Filename starts with dot (.)
                if file_name.startswith('\.'):
                    # Remove files starting with dot
                    msg = 'Removed hidden file ' + file_name
                    self.add_warning(msg)
                    self.remove_file(obj, msg)
                    continue


                # Following checks can only occur once in current file
                # all are tied together with if / elif

                # TeX: Remove hyperlink styles espcrc2 and lamuphys
                if re.search('^(espcrc2|lamuphys)\.sty$', file_name):
                    # TeX: styles that conflict with internal hypertex package
                    print("Found hyperlink-compatible package\n")
                    self.remove_file(obj, msg)
                    self.add_warning('    -- instead using hypertex-compatible local version')
                elif re.search('^(espcrc2|lamuphys)\.tex$', file_name):
                    # TeX: source files that conflict with internal hypertex package
                    # I'm not sure why this is just a warning
                    self.add_warning('Possible submitter error. Unwanted ' + file_name)
                elif file_name == 'uufiles' or file_name == 'core' or file_name == 'splread.1st':
                    # Remove these files
                    msg = 'File not allowed.'
                    self.remove_file(obj, msg)
                elif re.search('^xxx\.(rsrc$|finfo$|cshrc$|nfs)', file_name) \
                    or re.search('\.[346]00gf$', file_name) \
                    or (re.search('\.desc$', file_name) and file_size < 10):
                    # Remove these files
                    msg = 'File not allowed.'
                    self.remove_file(obj, msg)
                elif re.search('(.*)\.bib$', file_name, re.IGNORECASE):
                    # TeX: Remove bib file since we do not run BibTeX
                    # TODO: Generate bib warning bib()??
                    msg = 'Removing ' + file_name + ". Please upload .bbl file instead."
                    self.remove_file(obj, msg)
                elif re.search('^(10pt\.rtx|11pt\.rtx|12pt\.rtx|aps\.rtx|revsymb\.sty|revtex4\.cls|rmp\.rtx)$',
                               file_name):
                    # TeX: submitter is including file already included in TeX Live release
                    # TODO: get revtex() warning message ???
                    self.remove_file(obj, msg)
                elif re.search('^diagrams\.(sty|tex)$', file_name):
                    # TeX: diagrams package contains a time bomb and stops working
                    # after a specified date. Use internal version with time bomb disable.

                    # TODO: get diagrams warning
                    msg = ''
                    self.remove_file(obj, msg)
                elif file_name == 'aa.dem':
                    # TeX: Check for aa.dem
                    # This is demo file that authors seem to include with their submissions.
                    self.remove_file(obj, msg)
                    self.add_warning('REMOVING ' + file_name + ' on the assumption that it is the example '
                                     + 'file for the Astronomy and Astrophysics macro package aa.cls.')
                elif re.search('(.+)\.(log|aux|blg|dvi|ps|pdf)$', file_name, re.IGNORECASE):
                    # TeX: Check for TeX processed output files (log, aux, blg, dvi, ps, pdf, etc.)
                    # Detect naming conflict, warn, remove offending files.
                    # Check if certain source files exist
                    filebase, file_extension = os.path.splitext(file_name)
                    tex_file = os.path.join(a, filebase, '.tex')
                    TEX_file = os.path.join(a, filebase, '.TEX')
                    if os.path.exists(tex_file) or os.path.exists(TEX_file):
                        # Potential conflict / corruption by including TeX generated files in submission
                        self.add_warning(' REMOVING $fn due to name conflict')
                        self.remove_file(obj, msg)
                elif re.search('[^\w\+\-\.\=\,]', file_name):
                    # File name contains unwanted bad characters - this is an Error
                    # We attempted to fix file_names with bad characters at beginning of this routine
                    self.add_error('Filename \"' + file_name + '\" contains unwanted bad character \"$&\", '
                                   + 'only allowed are a-z A-Z 0-9 _ + - . , =')
                elif re.search('([\.\-]t?[ga]?z)$', file_name):
                    # Fix filename
                    new_file_name = re.sub(r'([\.\-]t?[ga]?z)$', '', file_name, re.IGNORECASE)
                    new_file_path = os.path.join(a, new_file_name)
                    try:
                        os.rename(file_path, new_file_path)
                        msg = 'Renaming ' + file_name + ' to ' + new_file_name + '.'
                        self.add_warning(msg)
                    except os.error:
                        self.add_warning('Unable to rename ' + file_name)
                elif file_name.endswith('.doc') and type == 'failed':
                    # Doc warning
                    # TODO: Get doc warning from message class
                    msg = ''
                    # TODO: need to log error
                    self.add_error(msg)
                    self.remove_file(obj, msg)

                # Finished basic file checks

                # We are done if file was marked as removed, otherwise continue with
                # additional type checks below
                if obj.removed:
                    print("File was removed -- skipping to next file\n")
                    continue


                # Placeholder for future checks/notes

                # TeX: Files that indicate user error
                # TODO: Investigate missfont.log error - possibly move handling here

                # TODO: diagrams detection script (does not exist in legacy system)
                # TeX: Detect various diagrams files where user changes name of package.
                # Implement at some point - just thinking of this given recent failures.




                # Check for individual types if/elif/else

                # TeX: If dvi file is present we ask for TeX source
                #   Do we need to do this is TeX was also included???????
                if file_type == 'dvi':
                    msg = file_name + ' is a TeX-produced DVI file. Please submit the TeX source instead.'
                    self.add_error(msg)

                # Clean up any html
                elif file_type == 'html':
                    pass

                # Postscript - must check and clean up postscript
                #   unmacify, check_ps, ???
                elif file_type == 'postscript' or (file_type == 'failed'
                                                   and re.search('\.e?psi?$', file_name, re.IGNORECASE)):
                    pass

                # TeX: Check form of source for latex and latex2e
                elif file_type == 'latex' or file_type == 'latex2e':
                    pass

                # TeX: Check for image types that are not accepted
                elif file_type == 'image' and re.search(r'\.(pcx|bmp|wmf|opj|pct|tiff?)$', file_name, re.IGNORECASE):
                    pass

                # Uuencode file: decode uuencoded file
                elif file_type == 'uuencoded':
                    pass

                # File types we don't accept

                # RAR
                elif file_type == 'rar':
                    msg = "We do not support 'rar' files. Please use 'zip' or 'tar'."
                    self.add_error(msg)



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
                    pass

                # End of file type checks

    def create_file_list(self) -> None:
        """Create list of File objects with details of each file in upload package."""

        pass

    def set_file_permissions(self, source_directory: str) -> None:

        # Set permissions on all directories and files
        for root_directory, b, c in os.walk(source_directory):
            for file in c:
                file_path = os.path.join(root_directory, file)
                os.chmod(file_path, 0o664)
            for dir in b:
                dir_path = os.path.join(root_directory, dir)
                os.chmod(dir_path, 0o775)


    def fix_top_level_directory(self):
        """Eliminate single top-level directory."""

        source_directory = self.get_source_directory()

        entries = os.listdir(source_directory)

        if len(entries) == 1:

            if os.path.isdir(os.path.join(source_directory, entries[0])):

                self.add_warning("Removing top level directory");
                single_directory = os.path.join(source_directory, entries[0])

                # Save copy in removed directory
                save_filename = os.path.join(self.get_removed_directory(), 'move_source.tar.gz')
                with tarfile.open(save_filename, "w:gz") as tar:
                    tar.add(single_directory, arcname=os.path.sep)

                # Remove existing directory
                if os.path.exists(single_directory):
                    shutil.rmtree(single_directory)

                # Replace files
                if os.path.exists(save_filename):
                    tar = tarfile.open(save_filename)
                    tar.extractall(path=source_directory)  # untar file into source directory
                    tar.close()
                else:
                    self.add_error('Failed to remove top level directory.')

                # Set permissions
                self.set_file_permissions(source_directory)



    def finalize_upload(self):
        """For file type checks that cannot be done until all files are uploaded,
        including total submission size.

        Build final list of files contained in upload.

        Remove single top level directory.
        """

        # Only do this if we haven't generated list already
        self.create_file_list()

        # Eliminate top directory when only single directory
        self.fix_top_level_directory()


    def process_upload(self, file: FileStorage) -> None:
        """
        Add some ones to the name of a :class:`.Upload`.

        Parameters
        ----------
        upload_id : :int
        filename : str
        :param file:
        :return:
        """

        # Upload_id and filename exists
        # Testing
        print("\n---> Upload id: " + str(self.upload_id) + " FilenamePath: " + file.filename
              + " FilenameBase: " + os.path.basename(file.filename)
              + " Mime: " + file.mimetype + '\n')

        # Make sure upload directory exists or create it
        # Nornally done is seperate step!!!!!!
        dir_path = self.create_upload_workspace()

        ####print("Create upload work area: " + dir_path)

        # Move file to source directory
        path = self.deposit_upload(file)

        from filemanager.utilities.unpack import unpack_archive
        # Unpack upload archive (if necessary)
        unpack_archive(self, path)

        # Check files
        self.check_files()

        self.finalize_upload()


        return ("SUCCEEDED")
