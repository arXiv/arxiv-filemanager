"""Provides :class:`.SingleFileMixin`."""

from typing import List, Union, Mapping, Optional, Any, Callable, cast

from dataclasses import dataclass, field
from typing_extensions import Protocol

from ..file_type import FileType
from ..uploaded_file import UserFile
from .base import IBaseWorkspace


class IWorkspace(IBaseWorkspace, Protocol):
    """Workspace functionality required by :class:`SingleFile`."""

    @property
    def file_count(self) -> int:
        """The total number of non-ancillary files in this workspace."""

    def get_file_type_counts(self) -> Mapping[Union[FileType, str], int]:
        """Get the number of files of each type in the workspace."""


class ISingleFile(Protocol):
    """Interface for single file behavior."""

    @property
    def is_single_file_submission(self) -> bool:
        """Indicate whether or not this is a valid single-file submission."""

    def get_single_file(self) -> Optional[UserFile]:
        """Get the primary source file for single-file submission."""


class ISingleFileWorkspace(IBaseWorkspace, ISingleFile, Protocol):
    """Interface for workspace with single file behavior."""


@dataclass
class SingleFile(ISingleFile):
    """Adds methods related to single-file source packages."""

    __internal_api = None

    def __api_init__(self, api: IWorkspace) -> None:
        """Register the workspace API."""
        if hasattr(super(SingleFile, self), '__api_init__'):
            super(SingleFile, self).__api_init__(api)   # type: ignore
        self.__internal_api = api

    @property
    def __api(self) -> IWorkspace:
        assert self.__internal_api is not None
        return self.__internal_api

    @property
    def is_single_file_submission(self) -> bool:
        """Indicate whether or not this is a valid single-file submission."""
        if self.__api.file_count != 1:
            return False
        counts = self.__api.get_file_type_counts()
        if counts['ignore'] == 1:
            return False
        return True

    def get_single_file(self) -> Optional[UserFile]:
        """
        Return File object for single-file submission.

        This routine is intended for submission that are composed of a single
        content file.

        Single file can't be type 'ancillary'. Single ancillary file is invalid
        submission and generates an error.

        Returns
        -------
        :class:`.UserFile` or ``None``
            Single file. Returns None when submission has more than one file.

        """
        if self.is_single_file_submission:
            for u_file in self.__api.iter_files(allow_ancillary=False):
                return u_file    # Return the first file.
        return None