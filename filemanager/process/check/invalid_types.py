"""Methods for checking for invalid file types."""

from arxiv.base import logging

from ...domain import FileType, UploadedFile, UploadWorkspace
from .base import BaseChecker


logger = logging.getLogger(__name__)


class FlagInvalidSourceTypes(BaseChecker):
    """Flag any invalid source types."""

    DOCX_ERROR_MESSAGE = (
        "Submissions in docx are no longer supported. Please create a PDF file"
        " and submit that instead. Server side conversion of .docx to PDF may"
        " lead to incorrect font substitutions, among other problems, and your"
        " own PDF is likely to be more accurate."
    )

    ODF_ERROR_MESSAGE = (
        "Unfortunately arXiv does not support ODF. Please submit PDF instead."
    )

    EPS_ERROR_MESSAGE = (
        "This file appears to be a single encapsulated PostScript file."
    )

    TEXAUX_ERROR_MESSAGE = (
        "This file appears to be a single auxiliary TeX file."
    )

    def check_DOCX(self, workspace: UploadWorkspace,
                   u_file: UploadedFile) -> None:
        """We no longer support DOCX."""
        if workspace.file_count == 1:
            workspace.source_type = UploadWorkspace.SourceType.INVALID
            workspace.add_error(u_file, self.DOCX_ERROR_MESSAGE)

    def check_ODF(self, workspace: UploadWorkspace,
                  u_file: UploadedFile) -> None:
        """We no longer support ODF."""
        if workspace.file_count == 1:
            workspace.source_type = UploadWorkspace.SourceType.INVALID
            workspace.add_error(u_file, self.DOCX_ERROR_MESSAGE)

    def check_EPS(self, workspace: UploadWorkspace,
                  u_file: UploadedFile) -> None:
        """Encapsulated postscript format is not supported."""
        if workspace.file_count == 1:
            workspace.source_type = UploadWorkspace.SourceType.INVALID
            workspace.add_error(u_file, self.EPS_ERROR_MESSAGE)

    def check_TEXAUX(self, workspace: UploadWorkspace,
                     u_file: UploadedFile) -> None:
        """Auxiliary TeX files are not allowed."""
        if workspace.file_count == 1:
            workspace.source_type = UploadWorkspace.INVALID
            workspace.add_error(u_file, self.TEXAUX_ERROR_MESSAGE)

    def check_TEXAUX(self, workspace: UploadWorkspace,
                     u_file: UploadedFile) -> None:
        """Auxiliary TeX files are not allowed."""
        if workspace.file_count == 1:
            workspace.source_type = UploadWorkspace.INVALID
            workspace.add_error(u_file, self.TEXAUX_ERROR_MESSAGE)


class FlagInvalidFileTypes(BaseChecker):
    """Flag any invalid file types."""

    def check_RAR(self, workspace: UploadWorkspace,
                  u_file: UploadedFile) -> None:
        """Disallow rar files."""
        workspace.add_error(u_file,
                            "We do not support 'rar' files. Please use 'zip'"
                            " or 'tar' instead.")
