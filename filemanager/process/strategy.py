"""File checks."""

from typing import Optional, Callable
from ..domain import UploadWorkspace, IChecker


class SynchronousCheckingStrategy:
    """Runs checks one file at a time."""

    def check(self, workspace: 'UploadWorkspace', *checkers: IChecker) -> None:
        """Run checks one file at a time."""
        # This may take a few passes, as we may be unpacking compressed files.
        while workspace.has_unchecked_files:
            for u_file in workspace.iter_files():
                if u_file.is_checked:   # Don't run checks twice on the same
                    continue            # file.
                for checker in checkers:
                    checker(workspace, u_file)
                    if u_file.is_removed:   # If a checker removes a file, no
                        break               # further action should be taken.
                u_file.is_checked = True

            # Perform workspace-wide checks.
            for checker in checkers:
                if hasattr(checker, 'check_workspace'):
                    checker.check_workspace(workspace)
