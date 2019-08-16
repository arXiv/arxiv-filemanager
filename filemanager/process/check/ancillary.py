"""Check for and mark ancillary files."""

import os
from arxiv.base import logging

from ...domain import FileType, UserFile, Workspace
from .base import BaseChecker


logger = logging.getLogger(__name__)


class AncillaryFileChecker(BaseChecker):
    """Checks for and marks ancillary files."""

    def check(self, workspace: Workspace, u_file: UserFile) \
            -> UserFile:
        """Check for and mark ancillary files."""
        if u_file.path.startswith(workspace.ancillary_path):
            u_file.is_ancillary = True
        return u_file
