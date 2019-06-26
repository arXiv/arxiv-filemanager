# Decision log for arXiv file manager service

Initial design decisions:

- File checks are fast enough to run synchronously in a request context; there
  is no need for an asynchronous worker.
- In order to scale horizontally, this app must have a shared filesystem. We 
  will use something like Elastic File Store for this purpose.

## 2019-06-26 Refactor of initial implementation

The initial implementation of the file manager service focused on replicating 
the behavior of the legacy file checks, and so closely reproduced much of the 
logic and abstractions. This implementation was quite fast in local tests,
correct, and had excellent test coverage over known problematic uploads.

### Problem: EFS I/O is too slow to run checks

EFS I/O limits scale with overall volume size, which makes things difficult
from the start. But even if we provision a high level of I/O ahead of time, 
there are too many low-level reads and writes to perform file checks on EFS 
directly. A modestly sized tarball could take around 12 seconds to unpack and 
check, which is not acceptable.

So we decided that we need to refactor the application to perform checks on a
local disk (e.g. in memory), and then move files over to EFS at the end of the
request. This way we are keeping I/O to a minimum.

### Problem: the core checking and file-shuffling routines were too complex

Because the initial implementation stuck closely to the logic of the legacy 
system, the file management and checking logic had grown to nearly 3,000 lines
largely contained in a single class, with really long methods doing the 
actual checking. This made it hard to understand what checks were being 
performed, and make changes that were predictable.

Since we were going to refactor to address the I/O issues, we decided to go 
ahead and perform an initial refactor for clarity, composability, and
extensibility.

### Refactor

Here is an overview of the refactor in 2019-06:

- Abstracted away the underlying filesystem logic by encapsulating it in
  adapters. A
  [``SimpleStorageAdapter``](https://github.com/arXiv/arxiv-filemanager/blob/42b9e69eb24d5f41c5eb1667cb1215fa7b83484b/filemanager/services/storage.py#L24)
  implements logic that is close to the original implementation (on a single
  volume). A
  [``QuarantineStorageAdapter``](https://github.com/arXiv/arxiv-filemanager/blob/42b9e69eb24d5f41c5eb1667cb1215fa7b83484b/filemanager/services/storage.py#L271)
  implements the two-volume logic needed to do fast checks before shipping data
  to EFS. The storage adapters implement an API/protocol that is [formalized in
  the domain](https://github.com/arXiv/arxiv-filemanager/blob/42b9e69eb24d5f41c5eb1667cb1215fa7b83484b/filemanager/domain/storage.py#L1).

- Separated the file/workspace checks from the upload workspace class itself
  using multiple-dispatch (something like the visitor pattern). The advantage
  of this pattern is that we can add more checks, reorder the checks, etc,
  without creating an even more enormous class. We can also test them 
  separately, which we should start to do...
  
  - Checkers (visitors) are [formalized in the
    domain](https://github.com/arXiv/arxiv-filemanager/blob/42b9e69eb24d5f41c5eb1667cb1215fa7b83484b/filemanager/domain/checks.py#L1),
    and extend a [``BaseChecker``
    class](https://github.com/arXiv/arxiv-filemanager/blob/42b9e69eb24d5f41c5eb1667cb1215fa7b83484b/filemanager/process/check/base.py#L21).
  - Checking strategies are also [formalized in the
    domain](https://github.com/arXiv/arxiv-filemanager/blob/42b9e69eb24d5f41c5eb1667cb1215fa7b83484b/filemanager/domain/checks.py#L15),
    and implement the visitation of the checkers on a workspace. The
    [``SynchronousCheckingStrategy``](https://github.com/arXiv/arxiv-filemanager/blob/42b9e69eb24d5f41c5eb1667cb1215fa7b83484b/filemanager/process/strategy.py#L13)
    is the first such implementation.
  - The ``UploadWorkspace`` class is assigned a [set of checks and a
    strategy](https://github.com/arXiv/arxiv-filemanager/blob/42b9e69eb24d5f41c5eb1667cb1215fa7b83484b/filemanager/domain/uploads.py#L758-L762),
    which are applied via the
    [``UploadWorkspace.perform_checks``](https://github.com/arXiv/arxiv-filemanager/blob/42b9e69eb24d5f41c5eb1667cb1215fa7b83484b/filemanager/domain/uploads.py#L692)
    method.

- For clarity sake, decomposed most of the ``UploadWorkspace`` into [mixins
  that add sets of
  functionality](https://github.com/arXiv/arxiv-filemanager/blob/42b9e69eb24d5f41c5eb1667cb1215fa7b83484b/filemanager/domain/uploads.py#L1).
- Consolidated the storage of metadata about the workspace. 

  - Previously, details about the workspace state, and about the files in the
    workspace, were generated on each request (indeed, all or most checks were
    re-run on each request). In addition, a database row was maintained with
    some metdata about the last run through the checks. 
  - In the reimplemented checks, file-level checks are only run once per file,
    and workspace-level checks are only run after files are added or deleted. 
  - In the new implementation, the database service has the primary 
    responsibility for loading metadata about the workspace, and initializing 
    the ``UploadWorkspace`` with its storage adapter. This means that loading
    the workspace requires only a single function call, and there is no need 
    to keep track of both a filesystem-based workspace object and a database
    object (both of which represent the workspace) in the controllers.

- Since the core classes were significantly altered, much of the work involved
  modifying the extensive test suite to use the new internal APIs, and 
  modifying the controllers to leverage the new patterns in the domain and
  processes. Since this involved going through the test suite one case at a 
  time, I took the liberty of breaking things up into more manageable pieces:

  - Split controllers out into submodules, for easier navigation.
  - Split up super long test routines in the API tests into separate modules in
    (``tests/test_api/``), smaller ``TestCase``s, and smaller ``test_`` 
    methods. Hopefully this makes it easier to find relevant tests and also see
    what specifically is being tested.

- Removed some cruft that wasn't being used and wasn't likely to be used
  (async boilerplate, etc).