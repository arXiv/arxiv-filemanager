"""File checks."""

from typing import Optional, Callable
from ..domain import UploadWorkspace, Checker


class SynchronousCheckingStrategy:
    """Runs checks one file at a time."""

    def check(self, workspace: 'UploadWorkspace', *checkers: Checker) -> None:
        """Run checks one file at a time."""
        for uploaded_file in workspace.files:
            for checker in checkers:
                checker(workspace, uploaded_file)
