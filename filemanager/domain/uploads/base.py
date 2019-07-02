"""Provides :class:`.BaseWorkspace`."""

from typing import Iterable, Union, Optional, Tuple, List
from datetime import datetime

from dataclasses import dataclass, field

from ..uploaded_file import UploadedFile
from ..index import FileIndex


@dataclass
class _BaseFields:
    upload_id: int
    """Unique ID for the upload workspace."""

    owner_user_id: str
    """User id for owner of workspace."""

    created_datetime: datetime
    """When workspace was created"""

    modified_datetime: datetime
    """When workspace was last modified"""


@dataclass
class _BaseFieldsWithDefaults:
    files: FileIndex = field(default_factory=FileIndex)
    """Index of all of the files in this workspace."""


@dataclass
class BaseWorkspace(_BaseFieldsWithDefaults, _BaseFields):
    """
    Base class for upload workspaces.
    
    Provides a foundational :class:`.FileIndex` at :attr:`.files`, plus some
    core methods that depend on the index.
    """

    def iter_children(self, u_file_or_path: Union[str, UploadedFile],
                      max_depth: Optional[int] = None,  
                      is_ancillary: bool = False,
                      is_removed: bool = False, is_system: bool = False) \
            -> Iterable[Tuple[str, UploadedFile]]:
        """Get an iterator over path, :class:`.UploadedFile` tuples."""
        # QUESTION: is it really so bad to use non-directories here? Can be
        # like the key-prefix for S3. --Erick 2019-06-11.
        u_file: Optional[UploadedFile] = None
        if isinstance(u_file_or_path, str) \
                and self.files.contains(u_file_or_path,
                                        is_ancillary=is_ancillary,
                                        is_removed=is_removed,
                                        is_system=is_system):
            u_file = self.files.get(u_file_or_path,
                                    is_ancillary=is_ancillary,
                                    is_removed=is_removed,
                                    is_system=is_system)
        elif isinstance(u_file_or_path, UploadedFile):
            u_file = u_file_or_path

        if u_file is not None and not u_file.is_directory:
            raise ValueError('Not a directory')

        path: str = str(u_file.path if u_file is not None else u_file_or_path)
        for _path, _file in list(self.files.items(is_ancillary=is_ancillary,
                                                  is_removed=is_removed,
                                                  is_system=is_system)):
            if _path.startswith(path) and not _path == path:
                if max_depth is not None:
                    if path != '':
                        remainder = _path.split(path, 1)[1]
                    else:
                        remainder = _path
                    if len(remainder.strip('/').split('/')) > max_depth:
                        continue
                yield _path, _file

    def iter_files(self, allow_ancillary: bool = True,
                   allow_removed: bool = False,
                   allow_directories: bool = False,
                   allow_system: bool = False) -> List[UploadedFile]:
        """Get an iterator over :class:`.UploadFile`s in this workspace."""
        return [f for f in self.files
                if (allow_directories or not f.is_directory)
                and (allow_removed or not f.is_removed)
                and (allow_ancillary or not f.is_ancillary)
                and (allow_system or not f.is_system)]  
    
    @property
    def size_bytes(self) -> int:
        """Total size of the source content (including ancillary files)."""
        return sum([f.size_bytes for f in self.iter_files()])

    @property
    def last_modified(self) -> Optional[datetime]:
        """Time of the most recent change to a file in the workspace."""
        files_last_modified = [f.last_modified for f in self.iter_files()]
        if not files_last_modified:
            return None
        _mod: datetime = max(files_last_modified + [self.modified_datetime])   
        return _mod
    
    def _update_refs(self, u_file: UploadedFile, 
                     from_path: str) -> None:
        self.files.pop(from_path, is_ancillary=u_file.is_ancillary,
                       is_removed=u_file.is_removed,
                       is_system=u_file.is_system)   # Discard old ref.
        self.files.set(u_file.path, u_file)

    def _drop_refs(self, from_path: str, 
                   is_ancillary: bool = False, is_removed: bool = False, 
                   is_system: bool = False) -> None:
        self.files.pop(from_path, is_ancillary=is_ancillary,
                       is_removed=is_removed, is_system=is_system)
                