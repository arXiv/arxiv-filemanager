from typing import List, Optional
from typing_extensions import Protocol

from dataclasses import field, dataclass

from ..uploaded_file import UploadedFile
from .source_type import SourceTypeMixin
from .util import modifies_workspace
from .file_mutations import FileMutationsWorkspace
from .countable import CountableWorkspace


class IChecker(Protocol):
    """A visitor that performs a check on an :class:`.UploadedFile`."""

    def __call__(self, workspace: 'CheckableWorkspace',
                 u_file: UploadedFile) -> UploadedFile:
        """Check an :class:`.UploadedFile`."""
        ...

    def check_workspace(self, workspace: 'CheckableWorkspace') -> None:
        ...


class ICheckingStrategy(Protocol):
    """Strategy for checking files in an :class:`.CheckableWorkspace`."""

    def check(self, workspace: 'CheckableWorkspace',
              *checkers: IChecker) -> None:
        """Perform checks on all files in the workspace."""
        ...


@dataclass
class CheckableWorkspace(SourceTypeMixin, CountableWorkspace,
                         FileMutationsWorkspace):
    """Adds checking functionality."""

    checkers: List[IChecker] = field(default_factory=list)
    """File checkers that should be applied to all files in the workspace."""

    strategy: Optional[ICheckingStrategy] = field(default=None)
    """Strategy for performing file checks."""

    @property
    def has_unchecked_files(self) -> bool:
        """Determine whether there are unchecked files in this workspace."""
        for u_file in self.iter_files(allow_directories=True):
            if not u_file.is_checked:
                return True
        return False

    def perform_checks(self) -> None:
        """Perform all checks on this workspace using the assigned strategy."""
        if self.strategy is None:
            raise RuntimeError('No checking strategy set')
        self.strategy.check(self, *self.checkers)

    @modifies_workspace()
    def add_files(self, *u_files: UploadedFile) -> None:
        """When files are added to the workspace, perform checks."""
        super(CheckableWorkspace, self).add_files(*u_files)
        self.perform_checks()