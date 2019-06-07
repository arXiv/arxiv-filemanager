"""."""

from typing import Callable, Optional
from ...domain import FileType, UploadedFile, UploadWorkspace


class BaseChecker:
    """
    Base class for all file checkers.

    Child classes should implement a function
    ``check(self, u_file: UploadedFile) -> None:`` or
    ``check_{file_type}(self, u_file: UploadedFile) -> None:``.
    """

    def __call__(self, workspace: UploadWorkspace,
                 u_file: UploadedFile) -> None:
        """Perform file checks."""
        generic_check = getattr(self, 'check')
        typed_check = getattr(self, f'check_{u_file.file_type.value}')
        final_check = getattr(self, f'check_finally')
        if generic_check is not None:
            generic_check(workspace, u_file)
        if typed_check is not None:
            typed_check(workspace, u_file)
        if final_check is not None:
            final_check(workspace, u_file)
