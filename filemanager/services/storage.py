"""On-disk storage for uploads."""

from typing import Any
import io
import os
import shutil
import filecmp
from pathlib import Path

from ..domain import UploadWorkspace, UploadedFile


class SimpleStorageAdapter:

    def __init__(self, base_path: str) -> None:
        self._base_path = base_path

    def move(self, workspace: Workspace, u_file: UploadedFile, from_path: str, to_path: str) -> None:
        # if u_file.is_directory:
        pass

    def open(self, workspace: UploadWorkspace, u_file: UploadedFile,
             flags: str = 'r', **kwargs: Any) -> io.IOBase:
        return open(self._get_path(workspace, u_file), flags, **kwargs)

    def _get_path(self, workspace: UploadWorkspace,
                  u_file: UploadedFile) -> str:
        return os.path.join(self._base_path, workspace.get_path(u_file))

    def persist(self, workspace: UploadWorkspace, u_file: UploadedFile) -> None:
        # TODO: check path exists.
        u_file.is_persisted = True

    def cmp(self, workspace: UploadWorkspace, a_file: UploadedFile,
            b_file: UploadedFile, shallow: bool = True) -> bool:
        return filecmp.cmp(self._get_path(workspace, a_file),
                           self._get_path(workspace, b_file),
                           shallow=shallow)

    def create(self, workspace: UploadWorkspace, u_file: UploadedFile) -> None:
        Path(self._get_path(workspace, u_file)).touch()

    def copy(self, workspace: UploadWorkspace, u_file: UploadedFile,
             new_file: UploadedFile) -> None:
        pass

    def delete(self, workspace: UploadWorkspace, u_file: UploadedFile) -> None:
        if u_file.is_directory:
            shutil.rmtree(self._get_path(workspace, u_file))
        else:
            os.unlink(self._get_path(workspace, u_file))

    def getsize(self, workspace: UploadWorkspace, u_file: UploadedFile) -> int:
        return os.path.getsize(self._get_path(workspace, u_file))


class QuarantineStorageAdapter(SimpleStorageAdapter):
    def __init__(self, base_path: str, quarantine_path: str) -> None:
        self._base_path = base_path
        self._quarantine_path = quarantine_path

    def move(self, workspace: Workspace, u_file: UploadedFile, from_path: str, to_path: str) -> None:
        # if u_file.is_directory:
        pass

    def _get_permanent_path(self, path: str) -> str:
        return os.path.join(self._base_path, path)

    def _get_quarantine_path(self, path: str) -> str:
        return os.path.join(self._quarantine_path, path)

    def _get_path(self, workspace: UploadWorkspace,
                  u_file: UploadedFile) -> str:
        if u_file.is_persisted:
            return self._get_permanent_path(workspace.get_path(u_file))
        return self._get_quarantine_path(workspace.get_path(u_file))

    def open(self, workspace: UploadWorkspace, u_file: UploadedFile,
             flags: str = 'r') -> io.IOBase:
        return open(self._get_path(workspace, u_file), flags)

    def persist(self, workspace: UploadWorkspace, u_file: UploadedFile) -> None:
        u_path = workspace.get_path(u_file)
        shutil.move(self._get_quarantine_path(workspace.get_path(u_file)),
                    self._get_permanent_path(workspace.get_path(u_file)))
        u_file.is_persisted = True

        # Since we are working on a conventional file system, if we just copied
        # a directory then we have also copied all of its children. So we can
        # go ahead and mark those as persisted, too, in order to prevent
        # unnecessary i/o.
        if u_file.is_directory:
            for _path, _file in workspace.files.items():
                if _path.startswith(u_file.path) and not _file.is_persisted:
                    _file.is_persisted = True
