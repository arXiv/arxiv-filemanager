"""Remove a top level directory."""

import os

from arxiv.base import logging

from ...domain import FileType, UserFile, Workspace, Code
from .base import BaseChecker, StopCheck


logger = logging.getLogger(__name__)
logger.propagate = False


class RemoveTopLevelDirectory(BaseChecker):
    """
    Eliminates single top-level directory.

    Intended for case where submitter creates archive with all uploaded
    files in a subdirectory.
    """

    TOP_LEVEL_DIRECTORY: Code = 'top_level_directory_removed'
    TOP_LEVEL_DIRECTORY_MESSAGE = "Removed top level directory"

    def check_workspace(self, workspace: Workspace) -> None:
        """Eliminate single top-level directory."""
        # source_directory = self.source_path

        # entries = os.listdir(source_directory)
        entries = [c for _, c in workspace.iter_children('', max_depth=1)]

        # If all of the upload content is within a single top-level directory,
        # move everything up one level and remove the directory. But don't
        # clobber the ancillary directory!
        if len(entries) == 1 \
                and entries[0].is_directory and not entries[0].is_ancillary:

            workspace.add_warning(entries[0], self.TOP_LEVEL_DIRECTORY,
                                  self.TOP_LEVEL_DIRECTORY_MESSAGE,
                                  is_persistant=False)
            for _, child in workspace.iter_children(entries[0], max_depth=1):
                _, new_path = child.path.split(entries[0].path, 1)
                workspace.rename(child, new_path)
            workspace.remove(entries[0], "Removed top level directory")
            #
            # # Set permissions
            # self.set_file_permissions()

            # Rebuild file list
            # self.create_file_list()
