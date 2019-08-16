"""Provides :class:`.CountsMixin`."""

from collections import Counter
from typing import List, Union, Mapping, Dict, Optional, Any, Callable, cast

from dataclasses import dataclass, field
from typing_extensions import Protocol

from ..file_type import FileType
from ..uploaded_file import UserFile

from .base import IBaseWorkspace


class IWorkspace(IBaseWorkspace, Protocol):
    """
    Workspace API required for :class:`.Countable`.

    This incorporates the base API and any additional structures that require
    implementation by other components of the workspace.
    """


class ICountable(Protocol):
    """Interface for countable behavior."""

    @property
    def ancillary_file_count(self) -> int:
        """Get the total number of ancillary files in this workspace."""

    @property
    def file_count(self) -> int:
        """Get the total number of non-ancillary files in this workspace."""

    def get_file_type_counts(self) -> Mapping[Union[FileType, str], int]:
        """Get the number of files of each type in the workspace."""


class ICountableWorkspace(IWorkspace, ICountable, Protocol):
    """Structure of a workspace with countable behavior."""


@dataclass
class Countable(ICountable):
    """Adds methods related to file counts."""

    __internal_api = None

    def __api_init__(self, api: IWorkspace) -> None:
        """Register the workspace API."""
        if hasattr(super(Countable, self), '__api_init__'):
            super(Countable, self).__api_init__(api)   # type: ignore
        self.__internal_api = api

    @property
    def __api(self) -> IWorkspace:
        assert self.__internal_api is not None
        return self.__internal_api

    @property
    def ancillary_file_count(self) -> int:
        """Get the total number of ancillary files in this workspace."""
        files = self.__api.iter_files(allow_ancillary=True,
                                      allow_removed=False)
        return len([f for f in files if f.is_ancillary])

    @property
    def file_count(self) -> int:
        """Get the total number of non-ancillary files in this workspace."""
        return len(self.__api.iter_files(allow_ancillary=False))

    def get_file_type_counts(self) -> Mapping[Union[FileType, str], int]:
        """Get the number of files of each type in the workspace."""
        counts: Dict[Union[FileType, str], int] = Counter()
        for u_file in self.__api.iter_files():
            counts['all_files'] += 1
            if u_file.is_ancillary:
                counts['ancillary'] += 1
                continue
            elif u_file.is_always_ignore:
                counts['ignore'] += 1
                continue
            counts[u_file.file_type] += 1
        counts['files'] = counts['all_files'] - counts['ancillary']
        return counts