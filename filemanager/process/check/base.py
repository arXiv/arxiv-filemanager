"""."""

from typing import Callable, Optional
from ...domain import FileType, UploadedFile, UploadWorkspace


class BaseChecker:
    """
    Base class for all file checkers.

    Child classes should implement a function
    ``check(self, uploaded_file: UploadedFile) -> None:`` or
    ``check_{file_type}(self, uploaded_file: UploadedFile) -> None:``.
    """

    def __call__(self, workspace: UploadWorkspace,
                 uploaded_file: UploadedFile) -> None:
        """Perform file checks."""
        generic_check = getattr(self, 'check')
        typed_check = getattr(self, f'check_{uploaded_file.file_type.value}')
        final_check = getattr(self, f'check_finally')
        if generic_check is not None:
            generic_check(workspace, uploaded_file)
        if typed_check is not None:
            typed_check(workspace, uploaded_file)
        if final_check is not None:
            final_check(workspace, uploaded_file)
