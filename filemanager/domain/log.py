"""Defines the source log."""

import io
import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterator
from dataclasses import dataclass, field


DEFAULT_LOG_FORMAT = '%(asctime)s %(message)s'
DEFAULT_TIME_FORMAT = '%d/%b/%Y:%H:%M:%S %z'


@dataclass
class SourceLog:
    """Record of upload and processing events for a source workspace."""

    workspace: 'UploadWorkspace'
    """Workspace to which the source log belongs."""

    path: str = field(default='source.log')
    """Relative path to the source log with the containing workspace."""

    log_format: str = field(default=DEFAULT_LOG_FORMAT)
    """Format string for log messages."""

    time_format: str = field(default=DEFAULT_TIME_FORMAT)

    level: int = field(default=logging.INFO)
    """Log level."""

    def __post_init__(self) -> None:
        """Create a source log if it does not already exist."""
        self._file = self.workspace.get(self.path, is_system=True)

        # Grab standard logger and customize it.
        self._logger = logging.getLogger(f'source:{self.workspace.upload_id}')
        self._f_path = self.workspace.get_full_path(self._file, is_system=True)
        self._file_handler = logging.FileHandler(self._f_path)
        self._file_handler.setLevel(self.level)
        self._formatter = logging.Formatter(self.log_format, self.time_format)
        self._file_handler.setFormatter(self._formatter)
        self._logger.handlers = []
        self._logger.addHandler(self._file_handler)
        self._logger.setLevel(self.level)
        self._logger.propagate = False

    @property
    def size_bytes(self) -> int:
        """Get the size of the log file in bytes."""
        return self.workspace.get_size_bytes(self._file)

    @property
    def checksum(self) -> str:
        """Get the base64 md5 hash of the log file."""
        return self.workspace.get_checksum(self)

    @property
    def last_modified(self) -> datetime:
        """Get the datetime when the log was last modified."""
        return self.workspace.get_last_modified(self._file)

    @property
    def checksum(self) -> str:
        """Get the Base64-encoded MD5 hash of the log file."""
        return self.workspace.get_checksum(self._file)

    @contextmanager
    def open(self, flags: str = 'r', **kwargs: Any) -> Iterator[io.IOBase]:
        """
        Get an open file pointer to the log file.

        To be used as a context manager.
        """
        with self.workspace.open(self._file, flags, **kwargs) as f:
            yield f

    def open_pointer(self, flags: str = 'r', **kwargs: Any) -> io.IOBase:
        return self.workspace.open_pointer(self._file, flags, **kwargs)

    def debug(self, message: str) -> None:
        self._logger.debug(message)

    def info(self, message: str) -> None:

        self._logger.info(message)

    def error(self, message: str) -> None:
        self._logger.error(message)

    @property
    def full_path(self) -> str:
        return self.workspace.get_full_path(self._file)
