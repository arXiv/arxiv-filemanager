"""File checks."""

from typing import Optional, Callable
from ..domain import UploadWorkspace, Checker


class SynchronousCheckingStrategy:
    """Runs checks one file at a time."""

    def check(self, workspace: 'UploadWorkspace', *checkers: Checker) -> None:
        """Run checks one file at a time."""
        for path, uploaded_file in workspace.files.items():
            # Don't run checks twice on the same file.
            if 'file_checks' in uploaded_file.meta:
                continue
            for checker in checkers:
                checker(workspace, uploaded_file)
            uploaded_file.meta['file_checks'] = True

        for checker in checkers:
            if hasattr(checker, 'check_workspace'):
                checker.check_workspace(workspace)
