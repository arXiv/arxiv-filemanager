"""Transform domain objects to JSON-friendly structs."""

from .domain import UploadWorkspace, UploadedFile


def serialize_workspace(workspace: UploadWorkspace) -> dict:
    """Make a JSON-friendly dict from an :class:`UploadWorkspace`."""
    return {
        'upload_id': workspace.upload_id,
        'upload_total_size': workspace.size_bytes,
        'upload_compressed_size': workspace.source_package.size_bytes,
        'created_datetime': workspace.created_datetime,
        'modified_datetime': workspace.modified_datetime,
        'start_datetime': workspace.lastupload_start_datetime,
        'completion_datetime': workspace.lastupload_completion_datetime,
        'files': [serialize_file(f) for f in workspace.iter_files()],
        'errors': [(e['level'], e['path'], e['message'])
                   for e in workspace.errors + workspace.warnings],
        'readiness': workspace.readiness.value,
        'status': workspace.status.value,
        'lock_state': workspace.lock_state.value,
        'source_format': workspace.source_type.value,
        'checksum': workspace.source_package.checksum
    }


def serialize_file(u_file: UploadedFile) -> dict:
    """Make a JSON-friendly dict from an :class:`UploadedFile`."""
    return {
        'name': u_file.name,
        'public_filepath': u_file.path,
        'size': u_file.size_bytes,
        'type': u_file.file_type.value,
        'modified_datetime': u_file.last_modified
    }
