"""Core concepts and constraints of the file manager service."""

from .uploads import UploadedFile, UploadWorkspace, IChecker, IStorageAdapter
from .file_type import FileType
from .checks import ICheckingStrategy
from .error import Error
from .index import NoSuchFile, FileIndex
