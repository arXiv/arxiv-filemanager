"""Provides checking functionality to the workspace."""

from typing import List, Optional, Any, Callable, cast

from dataclasses import field, dataclass
from typing_extensions import Protocol

from ..uploaded_file import UserFile
from .base import IBaseWorkspace
from .util import modifies_workspace


class IChecker(Protocol):
    """A visitor that performs a check on an :class:`.UserFile`."""

    def __call__(self, workspace: Any, u_file: UserFile) -> UserFile:
        """Check an :class:`.UserFile`."""
        ...

    def check_workspace(self, workspace: Any) -> None:
        """Check the workspace as a whole."""
        ...


class ICheckingStrategy(Protocol):
    """Strategy for checking files in a workspace."""

    def check(self, workspace: Any, *checkers: IChecker) -> None:
        """Perform checks on all files in the workspace using ``checkers``."""
        ...


class IWorkspace(IBaseWorkspace, Protocol):
    """
    Workspace API required for :class:`.Checkable`.

    This incorporates the base API and any additional structures that require
    implementation by other components of the workspace.
    """


class ICheckable(Protocol):
    """Interface for checkable behavior."""

    checkers: List['IChecker']

    @property
    def has_unchecked_files(self) -> bool:
        """Determine whether there are unchecked files in this workspace."""

    # Preferably ``strategy`` would just be an attribute ``strategy:
    # 'ICheckingStrategy'``, but see https://github.com/python/mypy/issues/4125
    @property
    def strategy(self) -> 'ICheckingStrategy':
        """Checking strategy for the workspace."""

    # Known bugs in mypy:
    # - https://github.com/python/mypy/issues/5936
    # - https://github.com/python/mypy/issues/4644
    # - https://github.com/python/mypy/issues/1465
    # Probably also related to https://github.com/python/mypy/issues/4125.
    # @strategy.setter    # type: ignore
    def set_strategy(self, strategy: 'ICheckingStrategy') -> None:
        """Set the strategy for this workspace."""

    def perform_checks(self) -> None:
        """Perform all checks on this workspace using the assigned strategy."""


class ICheckableWorkspace(IWorkspace, ICheckable):
    """Joint API for a workspace that incorporates :class:`ICheckable`."""


@dataclass
class Checkable(ICheckable):
    """Adds checking functionality."""

    checkers: List['IChecker'] = field(default_factory=list)
    """File checkers that should be applied to all files in the workspace."""

    _strategy: Optional['ICheckingStrategy'] = field(default=None)
    """Strategy for performing file checks."""

    __internal_api = None

    def __api_init__(self, api: IWorkspace) -> None:
        """Register the workspace API."""
        if hasattr(super(Checkable, self), '__api_init__'):
            super(Checkable, self).__api_init__(api)   # type: ignore
        self.__internal_api = api

    @property
    def __api(self) -> 'IWorkspace':
        assert self.__internal_api is not None
        return self.__internal_api

    @property
    def has_unchecked_files(self) -> bool:
        """Determine whether there are unchecked files in this workspace."""
        for u_file in self.__api.iter_files(allow_directories=True):
            if not u_file.is_checked:
                return True
        return False

    # This is here so that we don't have to do a null-check on ``_strategy``
    # every time.
    @property
    def strategy(self) -> 'ICheckingStrategy':
        if self._strategy is None:
            raise RuntimeError('No checking strategy set')
        return self._strategy

    # Known bugs in mypy:
    # - https://github.com/python/mypy/issues/5936
    # - https://github.com/python/mypy/issues/4644
    # - https://github.com/python/mypy/issues/1465
    # Probably also related to https://github.com/python/mypy/issues/4125.
    # @strategy.setter    # type: ignore
    def set_strategy(self, strategy: 'ICheckingStrategy') -> None:
        """Set the strategy for this workspace."""
        self._strategy = strategy

    def perform_checks(self) -> None:
        """Perform all checks on this workspace using the assigned strategy."""
        self.strategy.check(self, *self.checkers)

