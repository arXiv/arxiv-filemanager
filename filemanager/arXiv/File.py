"""Encapsulate file-related methods necessary to complete checks on
   uploaded files. Pulls in analyzed type information and makes it easier
   to keep track of decisions as we analyze files."""

import os.path
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

    @property
    def name(self) -> str:
        """The file name without path/directory info"""
        return os.path.basename(self.filepath)

    @property
    def ext(self):
        """Return file extension"""
        fbase, ext = os.path.splitext(self.__filepath)
        return ext

    @property
    def dir(self) -> str:
        """Directory which contains the file. This is only used for files."""
        return os.path.dirname(self.filepath)

    @property
    def base_dir(self) -> str:
        """Directory containing all source files."""
        return self.__base_dir

    @base_dir.setter
    def base_dir(self, base: str) -> str:
        """Directory containing all source files."""
        self.__base_dir = base

    @property
    def public_dir(self) -> str:
        """Subdirectory in the base_dir which contains file.
        Does not include preceding / but does end in /."""
        pdir = os.path.dirname(self.filepath)
        if pdir == self.__base_dir:
            return ''
        else:
            return pdir.replace(self.base_dir + '/',"")

    @property
    def filepath(self) -> str:
        """The file name WITH complete path/directory in filesystem."""
        return self.__filepath

    @filepath.setter
    def filepath(self, path: str) -> str:
        """The file name WITH complete path/directory in filesystem."""
        self.__filepath = path

    @property
    def public_filepath(self) -> str:
        """Public directory and filename."""
        ppath = self.filepath
        return ppath.replace(self.base_dir + '/',"")

    @property
    def type(self) -> str:
        """The file type."""
        return guess(self.__filepath)

    @property
    def type_string(self) -> str:
        """The human readable type name."""
        return name(self.type)

    @property
    def sha256sum(self) -> str:
        return 'NOT IMPLEMENTED YET'

    @property
    def description(self, description='') -> str:
        """Description of file. (Optional)"""
        return self.__description

    @description.setter
    def description(self, description='') -> str:
        """Description of file. (Optional)"""
        if description != '':
            self.__description = description

    @property
    def is_tex_type(self) -> bool:
        """Is this file a TeX file"""
        return _is_tex_type(self.type)

    @property
    def size(self) -> int:
        return os.path.getsize(self.filepath)

    @property
    def removed(self):
        return self.__removed


    def remove(self):
        self.__removed = 1

# TODO Need to handle special Ancillary Files

# TODO Need to implement sha256sum routine
