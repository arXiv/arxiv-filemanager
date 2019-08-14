"""Provides :class:`.ErrorsAndWarningsMixin`."""

from typing import List, Optional

from dataclasses import dataclass, field

from .stored import StoredWorkspace
from ..uploaded_file import UploadedFile
from ..error import Error
from ..index import FileIndex


@dataclass
class ErrorsAndWarningsWorkspace(StoredWorkspace):
    """Adds methods for handling errors and warnings."""

    _errors: List[Error] = field(default_factory=list)

    @property
    def errors(self) -> List[Error]:
        """All of the errors + warnings in the workspace."""
        return [error for u_file in self.files for error in u_file.errors] \
            + self._errors

    @property
    def fatal_errors(self) -> List[Error]:
        """All of the fatal errors on active files in the workspace."""
        return (
            [error for u_file in self.files for error in u_file.errors
             if u_file.is_active and error.severity is Error.Severity.FATAL]
            +
            [error for error in self._errors
             if error.severity is Error.Severity.FATAL]
        )

    @property
    def warnings(self) -> List[Error]:
        """Warnings for all files in the workspace."""
        return self._get_warnings()

    @property
    def active_warnings(self) -> List[Error]:
        """Warnings for active files only."""
        return self._get_warnings(is_active=True)

    def _get_warnings(self, is_active: Optional[bool] = None) -> List[Error]:
        return (
            [error for u_file in self.files for error in u_file.errors
             if error.severity is Error.Severity.WARNING
             and (is_active is None or u_file.is_active == is_active)]
            +
            [error for error in self._errors
             if error.severity is Error.Severity.WARNING]
        )

    def get_warnings_for_path(self, path: str,
                              is_ancillary: bool = False,
                              is_system: bool = False,
                              is_removed: bool = False) -> List[str]:
        u_file = self.files.get(path, is_ancillary=is_ancillary,
                                is_system=is_system, is_removed=is_removed)
        return [e.message for e in u_file.errors
                if e.severity is Error.Severity.WARNING]

    def add_error(self, u_file: UploadedFile, msg: str,
                  severity: Error.Severity = Error.Severity.FATAL,
                  is_persistant: bool = True) -> None:
        """Add an error for a specific file."""
        u_file.add_error(Error(severity=severity, path=u_file.path,
                               message=msg, is_persistant=is_persistant))

    def add_non_file_error(self, msg: str,
                           severity: Error.Severity = Error.Severity.FATAL,
                           is_persistant: bool = True) -> None:
        """Add an error for the workspace that is not specific to a file."""
        self._errors.append(Error(severity=severity, path=None, message=msg,
                                  is_persistant=is_persistant))

    def add_warning(self, u_file: UploadedFile, msg: str,
                    is_persistant: bool = True) -> None:
        """Add a warning for a specific file."""
        self.add_error(u_file, msg, severity=Error.Severity.WARNING,
                       is_persistant=is_persistant)

    def add_non_file_warning(self, msg: str,
                             is_persistant: bool = False) -> None:
        """Add a warning for the workspace that is not specific to a file."""
        self.add_non_file_error(msg, severity=Error.Severity.WARNING,
                                is_persistant=is_persistant)

    @property
    def has_warnings(self) -> bool:
        """Determine whether or not this workspace has warnings."""
        return len(self.warnings) > 0

    @property
    def has_active_warnings(self) -> bool:
        """Determine whether this workspace has warnings for active files."""
        return len(self.active_warnings) > 0

    @property
    def has_errors(self) -> bool:
        """Determine whether or not this workspace has errors."""
        return len(self.errors) > 0

    @property
    def has_fatal_errors(self) -> bool:
        return len(self.fatal_errors) > 0