"""."""

from typing import Callable, Optional

from arxiv.base import logging

from ...domain import FileType, UploadedFile, UploadWorkspace

logger = logging.getLogger(__name__)
logger.propagate = False


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
        logger.debug('%s: check %s', self.__class__.__name__, u_file.path)
        generic_check = getattr(self, 'check', None)
        typed_check = getattr(self, f'check_{u_file.file_type.value}', None)
        final_check = getattr(self, f'check_finally', None)
        if generic_check is not None:
            generic_check(workspace, u_file)
        if typed_check is not None:
            typed_check(workspace, u_file)
        if final_check is not None:
            final_check(workspace, u_file)
