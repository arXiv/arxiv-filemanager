"""Checks related to well-formedness of TeX."""

import os
import re
from arxiv.base import logging

from ...domain import FileType, UserFile, Workspace
from .base import BaseChecker

logger = logging.getLogger(__name__)


# TODO: implement this.
class CheckTeXForm(BaseChecker):
    """
    Checks whether submission is using preprint document style.

    Adds warning if preprint style used in certain context.
    """

    NOT_IMPLEMENTED = ("%s: NOT IMPLEMENTED: formcheck routine needs to be"
                       " implemented.")

    def check_LATEX(self, workspace: Workspace,
                    u_file: UserFile) -> UserFile:
        """Check and warn if using preprint document style."""
        workspace.log.info(self.NOT_IMPLEMENTED % u_file.path)
        return u_file

    def check_LATEX2e(self, workspace: Workspace,
                      u_file: UserFile) -> UserFile:
        """Check and warn if using preprint document style."""
        workspace.log.info(self.NOT_IMPLEMENTED % u_file.path)
        return u_file
