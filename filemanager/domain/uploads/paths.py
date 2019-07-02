"""Provides :class:`.PathsMixin`."""

import os
from typing import Optional, Union, Any, Tuple

from ..uploaded_file import UploadedFile
from ..file_type import FileType
from ..index import FileIndex
from .base import BaseWorkspace
from .util import logger


class FilePathsWorkspace(BaseWorkspace):
    """Implements methods related to paths in :class:`.UploadWorkspace."""

    SOURCE_PREFIX = 'src'
    """The name of the source directory within the upload workspace."""

    REMOVED_PREFIX = 'removed'
    """The name of the removed directory within the upload workspace."""

    ANCILLARY_PREFIX = 'anc'
    """The directory within source directory where ancillary files are kept."""

    @property
    def base_path(self) -> str:
        """Relative base path for this workspace."""
        return str(self.upload_id)

    @property
    def source_path(self) -> str:
        """Get the path where source files are deposited."""
        return os.path.join(self.base_path, self.SOURCE_PREFIX)

    @property
    def removed_path(self) -> str:
        """Get path where source archive files get moved when unpacked."""
        return os.path.join(self.base_path, self.REMOVED_PREFIX)

    @property
    def ancillary_path(self) -> str:
        """Get the path where ancillary files are stored."""
        return os.path.join(self.source_path, self.ANCILLARY_PREFIX)

    def get(self, path: str, is_ancillary: Optional[bool] = None, 
            is_removed: bool = False, is_system: bool = False) -> UploadedFile:
        """Get a file at ``path``."""
        if is_ancillary is None:
            path, is_ancillary = self._check_is_ancillary_path(path)
        return self.files.get(path, is_ancillary=is_ancillary,
                              is_removed=is_removed, is_system=is_system)
    
    def get_public_path(self, u_file: UploadedFile) -> str:
        if u_file.is_system or u_file.is_removed:
            raise RuntimeError('Not a public file')
        if u_file.is_ancillary:
            return os.path.join(self.ANCILLARY_PREFIX, u_file.path)
        return u_file.path

    def get_path(self, u_file_or_path: Union[str, UploadedFile],
                 is_ancillary: bool = False, is_removed: bool = False,
                 is_system: bool = False, **kwargs: Any) -> str:
        """Get the path to an :class:`.UploadedFile` in this workspace."""
        if isinstance(u_file_or_path, UploadedFile):
            logger.debug('Get path for file: %s', u_file_or_path.path)
            path = self._get_path_from_file(u_file_or_path)
        else:
            path = self._get_path(u_file_or_path, is_ancillary=is_ancillary,
                                  is_removed=is_removed, is_system=is_system)
        return path.lstrip('/')

    def _get_path(self, path: str, 
                  is_ancillary: bool = False, is_removed: bool = False, 
                  is_system: bool = False) -> str:
        path = path.lstrip('/')
        if is_system:
            return os.path.join(self.base_path, path)
        if is_ancillary:
            return os.path.join(self.ancillary_path, path)
        if is_removed:
            return os.path.join(self.removed_path, path)
        return os.path.join(self.source_path, path)

    def _get_path_from_file(self, u_file: UploadedFile) \
            -> str:
        return self._get_path(u_file.path, is_ancillary=u_file.is_ancillary,
                              is_removed=u_file.is_removed,
                              is_system=u_file.is_system)
    
    def exists(self, path: str, is_ancillary: bool = False,
               is_removed: bool = False, is_system: bool = False) -> bool:
        """Determine whether or not a file exists in this workspace."""
        return self.files.contains(path, is_ancillary=is_ancillary,
                                   is_removed=is_removed, is_system=is_system)

    def _check_is_ancillary_path(self, path: str) -> Tuple[str, bool]:
        if path.startswith(self.ANCILLARY_PREFIX):
            logger.debug('Path indicates an ancillary file')
            _, path = path.split(self.ANCILLARY_PREFIX, 1)
            path = path.strip('/')
            logger.debug('Path indicates ancillary file; trimmed to `%s`',
                         path)
            return path, True
        return path, False  