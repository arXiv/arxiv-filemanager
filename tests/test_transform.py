"""Tests for :mod:`.transform`."""

import io
from contextlib import contextmanager
from unittest import TestCase, mock
from datetime import datetime
from filemanager.domain import UserFile, Workspace, Error, FileType, Severity
from filemanager.controllers.transform import transform_error, \
    transform_file, transform_workspace


class TestTransformError(TestCase):
    """Tests for :func:`.transform.transform_error`."""

    def test_transform_fatal_error(self):
        """Transform a fatal :class:`.Error."""
        error = Error(severity=Severity.FATAL, path='foo/path.md',
                      message='This is a message', is_persistant=True)
        expected = ('fatal', 'foo/path.md', 'This is a message')
        self.assertEqual(transform_error(error), expected)

    def test_transform_warning_error(self):
        """Transform a warning :class:`.Error."""
        error = Error(severity=Severity.WARNING, path='foo/path.md',
                      message='This is a message', is_persistant=True)
        expected = ('warn', 'foo/path.md', 'This is a message')
        self.assertEqual(transform_error(error), expected)


class TestTransformFile(TestCase):
    """Tests for :func:`.transform.transform_file`."""

    def test_transform_file(self):
        """Transform a :class:`.UserFile`."""
        workspace = mock.MagicMock(spec=Workspace)
        workspace.get_public_path.return_value = 'foo/path.md'
        u_file = UserFile(workspace=workspace,
                              path='foo/path.md', is_ancillary=True,
                              size_bytes=54_022, file_type=FileType.TEX)
        expected = {'name': 'path.md', 'public_filepath': 'foo/path.md',
                    'size': 54_022, 'type': 'TEX',
                    'modified_datetime': u_file.last_modified, 'errors': []}
        self.assertDictEqual(transform_file(u_file), expected)

    def test_transform_file_with_errors(self):
        """Transform a :class:`.UserFile` with errors."""
        workspace = mock.MagicMock(spec=Workspace)
        workspace.get_public_path.return_value = 'foo/path.md'
        u_file = UserFile(workspace=workspace,
                              path='foo/path.md', is_ancillary=False,
                              file_type=FileType.TEX,
                              size_bytes=54_022,
                              _errors={
                                  'fatal_error': Error(severity=Severity.FATAL,
                                        path='foo/path.md',
                                        code='fatal_error',
                                        message='This is a fatal error',
                                        is_persistant=True),
                                  'message': Error(severity=Severity.WARNING,
                                        path='foo/path.md',
                                        code='message',
                                        message='This is a message',
                                        is_persistant=False),
                              })
        expected = {'name': 'path.md', 'public_filepath': 'foo/path.md',
                    'size': 54_022, 'type': 'TEX',
                    'modified_datetime': u_file.last_modified,
                    'errors': [
                        ('fatal', 'foo/path.md', 'This is a fatal error'),
                        ('warn', 'foo/path.md', 'This is a message')
                    ]}
        self.assertDictEqual(transform_file(u_file), expected)


class TestTransformWorkspace(TestCase):
    """Transform an :class:`.Workspace."""

    def test_transform_workspace(self):
        """Transform an :class:`.Workspace."""
        self.upload_id = 5432

        @contextmanager
        def mock_open(*args, **kwargs):
            yield io.BytesIO(b'foo')

        mock_storage = mock.MagicMock()
        mock_storage.get_path.return_value = 'foo'
        mock_storage.open = mock_open
        mock_storage.get_size_bytes.return_value = 1234
        workspace = Workspace(
            upload_id=self.upload_id,
            owner_user_id='98765',
            created_datetime=datetime.now(),
            modified_datetime=datetime.now(),
            _strategy=mock.MagicMock(),
            _storage=mock_storage
        )
        workspace.initialize()
        expected = {'upload_id': 5432, 'upload_total_size': 0,
                    'upload_compressed_size': 1234,
                    'created_datetime': workspace.created_datetime,
                    'start_datetime': None, 'completion_datetime': None,
                    'files': [], 'errors': [],
                    'readiness': 'READY', 'upload_status': 'ACTIVE',
                    'lock_state': 'UNLOCKED', 'source_format': 'unknown',
                    'checksum': 'rL0Y20zC-Fzt72VPzMSk2A=='}
        data = transform_workspace(workspace)
        for key, value in expected.items():
            self.assertEqual(data.get(key), value, f'{key} should match')

    def test_transform_workspace_with_files_and_errors(self):
        """Transform an :class:`.Workspace."""
        self.upload_id = 5432

        @contextmanager
        def mock_open(*args, **kwargs):
            yield io.BytesIO(b'foo')

        mock_storage = mock.MagicMock()
        mock_storage.get_path.return_value = 'foo'
        mock_storage.open = mock_open
        mock_storage.get_size_bytes.return_value = 1234
        workspace = Workspace(
            upload_id=self.upload_id,
            owner_user_id='98765',
            created_datetime=datetime.now(),
            modified_datetime=datetime.now(),
            _strategy=mock.MagicMock(),
            _storage=mock_storage
        )
        workspace.initialize()
        u_file = workspace.create('foo/baz.md')
        u_file2 = workspace.create('secret', is_system=True)
        workspace.add_error(u_file, 'foo_error', 'foo error', is_persistant=True)
        workspace.add_warning(u_file, 'foo_warning', 'foo warning', is_persistant=False)
        transformd = transform_workspace(workspace)
        self.assertEqual(transformd['errors'],
                         [('fatal', 'foo/baz.md', 'foo error'),
                          ('warn', 'foo/baz.md', 'foo warning')],
                         'Errors are correctly transformd')
        self.assertEqual(len(transformd['files']), 1,
                         'One file is transformd')
        self.assertEqual(transformd['files'][0]['name'], u_file.name)
        self.assertEqual(transformd['files'][0]['type'],
                         u_file.file_type.value)
        self.assertEqual(len(transformd['files'][0]['errors']), 2)
