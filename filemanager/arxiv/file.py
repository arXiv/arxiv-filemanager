"""
File support.

Encapsulate file-related methods useful for performing checks on
uploaded files. Relies on type guess routine and makes it easier
to keep track of various decisions as we analyze files (has file
been removed).

"""

import os.path
import re
from datetime import datetime
from hashlib import md5
from base64 import urlsafe_b64encode
from pytz import UTC
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
        self.__removed = ''
        self.__type = self.initialize_type()
        self.__size = os.path.getsize(self.filepath)
        mtime = os.path.getmtime(filepath)
        self.__modified_datetime = datetime.fromtimestamp(mtime, tz=UTC)

    @property
    def name(self) -> str:
        """The file name without path/directory info."""
        return os.path.basename(self.filepath)

    @property
    def ext(self) -> str:
        """Return file extension."""
        # Base filename is not needed
        _, ext = os.path.splitext(self.__filepath)
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
        if self.dir:
            return pdir.replace(self.base_dir + '/', "")

        # For directories self.dir is empty, must get rest of path from
        # filepath
        public_dir = pdir.replace(self.base_dir + '/', "")
        regname = re.sub(r'[\+]/\\\+', '', self.name)
        regex = regname + '$'
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

    def initialize_type(self) -> str:
        """Initialize file type using best-guess routine."""
        if self.dir:
            # Guess file type.
            self.__type = guess(self.__filepath)
            return self.__type
        if self.dir == '' and self.filepath == os.path.join(self.base_dir, 'anc'):
            return 'directory'

        return 'directory'

    @property
    def type(self) -> str:
        """The file type."""
        if self.__type:
            # Use existing type setting.
            return self.__type

        return self.initialize_type()

    @type.setter
    def type(self, type: str) -> None:
        """Set the type manually."""
        self.__type = type

    @property
    def type_string(self) -> str:
        """The human readable type name."""
        if self.removed:
            return "Invalid File"
        if self.dir:
            return name(self.type)
        if self.dir == '' and self.filepath == os.path.join(self.base_dir, 'anc'):
            return 'Ancillary files directory'

        return 'Directory'

    @property
    def sha256sum(self) -> str:
        """Calculate sha256 Checksum."""
        return 'NOT IMPLEMENTED YET'

    @property
    def checksum(self) -> str:
        """
        Calculate MD5 checksum for file.

        Returns
        -------
        Returns Null string if file does not exist otherwise
        return b64-encoded MD5 hash of the specified file.

        """
        if os.path.exists(self.filepath):
            hash_md5 = md5()
            with open(self.filepath, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return urlsafe_b64encode(hash_md5.digest()).decode('utf-8')

        return ""


    @property
    def description(self) -> str:
        """Get description of file. (Optional)."""
        return self.__description

    @description.setter
    def description(self, description: str = '') -> None:
        """Set description of file. (Optional)."""
        if description != '':
            self.__description = description

    @property
    def is_tex_type(self) -> bool:
        """Determine whether this file is a TeX file."""
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
            self.__modified_datetime = datetime.fromtimestamp(mt, tz=UTC)
        return self.__modified_datetime.isoformat()

    @property
    def removed(self) -> str:
        """Indicate whether file has been flagged as removed."""
        return self.__removed

    def remove(self, reason: str) -> None:
        """Set file status to removed."""
        if not reason:
            reason = "Removed"
        self.__removed = reason

# TODO Need to handle special Ancillary Files

# TODO Need to implement sha256sum routine
