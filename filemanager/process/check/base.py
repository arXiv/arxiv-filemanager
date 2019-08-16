"""."""

from typing import Callable, Optional

from arxiv.base import logging

from ...domain import FileType, UserFile, Workspace, \
    ICheckableWorkspace

logger = logging.getLogger(__name__)
logger.propagate = False


class StopCheck(Exception):
    """
    Execution of the checker should stop immediately.

    This can be used by a checker to force moving on to the next checker.
    """


class BaseChecker:
    """
    Base class for all file checkers.

    Child classes should implement a function
    ``check(self, u_file: UserFile) -> None:`` or
    ``check_{file_type}(self, u_file: UserFile) -> None:``.
    """

    def __call__(self, workspace: Workspace, u_file: UserFile) \
            -> UserFile:
        """Perform file checks."""
        logger.debug('%s: check %s', self.__class__.__name__, u_file.path)
        generic_check = getattr(self, 'check', None)
        tex_types_check = getattr(self, 'check_tex_types', None)
        typed_check = getattr(self, f'check_{u_file.file_type.value}', None)
        final_check = getattr(self, f'check_finally', None)
        if generic_check is not None:
            u_file = generic_check(workspace, u_file)
        if u_file.file_type.is_tex_type and tex_types_check is not None:
            u_file = tex_types_check(workspace, u_file)
        if typed_check is not None:
            u_file = typed_check(workspace, u_file)
        if final_check is not None:
            u_file = final_check(workspace, u_file)
        return u_file

    def check_workspace(self, workspace: Workspace) -> None:
        """Dummy stub for workspace check, to be implemented by child class."""
        return
