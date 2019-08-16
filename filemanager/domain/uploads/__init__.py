"""
Provides :class:`.Workspace`, the organizing concept for this service.

Because :class:`.Workspace` has many properties and methods, its members are
split out into separate classes.

- :class:`.BaseWorkspace` provides the file index, and foundational methods
  for working with :class:`.UserFile`s and their paths.
- :class:`.FileMutations` adds methods for manipulating individual files.
- :class:`.Checkpointable` adds workspace checkpointing and restore.
- :class:`.Checkable` adds slots for checkers and checking strategy, and
  methods for performing checks.
- :class:`.SourceTypeable` adds a representation of the submission source
  upload type.
- :class:`.Countable` adds methods for counting files and types of files.
- :class:`.Workspace` extends :class:`.Checkable` to add an initialization
  method.
- :class:`.Readiable`, which adds semantics around the "readiness" of the
   workspace for use in a submission.
- :class:`.SingleFile`, which adds the concept of a "single file submission."
- :class:`.Lockable`, which adds support for locking/unlocking the workspace.
- :class:`.Statusable`, which adds the concept of a workspace status.

How to implement new functionality in the workspace
===================================================

Each of the classes mentioned above are "mixins" that contribute to the
functionality of :class:`.Workspace`. The best way to become familiar with how
to write new functionality is to look at the existing mixins. A few things to
observe:

- Protocols (structural typing) are used to define interfaces. You can read
  about the current state of protocols in the `mypy documentation
  <https://mypy.readthedocs.io/en/latest/protocols.html>`_. `PEP 544
  <https://www.python.org/dev/peps/pep-0544/>`_ provides the detailed
  specification.
- Each mixin class is a ``dataclass``.
- The mixins do *not* inherit from :class:`.BaseWorkspace`; they access the
  base workspace functionality and functionality provided by other mixins via
  an internal API (see below).
- For each mixin, an interface is defined for:

  - The workspace API upon which the mixin depends. These are attributes,
    properties, methods provided by either :class:`.BaseWorkspace` or other
    mixins that are required for the mixin to do its job. This is usually
    called ``IWorkspace``, and builds on :class:`.IBaseWorkspace``.
  - The API provided by the mixin itself, usually called ``I[Mixin]``.
  - The API of a workspace with the mixin mixed in, usually called
    ``I[Mixin]Workspace``.

- The mixin class itself inherits from its interface (``IMixin``).


Each mixin accesses the API of the rest of the workspace via a special
protected property called ``__api``. This is defined on each mixin. For
example:

.. code-block:: python

   @dataclass
   class Bounceable(IBounceable):
       # Note that this is not typed; this way dataclasses will ignore it.
       # The double-underscores are used to ensure that this attribute belongs
       # specifically to this class (and doesn't get clobbered by other
       # mixins).
       __internal_api = None

       # This method is called by Workspace right after construction, and
       # registers the final workspace instance as the internal workspace API.
       # Note that it is typed as ``IWorkspace``, which is the interface
       # that defines the external functionality upon which this mixin depends.
       def __api_init__(self, api: IWorkspace) -> None:
           '''Register the workspace API.'''
           if hasattr(super(Bounceable, self), '__api_init__'):
               super(Bounceable, self).__api_init__(api)   # type: ignore
           self.__internal_api = api

       # Since ``__internal_api`` is ``None`` until runtime, this property
       # saves us the hassle of having to perform a null check every time we
       # want to use the workspace API.
       @property
       def __api(self) -> 'IWorkspace':
           '''Get the internal workspace API.'''
           assert self.__internal_api is not None
           return self.__internal_api

"""

from datetime import datetime
from enum import Enum
from typing import List, Optional, Iterable, Tuple, Union, Any

from attrdict import AttrDict
from dataclasses import dataclass, field
from typing_extensions import Protocol

from ..error import Error
from ..file_type import FileType
from ..index import FileIndex
from ..uploaded_file import UserFile

from .base import BaseWorkspace, IStorageAdapter
from .checkable import Checkable, IChecker, ICheckingStrategy, \
    ICheckableWorkspace
from .checkpoint import Checkpointable
from .countable import Countable
from .errors_and_warnings import ErrorsAndWarnings
from .file_mutations import SourceLog, SourcePackage, FileMutations
from .lock import Lockable, LockState
from .readiness import Readiable, Readiness
from .single_file import SingleFile
from .source_type import SourceTypeable, SourceType
from .status import Statusable, Status
from .translatable import Translatable
from .util import modifies_workspace, logger


# Mypy is getting hung up on protected double-underscore members. This is
# probably a bug in mypy.
@dataclass    # type: ignore
class Workspace(ErrorsAndWarnings,
                      Translatable,
                      FileMutations,
                      Readiable,
                      Countable,
                      Checkpointable,
                      Checkable,
                      SourceTypeable,
                      Statusable,
                      Lockable,
                      SingleFile,
                      BaseWorkspace):
    """An upload workspace contains a set of submission source files."""

    interfaces: AttrDict = field(default_factory=AttrDict)
    _initialized: bool = field(default=False)

    def __post_init__(self) -> None:
        """Register all interfaces in the API."""
        if hasattr(super(Workspace, self), '__api_init__'):
            super(Workspace, self).__api_init__(self)

    @property
    def is_initialized(self) -> bool:
        """Determine whether or not the workspace has been initialized."""
        return self._initialized

    def initialize(self) -> None:
        """
        Make sure that we have all of the required directories.

        This is performed on demand, rather than as a ``__post_init__`` hook,
        so that we have an opportunity to attach an updated :class:`.FileIndex`
        after the :class:`.Workspace` is instantiated but before any
        system files are created.
        """
        self.storage.makedirs(self, self.source_path)
        self.storage.makedirs(self, self.ancillary_path)
        self.storage.makedirs(self, self.removed_path)
        super(Workspace, self).initialize()
        self._initialized = True





