"""Provides :class:`.CountsMixin`."""

from typing import List, Union, Mapping, Dict
from collections import Counter

from dataclasses import dataclass

from .base import BaseWorkspace
from ..file_type import FileType
from ..uploaded_file import UploadedFile


@dataclass
class CountableWorkspace(BaseWorkspace):
    """Adds methods related to file counts."""

    @property
    def file_count(self) -> int:
        """Get the total number of non-ancillary files in this workspace."""
        return len(self.iter_files(allow_ancillary=False))
    
    @property
    def ancillary_file_count(self) -> int:
        """Get the total number of ancillary files in this workspace."""
        files = self.iter_files(allow_ancillary=True, allow_removed=False)
        return len([f for f in files if f.is_ancillary])

    def get_file_type_counts(self) -> Mapping[Union[FileType, str], int]:
        """Get the number of files of each type in the workspace."""
        counts: Dict[Union[FileType, str], int] = Counter()
        for u_file in self.iter_files():
            counts['all_files'] += 1
            if u_file.is_ancillary:
                counts['ancillary'] += 1
                continue
            elif u_file.is_always_ignore:
                counts['ignore'] += 1
                continue
            counts[u_file.file_type] += 1
        counts['files'] = counts['all_files'] - counts['ancillary']
        return counts