"""Provides a struct for indexing file metadata."""

from typing import Iterable, Tuple, Optional, Dict, Iterator
from itertools import chain
from dataclasses import dataclass, field

from .uploaded_file import UploadedFile


class NoSuchFile(Exception):
    """An operation has been attempted on a non-existant file."""


@dataclass
class FileIndex:
    """
    Indexing struct for :class:`.UploadedFile`s.

    The overarching objective is to keep track of system, ancillary, removed,
    and source files without committing to an underlying path/filesystem
    structure. This helps us maintain flexibility around how we store files.
    """
    source: Dict[str, UploadedFile] = field(default_factory=dict)
    ancillary: Dict[str, UploadedFile] = field(default_factory=dict)
    removed: Dict[str, UploadedFile] = field(default_factory=dict)
    system: Dict[str, UploadedFile] = field(default_factory=dict)

    # def __post_init__(self) -> None:
    #     """Initialize with separate mappings for ancillary, system, etc."""
        

    def set(self, path: str, u_file: UploadedFile) -> None:
        """Add a :class:`.UploadedFile` to the index."""
        if u_file.is_system:
            self.system[path] = u_file
        elif u_file.is_removed:
            self.removed[path] = u_file
        elif u_file.is_ancillary:
            self.ancillary[path] = u_file
        else:
            self.source[path] = u_file

    def contains(self, path: str, is_ancillary: bool = False,
                 is_removed: bool = False, is_system: bool = False) -> bool:
        """Determine whether an :class:`.UploadedFile` exists at ``path``."""
        if is_system:
            return path in self.system
        if is_removed:
            return path in self.removed
        if is_ancillary:
            return path in self.ancillary
        return path in self.source

    def get(self, path: str, is_ancillary: bool = False,
            is_removed: bool = False, is_system: bool = False) \
            -> UploadedFile:
        """Get an :class:`.UploadedFile` exists at ``path``."""
        try:
            if is_system:
                return self.system[path]
            if is_removed:
                return self.removed[path]
            if is_ancillary:
                return self.ancillary[path]
            return self.source[path]
        except KeyError as e:
            raise NoSuchFile('No such file') from e

    def items(self, is_ancillary: bool = False, is_removed: bool = False,
              is_system: bool = False) -> Iterable[Tuple[str, UploadedFile]]:
        """Get an interator over (path, :class:`.UploadedFile`) tuples."""
        if is_system:
            return self.system.items()
        if is_removed:
            return self.removed.items()
        if is_ancillary:
            return self.ancillary.items()
        return self.source.items()

    def pop(self, path: str, is_ancillary: bool = False,
            is_removed: bool = False, is_system: bool = False) \
            -> Optional[UploadedFile]:
        """Pop the :class:`.UploadedFile` at ``path``."""
        if is_system:
            value = self.system.pop(path, None)
        elif is_removed:
            value = self.removed.pop(path, None)
        elif is_ancillary:
            value = self.ancillary.pop(path, None)
        else:
            value = self.source.pop(path, None)
        return value

    def __iter__(self) -> Iterator[UploadedFile]:
        """Get an interator over all :class:`.UploadedFile`s."""
        return chain(self.source.values(), self.ancillary.values(),
                     self.removed.values(), self.system.values())
