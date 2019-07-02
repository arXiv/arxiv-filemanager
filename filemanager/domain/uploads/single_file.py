"""Provides :class:`.SingleFileMixin`."""

from typing import List, Union, Mapping, Optional

from .countable import CountableWorkspace
from ..file_type import FileType
from ..uploaded_file import UploadedFile


class SingleFileWorkspace(CountableWorkspace):
    """Adds methods related to single-file source packages."""

    @property
    def is_single_file_submission(self) -> bool:
        """Indicate whether or not this is a valid single-file submission."""
        if self.file_count != 1:
            return False
        counts = self.get_file_type_counts()
        if counts['ignore'] == 1:
            return False
        return True

    def get_single_file(self) -> Optional[UploadedFile]:
        """
        Return File object for single-file submission.

        This routine is intended for submission that are composed of a single
        content file.

        Single file can't be type 'ancillary'. Single ancillary file is invalid
        submission and generates an error.

        Returns
        -------
        :class:`.UploadedFile` or ``None``
            Single file. Returns None when submission has more than one file.

        """
        if self.is_single_file_submission:
            for u_file in self.iter_files(allow_ancillary=False):
                return u_file    # Return the first file.
        return None