"""Transform domain objects to API-friendly structs for public consumption."""

from typing import Tuple, Optional
from ..domain import UploadWorkspace, UploadedFile, Error, FileType


def transform_workspace(workspace: UploadWorkspace) -> dict:
    """Make an API-friendly dict from an :class:`UploadWorkspace`."""
    return {
        'upload_id': workspace.upload_id,
        'upload_total_size': workspace.size_bytes,
        'upload_compressed_size': workspace.source_package.size_bytes,
        'created_datetime': workspace.created_datetime,
        'modified_datetime': workspace.modified_datetime,
        'start_datetime': workspace.lastupload_start_datetime,
        'completion_datetime': workspace.lastupload_completion_datetime,
        'files': [transform_file(f) for f in workspace.iter_files()],
        'errors': [transform_error(e) for e in workspace.errors],
        'readiness': workspace.readiness.value,
        'upload_status': workspace.status.value,
        'lock_state': workspace.lock_state.value,
        'source_format': workspace.source_type.value,
        'checksum': workspace.source_package.checksum
    }


def transform_file(u_file: UploadedFile) -> dict:
    """Make an API-friendly dict from an :class:`UploadedFile`."""
    return {
        'name': u_file.name,
        'public_filepath': u_file.public_path,
        'size': u_file.size_bytes,
        'type': u_file.file_type.value,
        'modified_datetime': u_file.last_modified,
        'errors': [transform_error(e) for e in u_file.errors]
    }


def transform_checkpoint(u_file: UploadedFile) -> dict:
    """Make an API-friendly dict from a checkpoint :class:`.UploadedFile`."""
    return {
        'name': u_file.name,
        'size': u_file.size_bytes,
        'checksum': u_file.checksum,
        'modified_datetime': u_file.last_modified,
    }


def transform_error(error: Error) -> Tuple[str, Optional[str], str]:
    """Make an API-friendly tuple from an :class:`Error`."""
    severity: str = error.severity.value
    return (severity, error.path, error.message)
