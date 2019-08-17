"""Checks for and removes hidden files."""

import os
import io
import re
from typing import Callable, Optional

from arxiv.base import logging

from ...domain import FileType, UserFile, Workspace, Code
from .base import BaseChecker


logger = logging.getLogger(__name__)


class RemoveMacOSXHiddenFiles(BaseChecker):
    """Removes ``__MACOSX`` directories."""

    HIDDEN_FILES_MACOSX: Code = 'hidden_files'
    HIDDEN_FILES_MACOSX_MESSAGE = "Removed '__MACOSX' directory."

    def check(self, workspace: Workspace, u_file: UserFile) \
            -> UserFile:
        """Remove ``__MACOSX`` directories."""
        if u_file.is_directory and u_file.name.strip('/') == '__MACOSX':
            workspace.add_warning(u_file, self.HIDDEN_FILES_MACOSX,
                                  self.HIDDEN_FILES_MACOSX_MESSAGE,
                                  is_persistant=False)
            workspace.remove(u_file)
        return u_file


class RemoveFilesWithLeadingDot(BaseChecker):
    """Removes files and directories that start with a dot."""

    HIDDEN_FILES_DOT = 'hidden_files_dot'
    HIDDEN_FILES_MESSAGE = 'Hidden file are not allowed.'

    def check(self, workspace: Workspace, u_file: UserFile) \
            -> UserFile:
        """Removes files and directories that start with a dot."""
        if u_file.name.startswith('.') or u_file.path.startswith('.'):
            workspace.add_warning(u_file, self.HIDDEN_FILES_DOT,
                                  self.HIDDEN_FILES_MESSAGE,
                                  is_persistant=False)
            workspace.remove(u_file,
                             f"Removed file '{u_file.name}' [File not"
                             " allowed].")
        return u_file
