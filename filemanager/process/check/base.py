"""."""

from typing import Callable, Optional
from ...domain import FileType, UploadedFile


class BaseChecker:
    """
    Base class for all file checkers.

    Child classes should implement a function
    ``check(self, uploaded_file: UploadedFile) -> None:`` or
    ``check_{file_type}(self, uploaded_file: UploadedFile) -> None:``.
    """

    def __call__(self, uploaded_file: UploadedFile) -> None:
        """Perform file checks."""
        generic_check: Optional[Callable[[UploadedFile], None]]
        generic_check = getattr(self, 'check')
        typed_check: Optional[Callable[[UploadedFile], None]]
        typed_check = getattr(self, f'check_{uploaded_file.file_type.value}')
        if generic_check is not None:
            generic_check(uploaded_file)
        if typed_check is not None:
            typed_check(uploaded_file)
