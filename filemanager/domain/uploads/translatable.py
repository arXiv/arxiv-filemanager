"""
Conversion of domain objects to/from native structs for persistence.

These are defined separately from the serialization functions that we use to
prepare workspace data for API responses. In the API case, we are only exposing
a subset of the information, and the naming/structure of the response documents
in somewhat different from our internal representation. In contrast, the goal
here is fidelity.
"""

from typing import Dict, Any
from datetime import datetime
from backports.datetime_fromisoformat import MonkeyPatch

from ..error import Error
from ..uploaded_file import UploadedFile
from ..file_type import FileType
from ..index import FileIndex

from .errors_and_warnings import ErrorsAndWarningsWorkspace

MonkeyPatch.patch_fromisoformat()


class TranslatableWorkspace(ErrorsAndWarningsWorkspace):
    """Adds translation functionality to/from native Python structs."""

    @classmethod
    def error_to_dict(cls, error: Error) -> dict:
        """Translate an :class:`.Error` to a dict."""
        return {
            'severity': error.severity.value,
            'message': error.message,
            'code': error.code.value,
            'path': error.path,
            'is_persistant': error.is_persistant
        }

    @classmethod
    def dict_to_error(cls, data: dict) -> Error:
        """Translate a dict to an :class:`.Error`."""
        return Error(
            severity=Error.Severity(data['severity']),
            message=data['message'],
            code=Error.Code(data.get('code', Error.Code.UNKNOWN.value)),
            path=data.get('path', None),
            is_persistant=data.get('is_persistant', True)
        )

    @classmethod
    def file_to_dict(cls, u_file: UploadedFile) -> dict:
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
            'last_modified': u_file.last_modified.isoformat(),
            'reason_for_removal': u_file.reason_for_removal,
            'errors': [cls.error_to_dict(error)
                       for error in u_file.errors
                       if error.is_persistant]
        }


    @classmethod
    def dict_to_file(cls, data: dict, workspace: 'TranslatableWorkspace') \
            -> UploadedFile:
        """Translate a dict to an :class:`.UploadedFile`."""
        last_modified = data['last_modified']
        if not isinstance(last_modified, datetime):
            last_modified = datetime.fromisoformat(last_modified)
        return UploadedFile(
            workspace=workspace,
            path=data['path'],
            size_bytes=int(data['size_bytes']),
            is_removed=data.get('is_removed', False),
            is_ancillary=data.get('is_ancillary', False),
            is_checked=data.get('is_checked', False),
            is_persisted=data.get('is_persisted', False),
            is_system=data.get('is_system', False),
            is_directory=data.get('is_directory', False),
            last_modified=last_modified,
            reason_for_removal=data.get('reason_for_removal'),
            _errors=[cls.dict_to_error(error)
                     for error in data.get('errors', [])],
            file_type=FileType(data['file_type'])
        )

    @classmethod
    def workspace_to_dict(cls, workspace: 'TranslatableWorkspace') -> dict:
        upload_data: Dict[str, Any] = {}
        upload_data['upload_id'] = workspace.upload_id
        upload_data['owner_user_id'] = workspace.owner_user_id

        # We won't let client update created_datetime

        upload_data['lastupload_start_datetime'] = \
            workspace.lastupload_start_datetime
        upload_data['lastupload_completion_datetime'] = \
            workspace.lastupload_completion_datetime
        upload_data['lastupload_logs'] = workspace.lastupload_logs
        upload_data['lastupload_file_summary'] = workspace.lastupload_file_summary
        upload_data['lastupload_readiness'] = workspace.lastupload_readiness.value
        upload_data['status'] = workspace.status.value
        upload_data['lock_state'] = workspace.lock_state.value
        upload_data['source_type'] = workspace.source_type.value
        upload_data['created_datetime'] = workspace.created_datetime
        upload_data['modified_datetime'] = workspace.modified_datetime

        upload_data['files'] = {
            'source': {p: cls.file_to_dict(f)
                    for p, f in workspace.files.source.items()},
            'ancillary': {p: cls.file_to_dict(f)
                        for p, f in workspace.files.ancillary.items()},
            'removed': {p: cls.file_to_dict(f)
                        for p, f in workspace.files.removed.items()},
            'system': {p: cls.file_to_dict(f)
                    for p, f in workspace.files.system.items()},
        }
        upload_data['errors'] = [
            cls.error_to_dict(e) for e in workspace._errors if e.is_persistant
        ]
        return upload_data

    def to_dict(self) -> dict:
        return self.workspace_to_dict(self)

    @classmethod
    def from_dict(cls, upload_data: dict) -> 'TranslatableWorkspace':
        args = {}
        args['upload_id'] = upload_data['upload_id']
        args['owner_user_id'] = upload_data['owner_user_id']
        args['created_datetime'] = upload_data['created_datetime']
        args['modified_datetime'] = upload_data['modified_datetime']
        args['status'] = cls.Status(upload_data['status'])
        args['lock_state'] = cls.LockState(upload_data['lock_state'])
        args['source_type'] = cls.SourceType(upload_data['source_type'])

        args['lastupload_start_datetime'] = upload_data.get('lastupload_start_datetime')
        args['lastupload_completion_datetime'] = upload_data.get('lastupload_completion_datetime')
        args['lastupload_logs'] = upload_data.get('lastupload_logs')
        args['lastupload_file_summary'] = upload_data.get('lastupload_file_summary')

        lastupload_readiness = upload_data.get('lastupload_readiness')
        if lastupload_readiness is not None:
            args['lastupload_readiness'] = cls.Readiness(lastupload_readiness)

        workspace = cls(**args)

        _files = upload_data.get('files')
        if _files:
            workspace.files = FileIndex(
                source={p: cls.dict_to_file(d, workspace)
                        for p, d in _files['source'].items()},
                ancillary={p: cls.dict_to_file(d, workspace)
                        for p, d in _files['ancillary'].items()},
                removed={p: cls.dict_to_file(d, workspace)
                        for p, d in _files['removed'].items()},
                system={p: cls.dict_to_file(d, workspace)
                        for p, d in _files['system'].items()
                }
            )
        _errors = upload_data.get('errors')
        if _errors:
            for datum in _errors:
                workspace._errors.append(cls.dict_to_error(datum))

        # workspace.initialize()
        return workspace