"""Check for domain-specific files that we disallow."""

import os
import re
from arxiv.base import logging

from ...domain import FileType, UploadedFile, UploadWorkspace
from .base import BaseChecker

logger = logging.getLogger(__name__)


class RemoveHyperlinkStyleFiles(BaseChecker):
    """
    Checks for and remove hyperlink styles espcrc2 and lamuphys.

    These are styles that conflict with internal hypertex package.
    """

    WARNING_MSG = ("Found hyperlink-compatible package '%s'. Will remove and"
                   " use hypertex-compatible local version")
    DOT_STY = re.compile(r'^(espcrc2|lamuphys)\.sty$')
    DOT_TEX = re.compile(r'^(espcrc2|lamuphys)\.tex$')

    def check(self, workspace: UploadWorkspace, u_file: UploadedFile) -> None:
        """Check for and remove hyperlink styles espcrc2 and lamuphys."""
        if self.DOT_STY.search(u_file.name):
            workspace.remove(u_file, self.WARNING_MSG % u_file.name)

        elif self.DOT_TEX.search(u_file.name):
            # I'm not sure why this is just a warning
            workspace.add_warning(u_file,
                                  "Possible submitter error. Unwanted"
                                  f" '{file_name}'")


# TODO: this needs more documentation/context. What are they? Why are they
# being removed? -- Erick 2019-06-07
class RemoveDisallowedFiles(BaseChecker):
    """Checks for and removes disallowed files."""

    DISALLOWED = ['uufiles', 'core', 'splread.1st']

    def check(self, workspace: UploadWorkspace, u_file: UploadedFile) -> None:
        """Check for and removes disallowed files."""
        if u_file.name in self.DISALLOWED:
            workspace.remove(u_file,
                             f"Removed the file '{file_name}' [File not"
                             " allowed].")


class RemoveMetaFiles(BaseChecker):
    """Checks for and removes a variety of meta files based on file names."""

    XXX_FILE = re.compile(r'^xxx\.(rsrc$|finfo$|cshrc$|nfs)')
    GF_FILE = re.compile(r'\.[346]00gf$')
    DESC_FILE = re.compile(r'\.desc$')
    DISALLOWED_PATTERNS = [XXX_FILE, GF_FILE, DESC_FILE]

    def check(self, workspace: UploadWorkspace, u_file: UploadedFile) -> None:
        """Check for and remove disallowed meta files."""
        for pattern in self.DISALLOWED_PATTERNS:
            if pattern.search(u_file.name):
                workspace.remove(u_file,
                                 f"Removed file '{obj.name}' [File not"
                                 " allowed].")
                return


class CheckForBibFile(BaseChecker):
    """
    Checks for .bib files, and removes them if a .bbl file is present.

    New modified handling of .bib without .bbl. We no longer delete .bib UNLESS
    we detect .bbl file Generate error until we have .bbl.
    """

    BIB_FILE = re.compile(r'(.*)\.bib$', re.IGNORECASE)

    BIB_WITH_BBL_WARNING = (
        "We do not run bibtex in the auto - TeXing procedure. We do not run"
        " bibtex because the .bib database files can be quite large, and the"
        " only thing necessary to make the references for a given paper is"
        " the .bbl file."
    )

    BIB_NO_BBL_WARNING = (
        "We do not run bibtex in the auto - TeXing "
        "procedure. If you use it, include in your submission the .bbl file "
        "which bibtex produces on your home machine; otherwise your "
        "references will not come out correctly. We do not run bibtex "
        "because the .bib database files can be quite large, and the only "
        "thing necessary to make the references for a given paper is "
        "the.bbl file."
    )

    BBL_MISSING_ERROR_MSG = (
        "Your submission contained {base}.bib file, but no {base}.bbl"
        " file (include {base}.bbl, or submit without {base}.bib; and"
        " remember to verify references)."
    )

    def check(self, workspace: UploadWorkspace, u_file: UploadedFile) -> None:
        """Check for a .bib file, and remove if a .bbl file is present."""
        if self.BIB_FILE.search(u_file.name):
            # Create path to bbl file - assume uses same basename as .bib.
            base_path, name = os.path.split(u_file.path)
            base, _ = os.path.splitext(name)
            bbl_file = f'{base}.bbl'
            bbl_path = os.path.join(base_path, bbl_file)

            if workspace.exists(bbl_path):
                # If .bbl exists we go ahead and delete .bib file and warn
                # submitter of this action.
                workspace.add_warning(u_file, self.BIB_WITH_BBL_WARNING)
                workspace.remove(u_file,
                                 f"Removed the file '{file_name}'. Using"
                                 f" '{bbl_file}' for references.")
            else:
                # Missing .bbl (potential missing references). Generate an
                # error and DO NOT DELETE .bib file. Note: We are using .bib as
                # flag until .bbl exists.
                workspace.add_warning(u_file, self.BIB_NO_BBL_WARNING)
                workspace.add_error(u_file,
                                    self.BBL_MISSING_ERROR_MSG.format(base=base))


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

    def check(self, workspace: UploadWorkspace, u_file: UploadedFile) -> None:
        """Check for and remove files already included in TeX Live release."""
        if self.EXTRANEOUS.search(u_file.name):
            workspace.remove(u_file, self.REVTEX_WARNING_MSG)


class RemoveDiagramsPackage(BaseChecker):
    """
    Checks for and removes the diagrams package.

    The diagrams package contains a time bomb and stops working after a
    specified date. We use an internal version with the time bomb disabled.
    """

    DIAGRAMS_WARNING = (
        "REMOVING standard style files for Paul Taylor's "
        "diagrams package. This package is supported in arXiv's TeX "
        "tree and the style files are thus unnecessary. Furthermore, they "
        "include 'time-bomb' code which will render submissions that include "
        "them unprocessable at some time in the future."
    )

    DIAGRAMS = re.compile(r'^diagrams\.(sty|tex)$')

    def check(self, workspace: UploadWorkspace, u_file: UploadedFile) -> None:
        """Check for and remove the diagrams package."""
        if self.DIAGRAMS.search(u_file.name):
            workspace.remove(u_file, self.DIAGRAMS_WARNING)


class RemoveAADemoFile(BaseChecker):
    """
    Checks for and removes the Astronomy and Astrophysics demo file.

    This is demo file that authors seem to include with their submissions.
    """

    AA_DEM_MSG = (
         "Removing file 'aa.dem' on the assumption that it is "
         'the example file for the Astronomy and Astrophysics '
         'macro package aa.cls.'
    )

    def check(self, workspace: UploadWorkspace, u_file: UploadedFile) -> None:
        """Check for and remove the ``aa.dem`` file."""
        if u_file.name == 'aa.dem':
            workspace.remove(u_file, self.AA_DEM_MSG)


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

    def check(self, workspace: UploadWorkspace, u_file: UploadedFile) -> None:
        """Check for and remove the ``missfont.log`` file."""
        if u_file.name == 'missfont.log':
            workspace.remove(u_file, self.MISSFONT_WARNING)


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

    def check(self, workspace: UploadWorkspace, u_file: UploadedFile) -> None:
        """Check for and remove synctex files."""
        if u_file.name == 'missfont.log':
            workspace.remove(u_file, self.SYNCTEX_MSG % u_file.name)


# TODO: this needs some context/explanation. -- Erick 2019-06-07
class FixTGZFileName(BaseChecker):
    """[ needs info ]"""

    PTN = re.compile(r'([\.\-]t?[ga]?z)$', re.IGNORECASE)
    """[ needs info ]"""

    def check(self, workspace: UploadWorkspace, u_file: UploadedFile) -> None:
        """[ needs info ]"""
        if self.PTN.search(u_file.name):
            base_path, prev_name = os.path.split(u_file.path)
            new_name = self.PTN.sub('', prev_name)
            new_path = os.path.jion(base_path, new_name)
            workspace.rename(u_file, new_path)
            workspace.add_warning(u_file,
                                  "Renaming '{prev_name}' to '{new_name}'.")


class RemoveDOCFiles(BaseChecker):

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

    def check(self, workspace: UploadWorkspace, u_file: UploadedFile) -> None:
        if u_file.name.endswith('.doc'):
            workspace.remove(u_file)
            workspace.add_error(u_file, self.DOC_WARNING)