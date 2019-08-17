"""Provides :class:`.ErrorsAndWarnings`."""

from typing import List, Optional, Any, Iterator, Dict, Callable, Tuple, cast

from dataclasses import dataclass, field
from typing_extensions import Protocol

from ..uploaded_file import UserFile
from ..error import Error, Code, Severity
from ..index import FileIndex
from .base import IBaseWorkspace


class IWorkspace(IBaseWorkspace, Protocol):
    """
    Workspace API required for :class:`.ErrorsAndWarnings`.

    This incorporates the base API and any additional structures that require
    implementation by other components of the workspace.
    """


class IErrorsAndWarnings(Protocol):
    """Interface for errors and warnings behavior."""

    @property
    def errors(self) -> List[Error]:
        """All of the errors + warnings in the workspace."""

    @property
    def errors_fatal(self) -> List[Error]:
        """All of the fatal errors on active files in the workspace."""

    @property
    def has_errors(self) -> bool:
        """Determine whether or not this workspace has errors."""

    @property
    def has_errors_fatal(self) -> bool:
        """Determine whether or not this workspace has fatal errors."""

    @property
    def has_warnings(self) -> bool:
        """Determine whether or not this workspace has warnings."""

    @property
    def has_warnings_active(self) -> bool:
        """Determine whether this workspace has warnings for active files."""

    @property
    def warnings(self) -> List[Error]:
        """Warnings for all files in the workspace."""

    @property
    def warnings_active(self) -> List[Error]:
        """Warnings for active files only."""

    def add_error(self, u_file: UserFile, code: Code, msg: str,
                  severity: Severity = Severity.FATAL,
                  is_persistant: bool = True) -> None:
        """Add an error for a specific file."""

    def add_error_non_file(self, code: Code, msg: str,
                           severity: Severity = Severity.FATAL,
                           is_persistant: bool = True) -> None:
        """Add an error for the workspace that is not specific to a file."""

    def add_warning(self, u_file: UserFile, code: Code, msg: str,
                    is_persistant: bool = True) -> None:
        """Add a warning for a specific file."""

    def add_warning_non_file(self, code: Code, msg: str,
                             is_persistant: bool = False) -> None:
        """Add a warning for the workspace that is not specific to a file."""

    def get_warnings(self, path: str,
                     is_ancillary: bool = False,
                     is_system: bool = False,
                     is_removed: bool = False) -> List[str]:
        """Get all warnings for the file at ``path``."""

    def remove_error(self, code: Code, path: Optional[str] = None) -> None:
        """Remove an error."""


class IErrorsAndWarningsWorkspace(IWorkspace, IErrorsAndWarnings, Protocol):
    """Interface for workspace with errors and warnings behavior."""

Path = Optional[str]

@dataclass
class ErrorsAndWarnings(IErrorsAndWarnings):
    """Adds methods for handling errors and warnings."""

    # _errors: List[Error] = field(default_factory=list)
    _errors: Dict[Tuple[Path, Code], Error] = field(default_factory=dict)

    __internal_api = None

    def __api_init__(self, api: IWorkspace) -> None:
        """Register the workspace API."""
        if hasattr(super(ErrorsAndWarnings, self), '__api_init__'):
            super(ErrorsAndWarnings, self).__api_init__(api)    # type: ignore
        self.__internal_api = api

    @property
    def __api(self) -> IWorkspace:
        """Accessor for the internal workspace API."""
        assert self.__internal_api is not None
        return self.__internal_api

    # This is a classmethod so that it can be accessed and utilized separately
    # from methods with the same name in other mixed-in classes.
    @classmethod
    def post_from_dict(cls, workspace: 'ErrorsAndWarnings',
                       data: Dict[str, Any]) -> None:
        """Update the workspace after loading from dict."""
        _errors = data.get('errors')
        if _errors:
            for datum in _errors:
                e = Error.from_dict(datum)
                # The protected access is safe, given that this is for all
                # intents and purposes an instancemethod without instance
                # binding.
                # workspace._errors.append(e)  # pylint: disable=protected-access
                workspace._errors[(e.path, e.code)] = e  # pylint: disable=protected-access

    @classmethod    # See comment for post_from_dict, above.
    def to_dict_impl(cls, self: 'ErrorsAndWarnings') -> Dict[str, Any]:
        """Generate a dict representation of errors."""
        # See comment above.
        return {'errors': [e.to_dict() for e in self._errors.values()  # pylint: disable=protected-access
                if e.is_persistant]}

    @property
    def errors(self) -> List[Error]:
        """All of the errors + warnings in the workspace."""
        return self._errors_files + list(self._errors.values())

    @property
    def errors_fatal(self) -> List[Error]:
        """All of the fatal errors on active files in the workspace."""
        return self._errors_fatal_files + self._errors_fatal

    @property
    def has_errors(self) -> bool:
        """Determine whether or not this workspace has errors."""
        return len(self.errors) > 0

    @property
    def has_errors_fatal(self) -> bool:
        """Determine whether or not this workspace has fatal errors."""
        return len(self.errors_fatal) > 0

    @property
    def has_warnings(self) -> bool:
        """Determine whether or not this workspace has warnings."""
        return len(self.warnings) > 0

    @property
    def has_warnings_active(self) -> bool:
        """Determine whether this workspace has warnings for active files."""
        return len(self.warnings_active) > 0

    @property
    def warnings(self) -> List[Error]:
        """Warnings for all files in the workspace."""
        return self._get_warnings()

    @property
    def warnings_active(self) -> List[Error]:
        """Warnings for active files only."""
        return self._get_warnings(is_active=True)

    @property
    def _errors_files(self) -> List[Error]:
        return [e for u_file in self.__api.files for e in u_file.errors]

    @property
    def _errors_fatal_files(self) -> List[Error]:
        return [e for u_file in self.__api.files for e in u_file.errors
                if u_file.is_active and e.is_fatal]

    @property
    def _errors_fatal(self) -> List[Error]:
        return [e for e in self._errors.values() if e.is_fatal]

    @property
    def _warnings(self) -> List[Error]:
        return [e for e in self._errors.values() if e.is_warning]

    def add_error(self, u_file: UserFile, code: Code, msg: str,
                  severity: Severity = Severity.FATAL,
                  is_persistant: bool = True) -> None:
        """Add an error for a specific file."""
        e = Error(severity=severity, path=u_file.path, code=code,
                  message=msg, is_persistant=is_persistant)
        u_file.add_error(e)

    def remove_error(self, code: Code, path: Optional[str] = None) -> None:
        if path is None:
            self._remove_error(code, path)
        else:
            self.__api.get(path).remove_error(code)


    def add_error_non_file(self, code: Code, msg: str,
                           severity: Severity = Severity.FATAL,
                           is_persistant: bool = True) -> None:
        """Add an error for the workspace that is not specific to a file."""
        self._insert_error(Error(severity=severity, path=None, code=code,
                           message=msg, is_persistant=is_persistant))

    def add_warning(self, u_file: UserFile, code: Code, msg: str,
                    is_persistant: bool = True) -> None:
        """Add a warning for a specific file."""
        self.add_error(u_file, code, msg, severity=Severity.WARNING,
                       is_persistant=is_persistant)

    def add_warning_non_file(self, code: Code, msg: str,
                             is_persistant: bool = False) -> None:
        """Add a warning for the workspace that is not specific to a file."""
        self.add_error_non_file(code, msg, severity=Severity.WARNING,
                                is_persistant=is_persistant)

    def get_warnings(self, path: str,
                     is_ancillary: bool = False,
                     is_system: bool = False,
                     is_removed: bool = False) -> List[str]:
        """Get all warnings for the file at ``path``."""
        u_file = self.__api.files.get(path, is_ancillary=is_ancillary,
                                      is_system=is_system,
                                      is_removed=is_removed)
        return [e.message for e in u_file.errors
                if e.severity is Severity.WARNING]

    def _get_warnings(self, is_active: Optional[bool] = None) -> List[Error]:
        return self._get_warnings_file(is_active) + self._warnings

    def _get_warnings_file(self, is_active: Optional[bool]) -> List[Error]:
        return [e for u_file in self.__api.files for e in u_file.errors
                if e.is_warning
                and (is_active is None or u_file.is_active == is_active)]

    def _insert_error(self, error: Error) -> None:
        # pylint doesn't know that dataclasses is initializing this with a
        # dict.
        self._errors[(error.path, error.code)] = error  # pylint: disable=unsupported-assignment-operation

    def _remove_error(self, code: Code, path: Optional[str] = None) -> None:
        self._errors.pop((path, code), None)
