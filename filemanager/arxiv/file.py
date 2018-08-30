"""Encapsulate file-related methods necessary to complete checks on
   uploaded files. Pulls in analyzed type information and makes it easier
   to keep track of decisions as we analyze files."""

import os.path
import re
from datetime import datetime

from arxiv.base import logging

from filemanager.arxiv.file_type import guess, _is_tex_type, name

logger = logging.getLogger(__name__)


class File:
    """
    Represents a single file in an upload workspace.

    This is file object that contains uploaded file related information,
    including the file type, human readable type name, and the directory
    to be displayed to the submitter.
    """

    def __init__(self, filepath: str, base_dir: str) -> None:
        self.__filepath = filepath
        self.__base_dir = base_dir
        self.__description = ''
        self.__removed = 0
        self.__type = self.initialize_type()
        self.__size = os.path.getsize(self.filepath)
        mtime = os.path.getmtime(filepath)
        self.__modified_datetime = datetime.utcfromtimestamp(mtime)

    @property
    def name(self) -> str:
        """The file name without path/directory info."""
        return os.path.basename(self.filepath)

    @property
    def ext(self) -> str:
        """Return file extension."""
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
        """
        Subdirectory in the :prop:`base_dir` which contains file.

        Does not include preceding / but does end in /.
        """
        pdir = os.path.dirname(self.filepath)
        if pdir == self.__base_dir:
            return ''
        elif self.dir:
            return pdir.replace(self.base_dir + '/', "")
        else:
            # For directories self.dir is empty, must get rest of path from
            # filepath
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

    def initialize_type(self):
        if self.dir:
            """Guess file type."""
            self.__type = guess(self.__filepath)
            return self.__type
        elif self.dir == '' and self.filepath == os.path.join(self.base_dir, 'anc'):
            return 'directory'
        else:
            return 'directory'

    @property
    def type(self) -> str:
        """The file type."""
        if self.__type:
            """Use existing type setting."""
            return self.__type
        else:
            self.initialize_type()

    @type.setter
    def type(self, type: str) -> None:
        """Set the type manually."""
        self.__type = type

    @property
    def type_string(self) -> str:
        """The human readable type name."""
        if self.removed:
            return "Invalid File"
        elif self.dir:
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
        return self.__size

    @property
    def modified_datetime(self) -> str:
        """Return modified datetime of file entity."""
        # Doing this at call time, since the modified time may change after
        # the File is instantiated.
        logger.debug('Get modified_datetime')
        if os.path.exists(self.filepath):
            mt = os.path.getmtime(self.filepath)
            self.__modified_datetime = datetime.utcfromtimestamp(mt)
        return self.__modified_datetime.isoformat()

    @property
    def removed(self) -> int:
        """Indicate whether file has been flagged as removed."""
        return self.__removed

    def remove(self, reason: str) -> None:
        """Set file status to removed."""
        if not reason:
            reason = "Removed"
        self.__removed = reason

# TODO Need to handle special Ancillary Files

# TODO Need to implement sha256sum routine
