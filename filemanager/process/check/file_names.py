"""Check for and fix malformed disallowed/filenames."""

import os
import re
from arxiv.base import logging

from ...domain import FileType, UserFile, Workspace, Code
from .base import BaseChecker


logger = logging.getLogger(__name__)

ILLEGAL_CHARACTERS: Code = 'filename_illegal_characters'


class FixWindowsFileNames(BaseChecker):
    """Checks for and fixes Windows-style filenames."""

    WINDOWS_FILE_PREFIX = re.compile(r'^[A-Za-z]:\\(.*\\)?')

    FIXED_WINDOWS_NAME = 'fixed_windows_name'
    FIXED_WINDOWS_NAME_MESSAGE = "Renamed '%s' to '%s'."

    def check(self, workspace: Workspace, u_file: UserFile) \
            -> UserFile:
        """Find Windows-style filenames and fix them."""
        if self.WINDOWS_FILE_PREFIX.search(u_file.path):
            # Rename using basename
            prev_name = u_file.name
            new_name = self.WINDOWS_FILE_PREFIX.sub('', prev_name)
            base_path, _ = os.path.split(u_file.path)
            new_path = os.path.join(base_path, new_name)
            workspace.rename(u_file, new_path)

            workspace.add_warning(
                u_file,
                self.FIXED_WINDOWS_NAME,
                self.FIXED_WINDOWS_NAME_MESSAGE % (prev_name, new_name),
                is_persistant=False
            )
        return u_file


class WarnAboutTeXBackupFiles(BaseChecker):
    """
    Checks for possible TeX backup files.

    We need to check this before tilde character gets translated to
    undderscore. Otherwise this warning never gets generated properly for
    ``.tex~``.
    """

    BACKUP_FILE: Code = 'possible_backup_file'
    BACKUP_MESSAGE = ("File '%s' may be a backup file. Please inspect and"
                      " remove extraneous backup files.")

    TEX_BACKUP_FILE = re.compile(r'(.+)\.(tex_|tex.bak|tex\~)$', re.IGNORECASE)

    def check(self, workspace: Workspace, u_file: UserFile) \
            -> UserFile:
        """Check for and warn about possible backup files."""
        if not u_file.is_ancillary \
                and self.TEX_BACKUP_FILE.search(u_file.name):
            workspace.add_warning(u_file, self.BACKUP_FILE,
                                 self.BACKUP_MESSAGE % u_file.name)
        return u_file


class ReplaceIllegalCharacters(BaseChecker):
    """Checks for illegal characters and replaces them with underscores."""

    ILLEGAL = re.compile(r'[^\w\+\-\.\=\,\_]')
    """Filename contains illegal characters ``+-/=,``."""

    ILLEGAL_CHARACTERS_MSG = ("We only accept file names containing the"
                              " characters: a-z A-Z 0-9 _ + - . =."
                              " Renamed '%s' to '%s'")

    def check(self, workspace: Workspace, u_file: UserFile) \
            -> UserFile:
        """Check for illegal characters and replace them with underscores."""

        if not u_file.is_directory and self.ILLEGAL.search(u_file.name):
            # Translate bad characters.
            prev_name = u_file.name
            new_name = self.ILLEGAL.sub('_', prev_name)
            base_path, _ = os.path.split(u_file.path.strip('/'))
            new_path = os.path.join(base_path, new_name)
            workspace.rename(u_file, new_path)

            workspace.add_warning(
                u_file, ILLEGAL_CHARACTERS,
                self.ILLEGAL_CHARACTERS_MSG % (prev_name, new_name),
                is_persistant=False
            )
        return u_file


# TODO: needs more context; why would this happen? -- Erick 2019-06-07
class PanicOnIllegalCharacters(BaseChecker):
    """Register an error for files with illegal characters in their names."""

    ILLEGAL_CHARACTERS_MSG = (
        'Filename "%s" contains unwanted bad characters. The only allowed are '
        'a-z A-Z 0-9 _ + - . , ='
    )

    def check(self, workspace: Workspace, u_file: UserFile) \
            -> UserFile:
        """Check for illegal characters and generate error if found."""
        if u_file.is_directory:
            return u_file
        if ReplaceIllegalCharacters.ILLEGAL.search(u_file.name):
            workspace.add_error(u_file, ILLEGAL_CHARACTERS,
                                self.ILLEGAL_CHARACTERS_MSG % u_file.name)
        return u_file


class ReplaceLeadingHyphen(BaseChecker):
    """Checks for a leading hyphen, and replaces it with an underscore."""

    LEADING_HYPHEN: Code = 'filename_leading_hyphen'
    LEADING_HYPHEN_MESSAGE = \
        "We do not accept files starting with a hyphen. Renamed '%s' to '%s'."

    def check(self, workspace: Workspace, u_file: UserFile) \
            -> UserFile:
        """Check for a leading hyphen, and replace it with an underscore."""

        if u_file.name.startswith('-'):
            prev_name = u_file.name
            new_name = re.sub('^-', '_', prev_name)
            base_path, _ = os.path.split(u_file.path)
            new_path = os.path.join(base_path, new_name)
            workspace.rename(u_file, new_path)

            workspace.add_warning(
                u_file,
                self.LEADING_HYPHEN,
                self.LEADING_HYPHEN_MESSAGE % (prev_name, new_name),
                is_persistant=False
            )
        return u_file
