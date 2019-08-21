"""Check for and eliminate files generated from TeX compilation."""

import os
import re
from arxiv.base import logging

from ...domain import FileType, UserFile, Workspace, Code, Severity
from .base import BaseChecker

logger = logging.getLogger(__name__)


class RemoveTeXGeneratedFiles(BaseChecker):
    """
    Check for TeX processed output files (log, aux, blg, dvi, ps, pdf, etc).

    Detect naming conflict, warn, remove offending files.
    """

    TEX_PRODUCED = re.compile(r'(.+)\.(log|aux|out|blg|dvi|ps|pdf)$',
                              re.IGNORECASE)

    NAME_CONFLICT: Code = 'name_conflict'
    NAME_CONFLICT_MSG = "Removed file '%s' due to name conflict."

    def check(self, workspace: Workspace, u_file: UserFile) \
            -> UserFile:
        """Check for and remove TeX processing files."""
        if self.TEX_PRODUCED.search(u_file.name):
            base_path, name = os.path.split(u_file.path)
            base, _ = os.path.splitext(name)

            tex_file = os.path.join(base_path, f'{base}.tex')
            ucase_tex_file = os.path.join(base_path, f'{base}.TEX')
            if workspace.exists(tex_file) or workspace.exists(ucase_tex_file):
                # Potential conflict / corruption by including TeX generated
                # files in submission.
                workspace.add_error(u_file, self.NAME_CONFLICT,
                                    self.NAME_CONFLICT_MSG % u_file.name,
                                    severity=Severity.INFO,
                                    is_persistant=False)
                workspace.remove(u_file, self.NAME_CONFLICT_MSG % u_file.name)
        return u_file


class DisallowDVIFiles(BaseChecker):
    """
    Check for DVI files in the source, and generate an error if found.

    If dvi file is present we ask for TeX source. Do we need to do this is TeX
    was also included???????
    """

    DVI_NOT_ALLOWED: Code
    DVI_MESSAGE = ('%s is a TeX-produced DVI file. Please submit the TeX'
                   'source instead.')

    def check_DVI(self, workspace: Workspace, u_file: UserFile) \
            -> UserFile:
        """Add an error for any non-ancillary DVI file."""
        if not u_file.is_ancillary:
            workspace.add_error(u_file, self.DVI_NOT_ALLOWED,
                                self.DVI_MESSAGE % u_file.name)
        return u_file
