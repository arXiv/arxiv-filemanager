"""Checks for and removes hidden files."""

import os
import io
import re
from typing import Callable, Optional

from arxiv.base import logging

from ...domain import FileType, UploadedFile, UploadWorkspace
from .base import BaseChecker


logger = logging.getLogger(__name__)


class RemoveMacOSXHiddenFiles(BaseChecker):
    """Removes ``__MACOSX`` directories."""

    def check(self, workspace: UploadWorkspace, u_file: UploadedFile) \
            -> UploadedFile:
        """Remove ``__MACOSX`` directories."""
        if u_file.is_directory and u_file.name == '__MACOSX':
            workspace.add_warning(u_file, "Removed '__MACOSX' directory.")
            workspace.remove(u_file)
        return u_file


class RemoveFilesWithLeadingDot(BaseChecker):
    """Removes files and directories that start with a dot."""

    def check(self, workspace: UploadWorkspace, u_file: UploadedFile) \
            -> UploadedFile:
        """Removes files and directories that start with a dot."""
        if u_file.name.startswith('.') or u_file.path.startswith('.'):
            workspace.add_warning(u_file, 'Hidden file are not allowed.')
            workspace.remove(u_file,
                             f"Removed file '{u_file.name}' [File not"
                             " allowed].")
        return u_file
