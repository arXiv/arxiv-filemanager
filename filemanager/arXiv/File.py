"""Encapsulate file-related methods necessary to complete checks on
   uploaded files. Pulls in analyzed type information and makes it easier
   to keep track of decisions as we analyze files."""

import os.path
import re

from filemanager.arXiv.FileType import guess, _is_tex_type, name


class File:
    """This is file object that contains uploaded file related information,
including the file type, human readable type name, and the directory
to be displayed to the submitter."""

    def __init__(self, filepath: str, base_dir: str) -> None:
        self.__filepath = filepath
        self.__base_dir = base_dir
        self.__description = ''
        self.__removed = 0
        self.__type = ''

    @property
    def name(self) -> str:
        """The file name without path/directory info"""
        return os.path.basename(self.filepath)

    @property
    def ext(self) -> str:
        """Return file extension"""
        fbase, ext = os.path.splitext(self.__filepath)
        return ext

    @property
    def dir(self) -> str:
        """Directory which contains the file. This is only used for files."""
        if os.path.isfile(self.filepath):
            return os.path.dirname(self.filepath)

        return ''

    @property
    def base_dir(self) -> str:
        """Directory containing all source files."""
        return self.__base_dir

    @base_dir.setter
    def base_dir(self, base: str) -> None:
        """Directory containing all source files."""
        self.__base_dir = base

    @property
    def public_dir(self) -> str:
        """Subdirectory in the base_dir which contains file.
        Does not include preceding / but does end in /."""
        pdir = os.path.dirname(self.filepath)
        if pdir == self.__base_dir:
            return ''
        elif self.dir:
            return pdir.replace(self.base_dir + '/', "")
        else:
            # For directories self.dir is empty, must get rest of path from filepath
            public_dir = pdir.replace(self.base_dir + '/', "")
            name = re.sub(r'[\+]/\\\+', '', self.name)
            regex = name + '$'
            public_dir = re.sub(regex, '', public_dir)
            return public_dir

    @property
    def filepath(self) -> str:
        """The file name WITH complete path/directory in filesystem."""
        return self.__filepath

    @filepath.setter
    def filepath(self, path: str) -> None:
        """The file name WITH complete path/directory in filesystem."""
        self.__filepath = path

    @property
    def public_filepath(self) -> str:
        """Public directory and filename."""
        ppath = self.filepath
        return ppath.replace(self.base_dir + '/', "")

    @property
    def type(self) -> str:
        """The file type."""
        if self.__type:
            """Use existing type setting."""
            return self.__type
        elif self.dir:
            """Guess file type."""
            self.__type = guess(self.__filepath)
            return self.__type
        elif self.dir == '' and self.filepath == os.path.join(self.base_dir, 'anc'):
            return 'directory'
        else:
            return 'directory'

    @type.setter
    def type(self, type: str) -> None:
        """Set the type manually."""
        self.__type = type

    @property
    def type_string(self) -> str:
        """The human readable type name."""
        if self.dir:
            return name(self.type)
        elif self.dir == '' and self.filepath == os.path.join(self.base_dir, 'anc'):
            return 'Ancillary files directory'
        else:
            return 'Directory'

    @property
    def sha256sum(self) -> str:
        """Calculate sha256 Checksum."""
        return 'NOT IMPLEMENTED YET'

    @property
    def description(self) -> str:
        """Description of file. (Optional)"""
        return self.__description

    @description.setter
    def description(self, description: str = '') -> None:
        """Description of file. (Optional)"""
        if description != '':
            self.__description = description

    @property
    def is_tex_type(self) -> bool:
        """Is this file a TeX file"""
        return _is_tex_type(self.type)

    @property
    def size(self) -> int:
        """Return size of file entity."""
        return os.path.getsize(self.filepath)

    @property
    def removed(self) -> int:
        """Indicate whether file has been flagged as removed."""
        return self.__removed

    def remove(self) -> None:
        """Set file status to removed."""
        self.__removed = 1

# TODO Need to handle special Ancillary Files

# TODO Need to implement sha256sum routine
