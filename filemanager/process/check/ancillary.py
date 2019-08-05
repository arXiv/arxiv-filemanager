"""Check for and mark ancillary files."""

import os
from arxiv.base import logging

from ...domain import FileType, UploadedFile, CheckableWorkspace
from .base import BaseChecker


logger = logging.getLogger(__name__)


class AncillaryFileChecker(BaseChecker):
    """Checks for and marks ancillary files."""

    def check(self, workspace: CheckableWorkspace, u_file: UploadedFile) \
            -> UploadedFile:
        """Check for and mark ancillary files."""
        if u_file.path.startswith(workspace.ancillary_path):
            u_file.is_ancillary = True
        return u_file
