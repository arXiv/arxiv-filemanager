"""Checks related to uuencoded files."""

import os
import re
from arxiv.base import logging

from ...domain import FileType, UploadedFile, CheckableWorkspace
from .base import BaseChecker

logger = logging.getLogger(__name__)


class CheckForUUEncodedFiles(BaseChecker):
    """
    Decodes uuencoded file.

    I don't believe we are going to implement this unless I discover evidence
    this is used in recent submissions.
    """
