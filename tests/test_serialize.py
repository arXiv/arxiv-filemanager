"""Tests for :mod:`.serialize`."""

import io
from contextlib import contextmanager
from unittest import TestCase, mock
from datetime import datetime
from filemanager.domain import UploadedFile, UploadWorkspace, Error, FileType
from filemanager.serialize import serialize_error, serialize_file, \
    serialize_workspace


class TestSerializeError(TestCase):
    """Tests for :func:`.serialize.serialize_error`."""

    def test_serialize_fatal_error(self):
        """Serialize a fatal :class:`.Error."""
        error = Error(severity=Error.Severity.FATAL, path='foo/path.md',
                      message='This is a message', is_persistant=True)
        expected = ('fatal', 'foo/path.md', 'This is a message')
        self.assertEqual(serialize_error(error), expected)
    
    def test_serialize_warning_error(self):
        """Serialize a warning :class:`.Error."""
        error = Error(severity=Error.Severity.WARNING, path='foo/path.md',
                      message='This is a message', is_persistant=True)
        expected = ('warn', 'foo/path.md', 'This is a message')
        self.assertEqual(serialize_error(error), expected)
            

class TestSerializeFile(TestCase):
    """Tests for :func:`.serialize.serialize_file`."""

    def test_serialize_file(self):
        """Serialize a :class:`.UploadedFile`."""
        workspace = mock.MagicMock(spec=UploadWorkspace)
        workspace.get_public_path.return_value = 'foo/path.md'
        u_file = UploadedFile(workspace=workspace, 
                              path='foo/path.md', is_ancillary=True,
                              size_bytes=54_022, file_type=FileType.TEX)
        expected = {'name': 'path.md', 'public_filepath': 'foo/path.md', 
                    'size': 54_022, 'type': 'TEX', 
                    'modified_datetime': u_file.last_modified, 'errors': []}
        self.assertDictEqual(serialize_file(u_file), expected)
    
    def test_serialize_file_with_errors(self):
        """Serialize a :class:`.UploadedFile` with errors."""
        workspace = mock.MagicMock(spec=UploadWorkspace)
        workspace.get_public_path.return_value = 'foo/path.md'
        u_file = UploadedFile(workspace=workspace, 
                              path='foo/path.md', is_ancillary=False,
                              file_type=FileType.TEX,
                              size_bytes=54_022, _errors=[
                                  Error(severity=Error.Severity.FATAL, 
                                        path='foo/path.md',
                                        message='This is a fatal error', 
                                        is_persistant=True),
                                  Error(severity=Error.Severity.WARNING, 
                                        path='foo/path.md',
                                        message='This is a message', 
                                        is_persistant=False),
                              ])
        expected = {'name': 'path.md', 'public_filepath': 'foo/path.md', 
                    'size': 54_022, 'type': 'TEX', 
                    'modified_datetime': u_file.last_modified, 
                    'errors': [
                        ('fatal', 'foo/path.md', 'This is a fatal error'), 
                        ('warn', 'foo/path.md', 'This is a message')
                    ]}
        self.assertDictEqual(serialize_file(u_file), expected)


class TestSerializeWorkspace(TestCase):
    """Serialize an :class:`.UploadWorkspace."""

    def test_serialize_workspace(self):
        """Serialize an :class:`.UploadWorkspace."""
        self.upload_id = 5432

        @contextmanager
        def mock_open(*args, **kwargs):
            yield io.BytesIO(b'foo')

        mock_storage = mock.MagicMock()
        mock_storage.get_path.return_value = 'foo'
        mock_storage.open = mock_open
        mock_storage.get_size_bytes.return_value = 1234
        workspace = UploadWorkspace(
            upload_id=self.upload_id,
            owner_user_id='98765',
            created_datetime=datetime.now(),
            modified_datetime=datetime.now(),
            strategy=mock.MagicMock(),
            storage=mock_storage
        )
        workspace.initialize()
        expected = {'upload_id': 5432, 'upload_total_size': 0, 
                    'upload_compressed_size': 1234, 
                    'created_datetime': workspace.created_datetime, 
                    'modified_datetime': workspace.modified_datetime, 
                    'start_datetime': None, 'completion_datetime': None, 
                    'files': [], 'errors': [], 
                    'readiness': 'READY', 'upload_status': 'ACTIVE', 
                    'lock_state': 'UNLOCKED', 'source_format': 'unknown', 
                    'checksum': 'rL0Y20zC-Fzt72VPzMSk2A=='}
        self.assertDictEqual(serialize_workspace(workspace), expected)
    
    def test_serialize_workspace_with_files_and_errors(self):
        """Serialize an :class:`.UploadWorkspace."""
        self.upload_id = 5432

        @contextmanager
        def mock_open(*args, **kwargs):
            yield io.BytesIO(b'foo')

        mock_storage = mock.MagicMock()
        mock_storage.get_path.return_value = 'foo'
        mock_storage.open = mock_open
        mock_storage.get_size_bytes.return_value = 1234
        workspace = UploadWorkspace(
            upload_id=self.upload_id,
            owner_user_id='98765',
            created_datetime=datetime.now(),
            modified_datetime=datetime.now(),
            strategy=mock.MagicMock(),
            storage=mock_storage
        )
        workspace.initialize()
        u_file = workspace.create('foo/baz.md')
        u_file2 = workspace.create('secret', is_system=True)
        workspace.add_error(u_file, 'foo error', is_persistant=True)
        workspace.add_warning(u_file, 'foo warning', is_persistant=False)
        serialized = serialize_workspace(workspace)
        self.assertEqual(serialized['errors'], 
                         [('fatal', 'foo/baz.md', 'foo error'), 
                          ('warn', 'foo/baz.md', 'foo warning')],
                         'Errors are correctly serialized')
        self.assertEqual(len(serialized['files']), 1,
                         'One file is serialized')
        self.assertEqual(serialized['files'][0]['name'], u_file.name)
        self.assertEqual(serialized['files'][0]['type'], 
                         u_file.file_type.value)
        self.assertEqual(len(serialized['files'][0]['errors']), 2)