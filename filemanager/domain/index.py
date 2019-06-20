"""Provides a struct for indexing file metadata."""

from typing import Iterable, Tuple, Optional
from itertools import chain


class FileIndex:
    """
    Indexing struct for :class:`.UploadedFile`s.

    The overarching objective is to keep track of system, ancillary, removed,
    and source files without committing to an underlying path/filesystem
    structure. This helps us maintain flexibility around how we store files.
    """

    def __init__(self) -> None:
        """Initialize with separate mappings for ancillary, system, etc."""
        self.source = {}
        self.ancillary = {}
        self.removed = {}
        self.system = {}

    def set(self, path: str, u_file: 'UploadedFile') -> None:
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
            -> 'UploadedFile':
        """Get an :class:`.UploadedFile` exists at ``path``."""
        if is_system:
            return self.system[path]
        if is_removed:
            return self.removed[path]
        if is_ancillary:
            return self.ancillary[path]
        return self.source[path]

    def items(self, is_ancillary: bool = False, is_removed: bool = False,
              is_system: bool = False) -> Iterable[Tuple[str, 'UploadedFile']]:
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
            -> Optional['UploadedFile']:
        """Pop the :class:`.UploadedFile` at ``path``."""
        if is_system:
            return self.system.pop(path, None)
        if is_removed:
            return self.removed.pop(path, None)
        if is_ancillary:
            return self.ancillary.pop(path, None)
        return self.source.pop(path, None)

    def __iter__(self) -> Iterable['UploadedFile']:
        """Get an interator over all :class:`.UploadedFile`s."""
        return chain(self.source.values(), self.ancillary.values(),
                     self.removed.values(), self.system.values())
