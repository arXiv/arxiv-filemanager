"""
Provides :class:`.UploadWorkspace`, the organizing concept for this service.

Because :class:`.UploadWorkspace` has many properties and methods, its
members are split out into separate classes.

- :class:`.BaseWorkspace` provides the file index, and foundational methods.
- :class:`.FilePathsWorkspace` adds methods for working with paths inside
  the workspace.
- :class:`.StoredWorkspace` adds integration with a storage adapter.
- :class:`.FileMutationsWorkspace` adds methods for manipulating individual
  files.
- :class:`.CheckpointWorkspace` adds workspace checkpointing and restore.
- :class:`.CheckableWorkspace` adds slots for checkers and checking strategy,
  and methods for performing checks. It also adds:

  - :class:`.SourceTypeMixin`, which adds a representation of the submission
    source upload type.
  - :class:`.CountableWorkspace`, which adds methods for counting files and
    types of files.

- :class:`.UploadWorkspace` extends :class:`.CheckableWorkspace` to add an
  initialization method, and also incorporates:

  - :class:`.ReadinessWorkspace`, which adds semantics around the "readiness"
    of the workspace for use in a submission.
  - :class:`.SingleFileWorkspace`, which adds the concept of a "single file
    submission."
  - :class:`.LockMixin`, which adds support for locking/unlocking the
    workspace.
  - :class:`.StatusMixin`, which adds the concept of a workspace status.


"""

from typing import List, Optional, Iterable, Tuple, Union
from enum import Enum
from datetime import datetime

from typing_extensions import Protocol
from dataclasses import dataclass, field

from ..file_type import FileType
from ..uploaded_file import UploadedFile
from ..error import Error
from ..index import FileIndex

from .file_mutations import SourceLog, SourcePackage
from .checkpoint import CheckpointWorkspace
from .stored import IStorageAdapter, StoredWorkspace
from .checkable import CheckableWorkspace, IChecker, ICheckingStrategy
from .lock import LockMixin
from .readiness import ReadinessWorkspace
from .single_file import SingleFileWorkspace
from .status import StatusMixin
from .util import modifies_workspace, logger


@dataclass
class UploadWorkspace(ReadinessWorkspace, SingleFileWorkspace, LockMixin,
                      StatusMixin, CheckableWorkspace):
    """An upload workspace contains a set of submission source files."""


    def __post_init__(self) -> None:
        """Mark the workspace as uninitialized."""
        self._initialized = False

    @property
    def is_initialized(self) -> bool:
        """Determine whether or not the workspace has been initialized."""
        return self._initialized

    def initialize(self) -> None:
        """
        Make sure that we have all of the required directories.

        This is performed on demand, rather than as a ``__post_init__`` hook,
        so that we have an opportunity to attach an updated :class:`.FileIndex`
        after the :class:`.UploadWorkspace` is instantiated but before any
        system files are created.
        """
        if self.storage is None:
            raise RuntimeError('Storage adapter is not set')
        self.storage.makedirs(self, self.source_path)
        self.storage.makedirs(self, self.ancillary_path)
        self.storage.makedirs(self, self.removed_path)
        super(UploadWorkspace, self).initialize()
        self._initialized = True





