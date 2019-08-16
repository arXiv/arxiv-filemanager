"""
Conversion of domain objects to/from native structs for persistence.

These are defined separately from the serialization functions that we use to
prepare workspace data for API responses. In the API case, we are only exposing
a subset of the information, and the naming/structure of the response documents
in somewhat different from our internal representation. In contrast, the goal
here is fidelity.
"""

from datetime import datetime
from typing import Dict, Any, TypeVar, Type, Optional, Iterable, Callable, cast

from dataclasses import dataclass, field
from typing_extensions import Protocol

from backports.datetime_fromisoformat import MonkeyPatch

from ..error import Error
from ..uploaded_file import UserFile
from ..file_type import FileType
from ..index import FileIndex
from .base import IBaseWorkspace

MonkeyPatch.patch_fromisoformat()


T = TypeVar('T', bound=IBaseWorkspace)


class IWorkspace(IBaseWorkspace, Protocol):
    """Workspace behavior required for :class:`.Translatable`."""


class ITranslatable(Protocol):
    """Interface for translatable behavior."""

    # Mypy notes correctly that the erased type of ``cls`` is not a superclass
    # of (I)Translatable. In practice this is not a problem, because we only
    # use (I)Translatable in conjunction with workspaces.
    @classmethod
    def from_dict(cls: Type[T], data: dict) -> T:  # type: ignore
        """Load a workspace from a dict representation."""

    def to_dict(self) -> Dict[str, Any]:
        """Generate a dict representation of a workspace."""


class ITranslatableWorkspace(IWorkspace, ITranslatable, Protocol):
    """Interface for workspace with translatable behavior."""


class IFromDictable(Protocol):
    """Supports loading constructor args from a dict."""

    @classmethod
    def args_from_dict(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Pluck object constructor args from a dict."""

    @classmethod    # See comment on ITranslatable.from_dict.
    def post_from_dict(cls: Type[T], workspace: T,      # type: ignore
                       data: Dict[str, Any]) -> None:
        """Update the object after it has been loaded from a dict."""


class IToDictable(Protocol):
    """Supports translating to dict."""

    @classmethod    # See comment on ITranslatable.from_dict.
    def to_dict_impl(cls: Type[T], workspace: T) -> Dict[str, Any]:  # type: ignore
        """Generate a dict representation of the object."""


@dataclass
class Translatable(ITranslatable):
    """Adds translation functionality to/from native Python structs."""

    __internal_api = None

    def __api_init__(self, api: IWorkspace) -> None:
        """Register the workspace API."""
        if hasattr(super(Translatable, self), '__api_init__'):
            super(Translatable, self).__api_init__(api)    # type: ignore
        self.__internal_api = api

    @property
    def __api(self) -> IWorkspace:
        """Accessor for the internal workspace API."""
        assert self.__internal_api is not None
        return self.__internal_api

    @classmethod    # See comment on ITranslatable, above.
    def from_dict(cls: Type[T], data: dict) -> T:  # type: ignore
        """Load a workspace from a dict representation."""
        args: Dict[str, Any] = {}
        for Interface in cls.mro():
            if hasattr(Interface, 'args_from_dict'):
                args.update(
                    cast(Type[IFromDictable], Interface).args_from_dict(data)
                )

        # Mypy doesn't like variant keys.
        workspace: T = cls(**args)  # type: ignore

        for Interface in cls.mro():
            if hasattr(Interface, 'post_from_dict'):
                cast(Type[IFromDictable], Interface).post_from_dict(
                    cast(IFromDictable, workspace), data
                )
        return workspace

    def to_dict(self) -> Dict[str, Any]:
        """Generate a dict representation of a workspace."""
        data: Dict[str, Any] = {}
        for Interface in self.__class__.mro()[::-1]:
            if hasattr(Interface, 'to_dict_impl'):
                data.update(cast(Type[IToDictable], Interface)
                            .to_dict_impl(cast(IToDictable, self)))
        return data
