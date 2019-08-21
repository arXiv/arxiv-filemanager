"""Check for domain-specific files that we disallow."""

import os
import re
from arxiv.base import logging

from ...domain import FileType, UserFile, Workspace, Code, Severity
from .base import BaseChecker

logger = logging.getLogger(__name__)

DISALLOWED_FILE: Code = 'disallowed_file'
DISALLOWED_FILE_MESSAGE = "Removed file '%s' [File not allowed]."


class RemoveHyperlinkStyleFiles(BaseChecker):
    """
    Checks for and remove hyperlink styles espcrc2 and lamuphys.

    These are styles that conflict with internal hypertex package.
    """

    DOT_STY = re.compile(r'^(espcrc2|lamuphys)\.sty$')
    DOT_TEX = re.compile(r'^(espcrc2|lamuphys)\.tex$')

    DOT_TEX_DETECTED: Code = 'dot_tex_detected'
    DOT_TEX_MESSAGE = "Possible submitter error. Unwanted '%s'"

    HYPERLINK_COMPATIBLE: Code = 'hyperlink_compatible_package'
    HYPERLINK_COMPATIBLE_MESSAGE = (
        "Found hyperlink-compatible package '%s'. Will remove and use"
        " hypertex-compatible local version"
    )

    def check(self, workspace: Workspace, u_file: UserFile) \
            -> UserFile:
        """Check for and remove hyperlink styles espcrc2 and lamuphys."""
        if self.DOT_STY.search(u_file.name):
            workspace.add_error(
                u_file, self.HYPERLINK_COMPATIBLE,
                self.HYPERLINK_COMPATIBLE_MESSAGE % u_file.name,
                severity=Severity.INFO, is_persistant=False
            )
            workspace.remove(u_file,
                             self.HYPERLINK_COMPATIBLE_MESSAGE % u_file.name)

        elif self.DOT_TEX.search(u_file.name):
            # I'm not sure why this is just a warning
            workspace.add_warning(u_file, self.DOT_TEX_DETECTED,
                                  self.DOT_TEX_MESSAGE % u_file.name)
        return u_file


# TODO: this needs more documentation/context. What are they? Why are they
# being removed? -- Erick 2019-06-07
class RemoveDisallowedFiles(BaseChecker):
    """Checks for and removes disallowed files."""

    DISALLOWED = ['uufiles', 'core', 'splread.1st']

    def check(self, workspace: Workspace, u_file: UserFile) \
            -> UserFile:
        """Check for and removes disallowed files."""
        if u_file.name in self.DISALLOWED:
            workspace.add_error(u_file, DISALLOWED_FILE,
                                DISALLOWED_FILE_MESSAGE % u_file.name,
                                severity=Severity.INFO, is_persistant=False)
            workspace.remove(u_file, DISALLOWED_FILE_MESSAGE % u_file.name)
        return u_file


class RemoveMetaFiles(BaseChecker):
    """Checks for and removes a variety of meta files based on file names."""

    XXX_FILE = re.compile(r'^xxx\.(rsrc$|finfo$|cshrc$|nfs)')
    GF_FILE = re.compile(r'\.[346]00gf$')
    DESC_FILE = re.compile(r'\.desc$')
    DISALLOWED_PATTERNS = [XXX_FILE, GF_FILE, DESC_FILE]

    def check(self, workspace: Workspace, u_file: UserFile) \
            -> UserFile:
        """Check for and remove disallowed meta files."""
        for pattern in self.DISALLOWED_PATTERNS:
            if pattern.search(u_file.name):
                workspace.add_error(u_file, DISALLOWED_FILE,
                                    DISALLOWED_FILE_MESSAGE % u_file.name,
                                    severity=Severity.INFO,
                                    is_persistant=False)
                workspace.remove(u_file, DISALLOWED_FILE_MESSAGE % u_file.name)
        return u_file


class RemoveExtraneousRevTeXFiles(BaseChecker):
    """Checks for and remove extraneous RevTeX files."""

    REVTEX_WARNING_MSG = (
        "WILL REMOVE standard revtex4 style files from this "
        "submission. revtex4 is now fully supported by arXiv "
        "and all its mirrors, for details see the "
        "<a href=\"/help/faq/revtex\">RevTeX FAQ</a>. If you "
        "have modified these files in any way then you must "
        "rename them before attempting to include them with your submission."
    )

    EXTRANEOUS = re.compile(r'^(10pt\.rtx|11pt\.rtx|12pt\.rtx|aps\.rtx|'
                            r'revsymb\.sty|revtex4\.cls|rmp\.rtx)$')

    def check(self, workspace: Workspace, u_file: UserFile) \
            -> UserFile:
        """Check for and remove files already included in TeX Live release."""
        if self.EXTRANEOUS.search(u_file.name):
            workspace.add_error(u_file, DISALLOWED_FILE,
                                self.REVTEX_WARNING_MSG,
                                severity=Severity.INFO, is_persistant=False)
            workspace.remove(u_file, self.REVTEX_WARNING_MSG)
        return u_file


class RemoveDiagramsPackage(BaseChecker):
    """
    Checks for and removes the diagrams package.

    The diagrams package contains a time bomb and stops working after a
    specified date. We use an internal version with the time bomb disabled.
    """

    DIAGRAMS_WARNING = (
        "Removed standard style files for Paul Taylor's "
        "diagrams package. This package is supported in arXiv's TeX "
        "tree and the style files are thus unnecessary. Furthermore, they "
        "include 'time-bomb' code which will render submissions that include "
        "them unprocessable at some time in the future."
    )

    DIAGRAMS = re.compile(r'^diagrams\.(sty|tex)$')

    def check(self, workspace: Workspace, u_file: UserFile) \
            -> UserFile:
        """Check for and remove the diagrams package."""
        if self.DIAGRAMS.search(u_file.name):
            workspace.add_error(u_file, DISALLOWED_FILE, self.DIAGRAMS_WARNING,
                                severity=Severity.INFO, is_persistant=False)
            workspace.remove(u_file, self.DIAGRAMS_WARNING)
        return u_file


class RemoveAADemoFile(BaseChecker):
    """
    Checks for and removes the Astronomy and Astrophysics demo file.

    This is demo file that authors seem to include with their submissions.
    """

    AA_DEM_MSG = (
         "Removed file 'aa.dem' on the assumption that it is "
         'the example file for the Astronomy and Astrophysics '
         'macro package aa.cls.'
    )

    def check(self, workspace: Workspace, u_file: UserFile) \
            -> UserFile:
        """Check for and remove the ``aa.dem`` file."""
        if u_file.name == 'aa.dem':
            workspace.add_error(u_file, DISALLOWED_FILE, self.AA_DEM_MSG,
                                severity=Severity.INFO, is_persistant=False)
            workspace.remove(u_file, self.AA_DEM_MSG)
        return u_file


# TODO: add more context here. -- Erick 2019-06-07
class RemoveMissingFontFile(BaseChecker):
    """Checks for and removes the ``missfont.log`` file."""

    MISSFONT_WARNING = (
        "Removed file 'missfont.log'. Detected 'missfont.log' file in"
        " uploaded files. This may indicate a problem with the fonts"
        " your submission uses. Please correct any issues with fonts"
        " and be sure to examine the fonts in the final preview PDF"
        " that our system generates."
    )

    def check(self, workspace: Workspace, u_file: UserFile) \
            -> UserFile:
        """Check for and remove the ``missfont.log`` file."""
        if u_file.name == 'missfont.log':
            workspace.add_error(u_file, DISALLOWED_FILE, self.MISSFONT_WARNING,
                                severity=Severity.INFO, is_persistant=False)
            workspace.remove(u_file, self.MISSFONT_WARNING)
        return u_file


class RemoveSyncTeXFiles(BaseChecker):
    """
    Checks for and removes SyncTeX files.

    ``.synctex`` files are generated by different TeX engine that we do not
    use.
    """

    SYNCTEX_MSG = (
        "Removed file '%s'. SyncTeX files are not used by our"
        " system and may be large."
    )
    SYNCTEX = re.compile(r'\.synctex$')

    def check(self, workspace: Workspace, u_file: UserFile) \
            -> UserFile:
        """Check for and remove synctex files."""
        if self.SYNCTEX.search(u_file.name):
            workspace.add_error(u_file, DISALLOWED_FILE,
                                self.SYNCTEX_MSG % u_file.name,
                                severity=Severity.INFO, is_persistant=False)
            workspace.remove(u_file, self.SYNCTEX_MSG % u_file.name)
        return u_file


# TODO: this needs some context/explanation. -- Erick 2019-06-07
class FixTGZFileName(BaseChecker):
    """[ needs info ]"""

    PTN = re.compile(r'([\.\-]t?[ga]?z)$', re.IGNORECASE)
    """[ needs info ]"""

    def check(self, workspace: Workspace, u_file: UserFile) \
            -> UserFile:
        """[ needs info ]"""
        if self.PTN.search(u_file.name):
            base_path, prev_name = os.path.split(u_file.path)
            new_name = self.PTN.sub('', prev_name)
            new_path = os.path.join(base_path, new_name)
            workspace.rename(u_file, new_path)
        return u_file


# TODO: it's unclear why we have a fatal error that discusses rejection here
# when we are also removing the file. -- Erick 2019-06-25
class RemoveDOCFiles(BaseChecker):
    """Removes .doc files that fail type checks."""

    MS_WORD_NOT_SUPPORTED: Code = 'ms_word_not_supported'

    DOC_WARNING = (
        "Your submission has been rejected because it contains "
        "one or more files with extension .doc, assumed to be "
        "MSWord files. Sadly, MSWord is not an acceptable "
        "submission format: see <a href=\"/help/submit\">"
        "submission help</a> for details of accepted formats. "
        "If your document was created using MSWord then it is "
        "probably best to submit as PDF (MSWord can produce "
        "marginal and/or non-compliant PostScript). If your "
        "submission includes files with extension .doc which "
        "are not MSWord documents, please rename to a different"
        " extension and resubmit."
    )
    """DOC (MS Word) format not accepted warning message."""

    def check_FAILED(self, workspace: Workspace, u_file: UserFile) \
            -> UserFile:
        if u_file.name.endswith('.doc'):
            # TODO: The original code did indeed include removal here; and
            # yet we are issuing a warning that pre-supposes the presence of
            # the file after processing. Disabling removal for now, but we
            # should get clear on what the desired behavior is.
            # -- Erick 2019-06-25
            #
            # workspace.remove(u_file)
            workspace.add_error(u_file, self.MS_WORD_NOT_SUPPORTED,
                                self.DOC_WARNING)
        return u_file
