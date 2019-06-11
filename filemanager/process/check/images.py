"""Checks related to images/graphics."""

import os
import re
from arxiv.base import logging

from ...domain import FileType, UploadedFile, UploadWorkspace
from .base import BaseChecker

logger = logging.getLogger(__name__)


class CheckForUnacceptableImages(BaseChecker):
    """
    Checks for image types that are not accepted.

    Issue error for graphics that are not supported by arXiv.

    Issue this error once due to possibility submission may contain
    dozens of invalid graphics files that we do not accept.
    """

    UNACCEPTABLE = re.compile(r'\.(pcx|bmp|wmf|opj|pct|tiff?)$', re.IGNORECASE)
    ERROR_MSG = (
        f"%s is not a supported graphics format: most "
        "readers do not have the programs needed to view and print "
        ".$format figures. Please save your [% format %] "
        "figures instead as PostScript, PNG, JPEG, or GIF "
        "(PNG/JPEG/GIF files can be viewed and printed with "
        "any graphical web browser) -- for more information."
    )

    def check_IMAGE(self, workspace: UploadWorkspace, u_file: UploadedFile) \
            -> UploadedFile:
        """Check and warn about image types that are not accepted."""
        match = self.UNACCEPTABLE.search(u_file.name)
        if match:
            workspace.add_warning(u_file, self.ERROR_MSG % match.group(1))
        return u_file
