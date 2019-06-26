"""Check for and fix malformed disallowed/filenames."""

import os
import re
from arxiv.base import logging

from ...domain import FileType, UploadedFile, UploadWorkspace
from .base import BaseChecker


logger = logging.getLogger(__name__)


class FixWindowsFileNames(BaseChecker):
    """Checks for and fixes Windows-style filenames."""

    WINDOWS_FILE_PREFIX = re.compile(r'^[A-Za-z]:\\(.*\\)?')

    def check(self, workspace: UploadWorkspace, u_file: UploadedFile) \
            -> UploadedFile:
        """Find Windows-style filenames and fix them."""
        if self.WINDOWS_FILE_PREFIX.search(u_file.path):
            # Rename using basename
            prev_name = u_file.name
            new_name = self.WINDOWS_FILE_PREFIX.sub('', prev_name)
            base_path, _ = os.path.split(u_file.path)
            new_path = os.path.join(base_path, new_name)
            workspace.rename(u_file, new_path)

            workspace.add_warning(u_file, f'Renamed {prev_name} to {new_name}')
        return u_file


class WarnAboutTeXBackupFiles(BaseChecker):
    """
    Checks for possible TeX backup files.

    We need to check this before tilde character gets translated to
    undderscore. Otherwise this warning never gets generated properly for
    ``.tex~``.
    """

    WARNING_MSG = ("File '%s' may be a backup file. Please inspect and remove"
                   " extraneous backup files.")
    TEX_BACKUP_FILE = re.compile(r'(.+)\.(tex_|tex.bak|tex\~)$', re.IGNORECASE)

    def check(self, workspace: UploadWorkspace, u_file: UploadedFile) \
            -> UploadedFile:
        """Check for and warn about possible backup files."""
        if not u_file.is_ancillary \
                and self.TEX_BACKUP_FILE.search(u_file.name):
            workspace.add_warning(u_file, self.WARNING_MSG % u_file.name)
        return u_file


class ReplaceIllegalCharacters(BaseChecker):
    """Checks for illegal characters and replaces them with underscores."""

    ILLEGAL = re.compile(r'[^\w\+\-\.\=\,\_]')
    """Filename contains illegal characters ``+-/=,``."""

    def check(self, workspace: UploadWorkspace, u_file: UploadedFile) \
            -> UploadedFile:
        """Check for illegal characters and replace them with underscores."""

        if not u_file.is_directory and self.ILLEGAL.search(u_file.name):
            # Translate bad characters.
            prev_name = u_file.name
            new_name = self.ILLEGAL.sub('_', prev_name)
            base_path, _ = os.path.split(u_file.path.strip('/'))
            new_path = os.path.join(base_path, new_name)
            workspace.rename(u_file, new_path)

            workspace.add_warning(u_file,
                                  "We only accept file names containing the"
                                  " characters: a-z A-Z 0-9 _ + - . =")
            workspace.add_warning(u_file, f'Renamed {prev_name} to {new_name}')
        return u_file


# TODO: needs more context; why would this happen? -- Erick 2019-06-07
class PanicOnIllegalCharacters(BaseChecker):
    """Register an error for files with illegal characters in their names."""

    ILLEGAL_ERROR = (
        'Filename "%s" contains unwanted bad characters. The only allowed are '
        'a-z A-Z 0-9 _ + - . , ='
    )

    def check(self, workspace: UploadWorkspace, u_file: UploadedFile) \
            -> UploadedFile:
        """Check for illegal characters and generate error if found."""

        if ReplaceIllegalCharacters.ILLEGAL.search(u_file.name):
            workspace.add_error(u_file, self.ILLEGAL_ERROR % u_file.name)
        return u_file


class ReplaceLeadingHyphen(BaseChecker):
    """Checks for a leading hyphen, and replaces it with an underscore."""

    def check(self, workspace: UploadWorkspace, u_file: UploadedFile) \
            -> UploadedFile:
        """Check for a leading hyphen, and replace it with an underscore."""

        if u_file.name.startswith('-'):
            prev_name = u_file.name
            new_name = re.sub('^-', '_', prev_name)
            base_path, _ = os.path.split(u_file.path)
            new_path = os.path.join(base_path, new_name)
            workspace.rename(u_file, new_path)

            workspace.add_warning(u_file,
                                  'We do not accept files starting with a'
                                  f' hyphen. Renamed {prev_name} to'
                                  f' {new_name}.')
        return u_file
