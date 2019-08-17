"""Methods for checking for invalid file types."""

from arxiv.base import logging

from ...domain import FileType, UserFile, Workspace, SourceType, Code
from .base import BaseChecker


logger = logging.getLogger(__name__)


class FlagInvalidSourceTypes(BaseChecker):
    """Flag any invalid source types."""

    DOCX_NOT_SUPPORTED: Code = 'docx_not_supported'
    DOCX_MESSAGE = (
        "Submissions in docx are no longer supported. Please create a PDF file"
        " and submit that instead. Server side conversion of .docx to PDF may"
        " lead to incorrect font substitutions, among other problems, and your"
        " own PDF is likely to be more accurate."
    )

    ODF_NOT_SUPPORTED: Code = 'odf_not_supported'
    ODF_MESSAGE = (
        "Unfortunately arXiv does not support ODF. Please submit PDF instead."
    )

    EPS_NOT_SUPPORTED: Code = 'eps_not_supported'
    EPS_MESSAGE = (
        "This file appears to be a single encapsulated PostScript file."
    )

    SINGLE_AUX_TEX: Code = 'single_auxiliary_tex_file'
    SINGLE_AUX_TEX_MESSAGE = (
        "This file appears to be a single auxiliary TeX file."
    )

    def check_DOCX(self, workspace: Workspace, u_file: UserFile) \
            -> UserFile:
        """We no longer support DOCX."""
        if workspace.file_count == 1:
            workspace.source_type = SourceType.INVALID
            workspace.add_error(u_file, self.DOCX_NOT_SUPPORTED,
                                self.DOCX_MESSAGE)
        return u_file

    def check_ODF(self, workspace: Workspace, u_file: UserFile) \
            -> UserFile:
        """We no longer support ODF."""
        if workspace.file_count == 1:
            workspace.source_type = SourceType.INVALID
            workspace.add_error(u_file, self.ODF_NOT_SUPPORTED,
                                self.ODF_MESSAGE)
        return u_file

    def check_EPS(self, workspace: Workspace, u_file: UserFile) \
            -> UserFile:
        """Encapsulated postscript format is not supported."""
        if workspace.file_count == 1:
            workspace.source_type = SourceType.INVALID
            workspace.add_error(u_file, self.EPS_NOT_SUPPORTED,
                                self.EPS_MESSAGE)
        return u_file

    def check_TEXAUX(self, workspace: Workspace, u_file: UserFile) \
            -> UserFile:
        """Auxiliary TeX files are not allowed."""
        if workspace.file_count == 1:
            workspace.source_type = SourceType.INVALID
            workspace.add_error(u_file, self.SINGLE_AUX_TEX,
                                self.SINGLE_AUX_TEX_MESSAGE)
        return u_file


class FlagInvalidFileTypes(BaseChecker):
    """Flag any invalid file types."""

    RAR_NOT_SUPPORTED: Code = 'rar_not_supported'
    RAR_MESSAGE = ("We do not support 'rar' files. Please use 'zip' or 'tar' "
                   "instead.")

    def check_RAR(self, workspace: Workspace, u_file: UserFile) \
            -> UserFile:
        """Disallow rar files."""
        workspace.add_error(u_file, self.RAR_NOT_SUPPORTED, self.RAR_MESSAGE)
        return u_file
