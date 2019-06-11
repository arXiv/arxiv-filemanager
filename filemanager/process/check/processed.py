"""
Check for processed directory.

TODO: Need to investigate what's going on here so we
TODO: understand what needs to be done.

Deletion of 'processed' directory depends on from_paper_id also being set.

This appears to be related to replacing a submission where files are
imported/copied from previous version of paper.

Legacy action is to delete 'processed' directory when from_paper_id is set.

We have not reached the point of implementing this yet so I will only issue a
warning for now.
"""

import os
import io
import re
from typing import Callable, Optional

from arxiv.base import logging

from ...domain import FileType, UploadedFile, UploadWorkspace
from .base import BaseChecker


logger = logging.getLogger(__name__)


class WarnAboutProcessedDirectory(BaseChecker):
    """Check for and warn about processed directory."""

    def check(self, workspace: UploadWorkspace, u_file: UploadedFile) \
            -> UploadedFile:
        if u_file.is_directory and u_file.name.strip('/') == 'processed':
            workspace.add_warning(u_file,
                                  "Detected 'processed' directory. Please"
                                  " check.")
        return u_file
