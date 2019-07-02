"""Core concepts and constraints of the file manager service."""

from .uploads import UploadedFile, UploadWorkspace, CheckableWorkspace, \
    StoredWorkspace, IChecker, IStorageAdapter, SourceLog, SourcePackage
from .file_type import FileType
from .uploads import ICheckingStrategy
from .error import Error
from .index import NoSuchFile, FileIndex
