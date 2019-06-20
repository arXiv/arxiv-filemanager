"""
Conversion of domain objects to/from native structs for persistence.

These are defined separately from the serialization functions that we use to
prepare workspace data for API responses. In the API case, we are only exposing
a subset of the information, and the naming/structure of the response documents
in somewhat different from our internal representation. In contrast, the goal
here is fidelity.
"""

from ...domain import Error, UploadedFile, UploadWorkspace


def error_to_dict(error: Error) -> dict:
    """Translate an :class:`.Error` to a dict."""
    return {
        'severity': error.severity.value,
        'message': error.message,
        'code': error.code.value,
        'path': error.path,
        'is_persistant': error.is_persistant
    }


def dict_to_error(data: dict) -> Error:
    """Translate a dict to an :class:`.Error`."""
    return Error(
        severity=Error.Severity(data['severity']),
        message=data['message'],
        code=Error.Code(data.get('code', Error.Code.UNKNOWN.value)),
        path=data.get('path', None),
        is_persistant=data.get('is_persistant', True)
    )


def file_to_dict(u_file: UploadedFile) -> dict:
    """Translate an :class:`.UploadedFile` to a dict."""
    return {
        'path': u_file.path,
        'size_bytes': u_file.size_bytes,
        'file_type': u_file.file_type.value,
        'is_removed': u_file.is_removed,
        'is_ancillary': u_file.is_ancillary,
        'is_directory': u_file.is_directory,
        'is_checked': u_file.is_checked,
        'is_persisted': u_file.is_persisted,
        'is_system': u_file.is_system,
        'last_modified': u_file.last_modified,
        'reason_for_removal': u_file.reason_for_removal,
        'errors': [error_to_dict(error) for error in u_file.errors]
    }


def dict_to_file(data: dict, workspace: UploadWorkspace) -> UploadedFile:
    """Translate a dict to an :class:`.UploadedFile`."""
    return UploadedFile(
        workspace=workspace,
        path=data['path'],
        size_bytes=int(data['size_bytes']),
        is_removed=data.get('is_removed', False),
        is_ancillary=data.get('is_ancillary', False),
        is_checked=data.get('is_checked', False),
        is_persisted=data.get('is_persisted', False),
        is_system=data.get('is_system', False),
        last_modified=data['last_modified'],
        reason_for_removal=data.get('reason_for_removal'),
        errors=[dict_to_error(error) for error in data.get('errors', [])]
    )
