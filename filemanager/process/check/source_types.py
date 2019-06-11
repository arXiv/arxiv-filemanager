"""Check overall source type."""

import os

from arxiv.base import logging

from ...domain import FileType, UploadedFile, UploadWorkspace
from .base import BaseChecker


logger = logging.getLogger(__name__)
logger.propagate = False


class InferSourceType(BaseChecker):
    """Attempt to determine the source type for the workspace as a whole."""

    def check(self, workspace: UploadWorkspace,
              u_file: UploadedFile) -> None:
        """Check for single-file TeX source package."""
        if workspace.file_count != 1:
            return
        logger.debug('Single file in workspace: %s', u_file.path)
        if u_file.is_ancillary or u_file.is_always_ignore:
            logger.debug('Ancillary or always-ignore file; invalid source')
            workspace.source_type = UploadWorkspace.SourceType.INVALID
            workspace.add_non_file_error('Found single ancillary file. Invalid'
                                         ' submission.')

    def check_workspace(self, workspace: UploadWorkspace) -> None:
        """Determine the source type for the workspace as a whole."""
        logger.debug('Check whole workspace')
        # if not workspace.source_type.is_unknown:
        #     return

        if workspace.file_count == 0:
            # No files detected, were all files removed? did user clear out
            # files? Since users are allowed to remove all files we won't
            # generate a message here. If system deletes all uploaded
            # files there will be warnings associated with those actions.
            logger.debug('Workspace has no files; setting source type invalid')
            workspace.source_type = UploadWorkspace.SourceType.INVALID
            return

        type_counts = workspace.get_file_type_counts()

        # HTML submissions may contain the formats below.
        html_aux_file_count = sum((
            type_counts['html'], type_counts['image'],
            type_counts['include'], type_counts['postscript'],
            type_counts['pdf'], type_counts['directory'],
            type_counts['readme']
        ))

        # Postscript submission may be composed of several other formats.
        postscript_aux_file_counts = sum((
            type_counts['postscript'], type_counts['pdf'],
            type_counts['ignore'], type_counts['directory'],
            type_counts['image']
        ))
        if type_counts['files'] == type_counts['ignore']:
            workspace.source_type = UploadWorkspace.SourceType.INVALID
            workspace.add_non_file_warning(
                "All files are auto-ignore. If you intended to withdraw the"
                " article, please use the 'withdraw' function from the list"
                "of articles on your account page."
            )
            logger.debug('All files are auto-ignore; source type is invalid')
        elif type_counts['all_files'] > 0 and type_counts['files'] == 0:
            # No source files detected, extra ancillary files may be present
            # User may have deleted main document source.
            logger.debug('No active (non-ancillary) submission files')
            workspace.source_type = UploadWorkspace.SourceType.INVALID
        elif type_counts['html'] > 0 \
                and type_counts['files'] == html_aux_file_count:
            workspace.source_type = UploadWorkspace.SourceType.HTML
        elif type_counts['postscript'] > 0 \
                and type_counts['files'] == postscript_aux_file_counts:
            workspace.source_type = UploadWorkspace.SourceType.POSTSCRIPT
        else:   # Default source type is TEX
            logger.debug('Default source type is TeX')
            workspace.source_type = UploadWorkspace.SourceType.TEX

    def check_TEX(self, workspace: UploadWorkspace,
                  u_file: UploadedFile) -> None:
        """Check for single-file TeX source package."""
        if workspace.source_type.is_unknown and workspace.file_count == 1:
            workspace.source_type = UploadWorkspace.SourceType.TEX
            return

    def check_POSTSCRIPT(self, workspace: UploadWorkspace,
                         u_file: UploadedFile) -> None:
        """Check for single-file PostScript source package."""
        if workspace.source_type.is_unknown and workspace.file_count == 1:
            workspace.source_type = UploadWorkspace.SourceType.POSTSCRIPT

    def check_PDF(self, workspace: UploadWorkspace,
                  u_file: UploadedFile) -> None:
        """Check for single-file PDF source package."""
        if workspace.source_type.is_unknown and workspace.file_count == 1:
            workspace.source_type = UploadWorkspace.SourceType.PDF

    def check_HTML(self, workspace: UploadWorkspace,
                   u_file: UploadedFile) -> None:
        """Check for single-file HTML source package."""
        if workspace.source_type.is_unknown and workspace.file_count == 1:
            workspace.source_type = UploadWorkspace.SourceType.HTML

    def check_FAILED(self, workspace: UploadWorkspace,
                     u_file: UploadedFile) -> None:
        """Check for single-file source with failed type detection."""
        if workspace.source_type.is_unknown and workspace.file_count == 1:
            workspace.source_type = UploadWorkspace.SourceType.INVALID
            workspace.add_error(u_file,
                                'Could not determine file type.')

    def check_finally(self, workspace: UploadWorkspace,
                      u_file: UploadedFile) -> None:
        """Check for unknown single-file source."""
        if workspace.source_type.is_unknown and workspace.file_count == 1:
            logger.debug('Source type not known, and only one file')
            workspace.source_type = UploadWorkspace.SourceType.INVALID
            workspace.add_error(u_file,
                                'Could not determine file type.')
