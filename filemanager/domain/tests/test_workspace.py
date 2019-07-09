"""Tests for :class:`.domain.UploadWorkspace`."""

from datetime import datetime, timedelta
from unittest import TestCase, mock

from pytz import UTC

from ..uploads import UploadWorkspace, UploadedFile
from ..file_type import FileType


class TestPaths(TestCase):
    """Workspace is responsible for managing several relative paths."""

    @mock.patch('filemanager.domain.uploads.file_mutations.logging',
                mock.MagicMock())
    def setUp(self):
        """We have a vanilla workspace."""
        self.mock_strategy = mock.MagicMock()
        self.mock_storage = mock.MagicMock()
        self.mock_storage.get_path.return_value = '/tmp/foo'
        self.wks = UploadWorkspace(
            upload_id=1234,
            owner_user_id='98765',
            created_datetime=datetime.now(),
            modified_datetime=datetime.now(),
            strategy=self.mock_strategy,
            storage=self.mock_storage
        )

    def test_get_source_path(self):
        """Source path is based on the upload ID and class-specific prefix."""
        self.assertEqual(self.wks.source_path,
                         f'{self.wks.upload_id}/{self.wks.SOURCE_PREFIX}')
        self.assertFalse(self.wks.source_path.startswith('/'),
                         'Must return a relative path')

    def test_get_removed_path(self):
        """Removed path is based on the upload ID and class-specific prefix."""
        self.assertEqual(self.wks.removed_path,
                         f'{self.wks.upload_id}/{self.wks.REMOVED_PREFIX}')
        self.assertFalse(self.wks.removed_path.startswith('/'),
                         'Must return a relative path')

    def test_get_ancillary_path(self):
        """Ancillary path is based on source path and class-specific prefix."""
        self.assertEqual(self.wks.ancillary_path,
                         f'{self.wks.upload_id}/{self.wks.SOURCE_PREFIX}/anc')
        self.assertFalse(self.wks.ancillary_path.startswith('/'),
                         'Must return a relative path')

    def test_get_path(self):
        """Can get a relative path for an :class:`.UploadedFile`."""
        mock_file = mock.MagicMock(spec=UploadedFile,
                                   is_ancillary=False,
                                   is_removed=False,
                                   is_directory=False,
                                   is_system=False,
                                   is_active=True,
                                   path='path/to/file')
        self.assertEqual(self.wks.get_path(mock_file),
                         f'{self.wks.source_path}/path/to/file',
                         'File path is inside workspace.')
        self.assertFalse(self.wks.get_path(mock_file).startswith('/'),
                         'Must return a relative path')

    def test_get_ancillary_file_path(self):
        """Can get a relative path for an ancillary :class:`.UploadedFile`."""
        mock_file = mock.MagicMock(spec=UploadedFile,
                                   is_ancillary=True,
                                   is_removed=False,
                                   is_directory=False,
                                   is_system=False,
                                   is_active=True,
                                   path='path/to/file')
        self.assertEqual(self.wks.get_path(mock_file),
                         f'{self.wks.ancillary_path}/path/to/file',
                         'File path is inside workspace.')
        self.assertFalse(self.wks.get_path(mock_file).startswith('/'),
                         'Must return a relative path')

    def test_get_removed_file_path(self):
        """Can get a relative path for a removed :class:`.UploadedFile`."""
        mock_file = mock.MagicMock(spec=UploadedFile,
                                   is_ancillary=False,
                                   is_removed=True,
                                   is_directory=False,
                                   is_system=False,
                                   is_active=True,
                                   path='path/to/file',
                                   workspace=mock.MagicMock())
        mock_file.workspace.get_full_path.return_value = '/tmp/foo'

        self.assertEqual(self.wks.get_path(mock_file),
                         f'{self.wks.removed_path}/path/to/file',
                         'File path is inside workspace.')
        self.assertFalse(self.wks.get_path(mock_file).startswith('/'),
                         'Must return a relative path')

    def test_get_full_path(self):
        """Can get a full path to a file on disk, using a storage adapter."""
        self.mock_storage.get_path.side_effect \
            = lambda w, f, **k: f'/foo/{w.get_path(f)}'
        mock_file = mock.MagicMock(spec=UploadedFile,
                                   is_ancillary=False,
                                   is_removed=False,
                                   is_directory=False,
                                   is_system=False,
                                   is_active=True,
                                   path='path/to/file')
        self.assertEqual(self.wks.get_full_path(mock_file),
                         f'/foo/{self.wks.source_path}/path/to/file',
                         'File path is inside workspace.')
        self.assertGreater(self.mock_storage.get_path.call_count, 0,
                           'Storage adapter get_full_path method is called')
        self.assertEqual(self.mock_storage.get_path.call_args[0],
                         (self.wks, mock_file),
                         'Workspace and uploaded file are passed')


class TestAddRemoveFiles(TestCase):
    """Test adding and removing files to/from the workspace."""

    @mock.patch('filemanager.domain.uploads.file_mutations.logging',
                mock.MagicMock())
    def setUp(self):
        """We have a vanilla workspace."""
        self.mock_strategy = mock.MagicMock()
        self.mock_storage = mock.MagicMock()
        self.mock_storage.get_path.return_value = '/tmp/foo'
        last_modified = datetime.now(UTC) - timedelta(days=1)
        self.mock_storage.get_last_modified.return_value = last_modified
        self.wks = UploadWorkspace(
            upload_id=1234,
            owner_user_id='98765',
            created_datetime=datetime.now(),
            modified_datetime=datetime.now(),
            strategy=self.mock_strategy,
            storage=self.mock_storage
        )
        self.wks.initialize()

    def test_add_single_file(self):
        """Adding a file to to the workspace."""
        last_modified = datetime.now(UTC) - timedelta(days=1)
        mock_file = mock.MagicMock(spec=UploadedFile,
                                   is_ancillary=False,
                                   is_removed=False,
                                   is_directory=False,
                                   is_system=False,
                                   last_modified=last_modified,
                                   path='path/to/file')
        self.assertEqual(self.wks.file_count, 0,
                         'There are no files in the workspace')
        self.wks.add_files(mock_file)
        self.assertEqual(self.wks.file_count, 1,
                         'There is one file in the workspace')
        self.assertEqual(self.mock_strategy.check.call_count, 1,
                         'Checker strategy is called')
        self.assertTrue(self.wks.exists('path/to/file'))

    def test_add_ancillary_file(self):
        """Adding an ancillary file to to the workspace."""
        last_modified = datetime.now(UTC) - timedelta(days=1)
        mock_file = mock.MagicMock(spec=UploadedFile,
                                   is_ancillary=True,
                                   is_removed=False,
                                   is_directory=False,
                                   is_system=False,
                                   last_modified=last_modified,
                                   path='path/to/file')
        self.assertEqual(self.wks.file_count, 0,
                         'There are no files in the workspace')
        self.wks.add_files(mock_file)
        self.assertEqual(self.wks.file_count, 0,
                         'There are no files; ancillary files are not counted')
        self.assertEqual(self.wks.ancillary_file_count, 1,
                         'There is one ancillary file')
        self.assertTrue(self.wks.exists('path/to/file', is_ancillary=True))

    def test_remove_file(self):
        """Remove a file from the workspace."""
        last_modified = datetime.now(UTC) - timedelta(days=1)
        mock_file = mock.MagicMock(spec=UploadedFile,
                                   is_ancillary=False,
                                   is_removed=False,
                                   is_directory=False,
                                   is_system=False,
                                   last_modified=last_modified,
                                   path='path/to/file')
        self.assertEqual(self.wks.file_count, 0,
                         'There are no files in the workspace')
        self.wks.add_files(mock_file)
        self.assertEqual(self.wks.file_count, 1,
                         'There is one file in the workspace')
        self.wks.remove(mock_file, 'This is the reason')
        self.assertEqual(self.wks.file_count, 0,
                         'There are no files in the workspace')
        self.assertFalse(self.wks.exists('path/to/file'),
                         'The file does not exist because it is removed')

        self.assertTrue(mock_file.is_removed, 'File is marked as removed')
        self.assertEqual(mock_file.reason_for_removal, 'This is the reason')
        self.assertEqual(self.mock_storage.remove.call_count, 1,
                         'Storage adapter move method is called')

    def test_add_files(self):
        """Add multiple files."""
        last_modified = datetime.now(UTC) - timedelta(days=1)
        mock_file = mock.MagicMock(spec=UploadedFile,
                                   is_ancillary=False,
                                   is_removed=False,
                                   is_directory=False,
                                   is_system=False,
                                   last_modified=last_modified,
                                   path='path/to/file')
        mock_file2 = mock.MagicMock(spec=UploadedFile,
                                    is_ancillary=False,
                                    is_removed=False,
                                    is_directory=False,
                                    is_system=False,
                                    last_modified=last_modified,
                                    path='path/to/file2')
        self.assertEqual(self.wks.file_count, 0,
                         'There are no files in the workspace')
        self.wks.add_files(mock_file, mock_file2)
        self.assertEqual(self.wks.file_count, 2,
                         'There are two files in the workspace')
        self.assertEqual(self.mock_strategy.check.call_count, 1,
                         'Checker strategy is called')
        self.assertTrue(self.wks.exists('path/to/file'))
        self.assertTrue(self.wks.exists('path/to/file2'))

    def test_remove_directory(self):
        """Remove a directory."""
        last_modified = datetime.now(UTC) - timedelta(days=1)
        mock_dir = mock.MagicMock(spec=UploadedFile,
                                  is_ancillary=False,
                                  is_removed=False,
                                  is_directory=True,
                                  is_system=False,
                                  last_modified=last_modified,
                                  path='path/to/dir')
        mock_file = mock.MagicMock(spec=UploadedFile,
                                   is_ancillary=False,
                                   is_removed=False,
                                   is_directory=False,
                                   is_system=False,
                                   last_modified=last_modified,
                                   path='path/to/dir/file')
        self.wks.add_files(mock_dir, mock_file)
        self.assertEqual(self.wks.file_count, 1,
                         'There is one file in the workspace (directories)'
                         ' don\'t count')
        self.wks.remove(mock_dir)
        self.assertTrue(mock_dir.is_removed, 'Directory is marked as removed')
        self.assertTrue(mock_file.is_removed,
                        'File is also removed because it is inside the'
                        ' directory')

    def test_add_file_at_subpath(self):
        """Add a file where the containing directories do not exist."""
        last_modified = datetime.now(UTC) - timedelta(days=1)
        mock_file = mock.MagicMock(spec=UploadedFile,
                                   is_ancillary=False,
                                   is_removed=False,
                                   is_directory=False,
                                   is_system=False,
                                   last_modified=last_modified,
                                   path='path/to/dir/file')
        self.wks.add_files(mock_file)
        self.assertTrue(self.wks.exists('path/'),
                        'Containing directories are added')
        self.assertTrue(self.wks.exists('path/to/'),
                        'Containing directories are added')
        self.assertTrue(self.wks.exists('path/to/dir/'),
                        'Containing directories are added')

    def test_delete_files(self):
        """Delete a file completely."""
        last_modified = datetime.now(UTC) - timedelta(days=1)
        mock_file = mock.MagicMock(spec=UploadedFile,
                                   is_ancillary=False,
                                   is_removed=False,
                                   is_directory=False,
                                   is_system=False,
                                   last_modified=last_modified,
                                   path='path/to/dir/file')
        self.wks.add_files(mock_file)
        self.wks.delete(mock_file)

        self.assertEqual(self.mock_storage.delete.call_count, 1,
                         'The underlying storage adapter is called')
        self.assertEqual(self.mock_storage.delete.call_args[0],
                         (self.wks, mock_file))
        self.assertFalse(self.wks.exists('path/to/dir/file'))
        self.assertEqual(self.wks.file_count, 0)

    def test_delete_directory(self):
        """Delete a directory completely."""
        last_modified = datetime.now(UTC) - timedelta(days=1)
        mock_dir = mock.MagicMock(spec=UploadedFile,
                                  is_ancillary=False,
                                  is_removed=False,
                                  is_directory=True,
                                  is_system=False,
                                  last_modified=last_modified,
                                  path='path/to/dir')
        mock_file = mock.MagicMock(spec=UploadedFile,
                                   is_ancillary=False,
                                   is_removed=False,
                                   is_directory=False,
                                   is_system=False,
                                   last_modified=last_modified,
                                   path='path/to/dir/file')
        mock_other_file = mock.MagicMock(spec=UploadedFile,
                                         is_ancillary=False,
                                         is_removed=False,
                                         is_directory=False,
                                         is_system=False,
                                         last_modified=last_modified,
                                         path='path/to/other/file')
        self.wks.add_files(mock_dir, mock_file, mock_other_file)
        self.assertEqual(self.wks.file_count, 2,
                         'There are two files in the workspace (directories)'
                         ' do not count')
        self.wks.delete(mock_dir)
        self.assertEqual(self.mock_storage.delete.call_count, 1,
                         'The underlying storage adapter is called')
        self.assertFalse(self.wks.exists('path/to/dir'))
        self.assertFalse(self.wks.exists('path/to/dir/file'))
        self.assertTrue(self.wks.exists('path/to/other/file'))
        self.assertEqual(self.wks.file_count, 1, 'There is only one file left')


class TestOperations(TestCase):
    """Test file operations via the workspace API."""

    @mock.patch('filemanager.domain.uploads.file_mutations.logging',
                mock.MagicMock())
    def setUp(self):
        """We have a vanilla workspace."""
        self.mock_strategy = mock.MagicMock()
        self.mock_storage = mock.MagicMock()
        self.mock_storage.get_path.return_value = '/tmp/foo'
        last_modified = datetime.now(UTC) - timedelta(days=-1)
        self.mock_storage.get_last_modified.return_value = last_modified
        self.wks = UploadWorkspace(
            upload_id=1234,
            owner_user_id='98765',
            created_datetime=datetime.now(),
            modified_datetime=last_modified,
            strategy=self.mock_strategy,
            storage=self.mock_storage
        )
        self.wks.initialize()
        self.mock_file = mock.MagicMock(spec=UploadedFile,
                                        is_ancillary=False,
                                        is_removed=False,
                                        is_directory=False,
                                        is_system=False,
                                        last_modified=last_modified,
                                        path='path/to/file')
        self.wks.add_files(self.mock_file)

    def test_open(self):
        """Get a file pointer for a file."""
        with self.wks.open(self.mock_file) as f:
            f.read()
        self.assertEqual(self.mock_storage.open.call_count, 1,
                         'Calls the underlying storage adapter')
        self.assertEqual(self.mock_storage.open.call_args[0],
                         (self.wks, self.mock_file, 'r'))

    def test_open_nonexistant(self):
        """Try to get a file pointer for a file not in this workspace."""
        last_modified = datetime.now(UTC) - timedelta(days=-1)
        mock_other_file = mock.MagicMock(spec=UploadedFile,
                                         is_ancillary=False,
                                         is_removed=False,
                                         is_directory=False,
                                         is_system=False,
                                         is_active=True,
                                         last_modified=last_modified,
                                         path='path/to/other/file')
        with self.assertRaises(ValueError):
            with self.wks.open(mock_other_file) as f:
                f.read()

    def test_compare_files(self):
        """Test comparing the contents of two files via workspace API."""
        last_modified = datetime.now(UTC) - timedelta(days=-1)
        mock_other_file = mock.MagicMock(spec=UploadedFile,
                                         is_ancillary=False,
                                         is_removed=False,
                                         is_directory=False,
                                         is_system=False,
                                         is_active=True,
                                         last_modified=last_modified,
                                         path='path/to/other/file')
        self.wks.add_files(mock_other_file)
        self.wks.cmp(self.mock_file, mock_other_file)
        self.assertEqual(self.mock_storage.cmp.call_count, 1,
                         'Calls underlying storage adapter')
        self.assertEqual(self.mock_storage.cmp.call_args[0],
                         (self.wks, self.mock_file, mock_other_file))

    def test_get_size_bytes(self):
        """Test getting the size in bytes of a file."""
        self.mock_storage.get_size_bytes.return_value = 42
        self.assertEqual(self.wks.get_size_bytes(self.mock_file), 42,
                         'Returns the size in bytes of the file')
        self.assertEqual(self.mock_storage.get_size_bytes.call_count, 1,
                         'Calls the underlying storage adapter')
        self.assertEqual(self.mock_file.size_bytes, 42,
                         'Updates the size on the UploadedFile itself')


class TestMoveFiles(TestCase):
    """Move/replace files in a workspace."""

    @mock.patch('filemanager.domain.uploads.file_mutations.logging',
                mock.MagicMock())
    def setUp(self):
        """We have a vanilla workspace."""
        self.mock_strategy = mock.MagicMock()
        self.mock_storage = mock.MagicMock()
        self.mock_storage.get_path.return_value = '/tmp/foo'
        last_modified = datetime.now(UTC) - timedelta(days=-1)
        self.mock_storage.get_last_modified.return_value = last_modified
        self.wks = UploadWorkspace(
            upload_id=1234,
            owner_user_id='98765',
            created_datetime=datetime.now(),
            modified_datetime=datetime.now(),
            strategy=self.mock_strategy,
            storage=self.mock_storage
        )
        self.wks.initialize()
        self.path = 'path/to/file'
        self.path2 = 'path/to/file2'
        self.mock_file = mock.MagicMock(spec=UploadedFile,
                                        is_ancillary=False,
                                        is_removed=False,
                                        is_directory=False,
                                        is_system=False,
                                        is_active=True,
                                        errors=[],
                                        last_modified=last_modified,
                                        path=self.path)
        self.mock_file2 = mock.MagicMock(spec=UploadedFile,
                                         is_ancillary=False,
                                         is_removed=False,
                                         is_directory=False,
                                         is_system=False,
                                         is_active=True,
                                         errors=[],
                                         last_modified=last_modified,
                                         path=self.path2)
        self.wks.add_files(self.mock_file, self.mock_file2)

    def test_replace(self):
        """Replace a file with another file."""
        self.assertEqual(self.wks.file_count, 2, 'There are two files')
        self.wks.replace(self.mock_file, self.mock_file2)
        self.assertEqual(self.mock_storage.move.call_count, 1,
                         'The underlying storage adapter is called')
        self.assertTrue(self.wks.exists(self.path), 'Target path still exists')
        self.assertFalse(self.wks.exists(self.path2),
                         'Source path does not exist')
        self.assertEqual(self.wks.get(self.path), self.mock_file2,
                         'Second file is now at the path of the first file')

    # TODO: implement these.
    # def test_replace_directory(self):
    #     """Replace a directory with another directory."""
    # def test_replace_file_with_directory(self):
    #     """Replace a file with a directory."""
    # def test_replace_file_with_directory(self):
    #     """Replace a directory with a file."""


# class TestPersist(TestCase):
#     """Test persisting files in the workspace."""

class TestUploadedFile(TestCase):
    """Test methods of the :class:`.UploadedFile`."""

    def setUp(self):
        """We have a file."""
        self.u_file = UploadedFile(mock.MagicMock(),
                                   path='foo/path/afile.txt',
                                   size_bytes=42,
                                   file_type=FileType.TEX,)

    def test_name(self):
        """Get the name of the file."""
        self.assertEqual(self.u_file.name, 'afile.txt')

    def test_ext(self):
        """Get the extension of the file."""
        self.assertEqual(self.u_file.ext, 'txt')

    def test_dir(self):
        """Get the path of the containing directory."""
        self.assertEqual(self.u_file.dir, 'foo/path/')

    def test_type_string(self):
        """Get the human-readable name of this file's type."""
        self.assertEqual(self.u_file.type_string, FileType.TEX.name)

    def test_type_string_directory(self):
        """Get the human-readable name of a directory."""
        self.u_file.is_directory = True
        self.assertEqual(self.u_file.type_string, 'Directory')

    def test_type_string_ancillary_directory(self):
        """Get the human-readable name of a directory."""
        self.u_file.path = 'anc/'
        self.u_file.is_directory = True
        self.assertEqual(self.u_file.type_string, 'Ancillary files directory')

    def test_removed_type_string(self):
        """Get the human-readable type for removed file."""
        self.u_file.is_removed = True
        self.assertEqual(self.u_file.type_string, 'Invalid File')

    def test_is_empty(self):
        """Determine whether the file is empty."""
        self.assertFalse(self.u_file.is_empty,
                         'File is not empty because it has bytes > 0')
        self.u_file.size_bytes = 0
        self.assertTrue(self.u_file.is_empty,
                        'File is empty because it has bytes == 0')
