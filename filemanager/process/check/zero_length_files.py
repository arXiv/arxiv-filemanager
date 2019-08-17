"""Check for and remove zero-length files."""

import os

from arxiv.base import logging

from ...domain import FileType, UserFile, Workspace, Code, Severity
from .base import BaseChecker


logger = logging.getLogger(__name__)


class ZeroLengthFileChecker(BaseChecker):
    """Checks for and removes zero-length files."""

    ZERO_LENGTH: Code = 'zero_length'
    ZERO_LENGTH_MESSAGE = "Removed file '%s' [file is empty]."

    def check(self, workspace: Workspace, u_file: UserFile) \
            -> UserFile:
        """Determine wether a file is zero-length, and remove it if so."""
        if u_file.is_empty and not u_file.is_directory:
            workspace.add_error(u_file, self.ZERO_LENGTH,
                                self.ZERO_LENGTH_MESSAGE % u_file.name,
                                severity=Severity.INFO, is_persistant=False)
            workspace.remove(u_file, self.ZERO_LENGTH_MESSAGE % u_file.name)
        return u_file
