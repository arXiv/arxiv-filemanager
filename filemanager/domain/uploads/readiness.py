"""Provides :class:`.ReadinessMixin`."""

from enum import Enum
from typing import Any, Dict, Optional, Callable, cast

from dataclasses import dataclass, field
from typing_extensions import Protocol

from .base import IBaseWorkspace


class Readiness(Enum):
    """
    Upload workspace readiness states.

    Provides an indication (but not the final word) on whether the
    workspace is suitable for incorporating into a submission to arXiv.
    """

    READY = 'READY'
    """Overall state of workspace is good; no warnings/errors reported."""

    READY_WITH_WARNINGS = 'READY_WITH_WARNINGS'
    """
    Workspace is ready, but there are warnings for the user.

    Upload processing reported warnings which do not prohibit client
    from continuing on to compilation and submit steps.
    """

    ERRORS = 'ERRORS'
    """
    There were errors reported while processing upload files.

    Subsequent steps [compilation, submit, publish] should reject working
    with such an upload package.
    """


class IWorkspace(IBaseWorkspace, Protocol):
    """
    Workspace API required for :class:`.Readiable`.

    This incorporates the base API and any additional structures that require
    implementation by other components of the workspace.
    """

    @property
    def has_errors_fatal(self) -> bool:
        """Determine whether or not this workspace has fatal errors."""

    @property
    def has_warnings_active(self) -> bool:
        """Determine whether this workspace has warnings for active files."""


class IReadiable(Protocol):
    """Interface for readiable behavior."""

    last_upload_readiness: 'Readiness'

    @property
    def readiness(self) -> 'Readiness':
        """Readiness state of the upload workspace."""


class IReadiableWorkspace(IWorkspace, IReadiable, Protocol):
    """Interface for workspace with readiable behavior."""


@dataclass
class Readiable(IReadiable):
    """Adds methods and properties releated to source readiness."""

    last_upload_readiness: Readiness = field(default=Readiness.READY)
    """Content readiness status after last upload event."""

    __internal_api = None

    def __api_init__(self, api: IWorkspace) -> None:
        """Register the workspace API."""
        if hasattr(super(Readiable, self), '__api_init__'):
            super(Readiable, self).__api_init__(api)    # type: ignore
        self.__internal_api = api

    @property
    def __api(self) -> IWorkspace:
        assert self.__internal_api is not None
        return self.__internal_api

    @property
    def readiness(self) -> 'Readiness':
        """Readiness state of the upload workspace."""
        if self.__api.has_errors_fatal:
            return Readiness.ERRORS
        elif self.__api.has_warnings_active:
            return Readiness.READY_WITH_WARNINGS
        return Readiness.READY

    @classmethod
    def to_dict_impl(cls, self: 'Readiable') -> Dict[str, Any]:
        """Generate a dict representation of the workspace."""
        return {'last_upload_readiness': self.last_upload_readiness.value}

    @classmethod
    def args_from_dict(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Pluck workspace constructor args from a dict."""
        args: Dict[str, Any] = {}
        last_upload_readiness = data.get('last_upload_readiness')
        if last_upload_readiness is not None:
            args['last_upload_readiness'] = Readiness(last_upload_readiness)
        return args