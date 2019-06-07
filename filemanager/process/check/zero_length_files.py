"""Check for and remove zero-length files."""

import os

from arxiv.base import logging

from ...domain import FileType, UploadedFile, UploadWorkspace
from .base import BaseChecker


logger = logging.getLogger(__name__)


class ZeroLengthFileChecker(BaseChecker):
    """Checks for and removes zero-length files."""

    def check(self, workspace: UploadWorkspace, u_file: UploadedFile) -> None:
        """Determine wether a file is zero-length, and remove it if so."""
        if u_file.is_empty:
            workspace.add_warning(
                u_file,
                f"File '{u_file.name}' is empty (size is zero)."
            )
            workspace.remove(u_file,
                             f"Removed file '{u_file.name}' [file is empty].")
