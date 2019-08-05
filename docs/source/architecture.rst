File management service architecture
####################################
The file management service is responsible for accepting, sanitizing, and 
making available user uploads for submission. This section provides a brief
overview of the architecture of the service.

For a general overview of the arXiv service architecture, see
:std:doc:`crosscutting/services`.

.. contents:: :depth: 3


Context
=======
The file management service is a part of the :std:doc:`submission subsystem
<architecture>`. This service is responsible for ensuring the safety and
suitability of files uploaded to the submission subsystem. The file management
service accepts uploads, performs verification and sanitization, and makes the
upload available for use by other services.

The file management service exposes a RESTful JSON-based API that is used by
various other services to update and access the source packages which can be
used to submit e-prints to arXiv.

.. note::
   
   Note the phrase "can be used," above. A source package in the file
   management service is agnostic about submissions. In fact, the file
   management service knows nothing about submissions *per se*. A source
   package may exist entirely without a submission. This allows us to imagine
   other kinds of workflows than the standard UI-driven workflows of the legacy
   system. This is especially useful to support API-based workflows or use of
   the compilation service outside the context of a submission.


Typical interactions with the file management service include:

- A human user may upload files via an intermediate interface, such as the
  submission UI.
- An API client may upload files directly to the file manager service, via the
  :ref:`ingress-api-gateway`.
- The `compiler service
  <https://arxiv.github.io/arxiv-compiler/architecture.html>`_
  retrieves uploaded content from the file manager service when it tries to
  compile PDFs.


Key requirements
================

1. Users/clients may upload files that are typical to e-print submissions, such
   as TeX sources, PDFs, ancillary files, etc.
2. Sanitize user/client uploads for use in other parts of the system. This
   includes normalizing filenames, looking for strange files, etc.
3. Check upload contents for errors that are common to e-print submissions.
4. Support adding, removing, and retrieving individual files by authorized 
   users/clients.
5. Uploads must be strongly isolated, so that strict authorization policies can
   be implemented and enforced. Uploaded files are grouped together into 
   workspaces, which provides a bounded context for all operations.
6. Allow authorized clients (e.g. system clients) to lock an upload workspace
   to prevent changes.
7. It must be possible for a client to determine whether or not a file or set 
   of files has changed. E.g. by exposing checksums of individual files and 
   the (tar-gzipped) source package.


Containers
==========
The file management service is implemented as a Flask web application.
The application relies on two storage systems:

1. A filesystem that can be shared among multiple instances of the application.
2. A database used to store workspace metadata, including ownership, 
   disposition of the most recent checks, etc.


.. code-block:: none

                +-----------------------+
                |File management service|
                +-+------------------+--+
                  |                  |
                  v                  v
   +--------------+--+           +---+---------------+
   |Shared filesystem|           |Relational database|
   |[AWS EFS]        |           |[AWS RDS: MariaDB] |
   +-----------------+           +-------------------+


Components
==========
The file management app follows the general :std:doc:`arXiv NG service design
<crosscutting/services>`.

Notionally, this looks something like:

.. code-block:: none

                                   +-----+
                                   |uWSGI|
                                   +--+--+
                                      v
                           +----------+-----------+
                           |         wsgi         |
                           |          v           |
                           |       factory        |
                           |          v           |
                           |        routes        |
                           |          v           |
                           |      controllers     |
                           |      v   |     v     |
                           | storage  |  database |
           +---------------+ service  |  service  +--------------+
           |               |       v  v  v        |              |
   +-------v---------+     |        domain        |   +----------v--------+
   |Shared filesystem|     +----------------------+   |Relational database|
   |[AWS EFS]        |                                |[AWS RDS: MariaDB] |
   +-----------------+                                +-------------------+


Domain
------
The core concept of the file management service is the
:class:`.UploadWorkspace`, which represents a collection of files (e.g. what
would be used as the source package for a submission and/or compilation), along
with attendant logs, metadata, and other ephemera used to track the state and
disposition of the workspace. The workspace contains :class:`.UploadedFile`
instances, which are organized into source files, ancillary files, etc using a
:class:`.FileIndex`.

Operations on files
'''''''''''''''''''
The workspace abstracts away the underlying storage model, providing an API
that focuses on common transformations on files (e.g. adding, removing,
renamed, etc). It provides a slot, :attr:`.UploadWorkspace.storage` into which
can be fitted a storage adapter that implements the :class:`.IStorageAdapter`
protocol.

See :class:`.FileMutationsMixin`, :class:`.PathsMixin`, and 
:class:`.FileStaticOperationsMixin` for details.

File and workspace checks
'''''''''''''''''''''''''
One of the most important functionalities of the service is performing
sanitization of files uploaded by external (untrusted) users/clients. The
workspace accepts :attr:`.UploadWorkspace.checkers` (containing objects that
implement :class:`.IChecker`) and a `.UploadWorkspace.checking_strategy` (an
object that implements :class:`.ICheckingStrategy`) that power the
:meth:`.ChecksMixin.perform_checks` routine.


Processes: file and workspace checks
------------------------------------
The :mod:`.process` module contains implementations of :class:`.IChecker` and 
:class:`.ICheckingStrategy`, which together comprise the sanitization and 
checks logic of the file management service.

Checkers are implemented in :mod:`.process.check`. Each checker extends 
:class:`.BaseChecker`, and implements any of the following file checking 
methods (which are applied in this order):

- ``check(UploadWorkspace, UploadedFile) -> UploadedFile:``, which is called
  for all files, regardless of type.
- ``check_tex_types(UploadWorkspace, UploadedFile) -> UploadedFile:``, which is
  called for TeX-related file types (see :meth:`.FileType.is_tex_type`).
- ``check_{TYPE}(UploadWorkspace, UploadedFile) -> UploadedFile:``, which is 
  called only for files of the corresponding :class:`.FileType` (indicated by
  :attr:`.UploadedFile.file_type`), 
- ``check_finally(UploadWorkspace, UploadedFile) -> UploadedFile:``, which is 
  called for all files, regardless of type, after all of the checks above have
  been applied.

In addition, a checker may implement ``check_workspace(UploadWorkspace) ->
None:``, which is called on the workspace after all file checks are applied.

Checks are applied to a workspace by a checking strategy, found in in
:mod:`.process.strategy` and implementing :class:`.ICheckingStrategy`. The
current default strategy is the :class:`.SynchronousCheckingStrategy`, which
checks files one at a time.

Note that :class:`.UploadedFile` has a property
:attr:`.UploadedFile.is_checked`, which the checking strategy may use to avoid
applying the same checks to a file more than once.


Database service
----------------
The :mod:`.services.database` module provides the primary API for loading 
and storing the state of the :class:`.UploadWorkspace`. The database itself
(backed by MariaDB in production) stores the workspace metadata, including 
its status, readiness, lock state, and the disposition of all of its files.

When a workspace is loaded via :func:`.database.retrieve`, a storage adapter
(implementing :class:`.IStorageAdapter`) is instantiated based on the
configuration of the app, and attached to the workspace as
:attr:`.UploadWorkspace.storage`. The workspace uses its storage adapter to
carry out file operations.


Storage adapters
----------------
Storage adapters are found in :mod:`.services.storage`, and implement
:class:`.IStorageAdapter`. There are currently two adapters:

- :class:`.SimpleStorageAdapter` uses a single volume; files are uploaded, 
  checked/transformed, and stored in the same volume.
- :class:`.QuarantineStorageAdapter` uses two volumes; files are uploaded and
  checked/transformed in one volume, and stored in another.

The property :attr:`.UploadedFile.is_persisted` denotes whether or not the file
is persisted beyond the lifetime of the client request.
:meth:`.FileMutationsMixin.persist` can be used to persist files. It is up to
the underlying storage adapter to decide what that means.


Controllers & routes
--------------------
For details on request controllers and routes, see :mod:`.controllers` and 
:mod:`.routes`, respectively.