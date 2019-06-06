"""Methods for checking file name extensions."""

import os

from arxiv.base import logging

from ...domain import FileType, UploadedFile, UploadWorkspace
from .base import BaseChecker


logger = logging.getLogger(__name__)


class FixFileExtensionsChecker(BaseChecker):
    """Checks and fixes filename extensions for known formats."""

    def _change_extension(self, workspace: UploadWorkspace,
                          uploaded_file: UploadedFile, extension: str) -> None:
        former_name = uploaded_file.name
        base_dir, name = os.path.split(uploaded_file.path)
        base_name, _ = os.path.splitext(name)
        new_name = f'{base_name}.{extension}'
        new_path = os.path.join(base_dir, new_name)
        workspace.rename_file(uploaded_file, new_path)
        workspace.add_warning(uploaded_file,
                              f"Renamed '{former_name}' to {new_name}.")

    def check_TYPE_POSTSCRIPT(self, workspace: UploadWorkspace,
                              uploaded_file: UploadedFile) -> None:
        """Ensure that postscript files have a ``.ps`` extension."""
        if uploaded_file.ext != 'ps':
            self._change_extension(workspace, uploaded_file, 'pdf')

    def check_TYPE_PDF(self, workspace: UploadWorkspace,
                       uploaded_file: UploadedFile) -> None:
        """Ensure that PDF files have a ``.pdf`` extension."""
        if uploaded_file.ext != 'pdf':
            self._change_extension(workspace, uploaded_file, 'pdf')

    def check_TYPE_HTML(self, workspace: UploadWorkspace,
                        uploaded_file: UploadedFile) -> None:
        """Ensure that HTML files have a ``.html`` extension."""
        if uploaded_file.ext != 'html':
            self._change_extension(workspace, uploaded_file, 'html')
