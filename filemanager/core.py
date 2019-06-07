
from ..domain import UploadWorkspace

class PersistentWorkspace(UploadWorkspace):
    """."""

    def persist(self, u_file: 'UploadedFile',
                replace: bool = True) -> None:
        ...

    def remove(self, u_file: 'UploadedFile') -> None:
        ...
