"""Tests for :mod:`.storage`."""

from unittest import TestCase, mock
import os
import shutil
from datetime import datetime
import tempfile
from ...domain import UploadWorkspace, UploadedFile
from ..storage import SimpleStorageAdapter, QuarantineStorageAdapter


class TestSimpleStorage(TestCase):
    """Test behavior of a :class:`.SimpleStorageAdapter`."""

    def setUp(self):
        """We have a :class:`.SimpleStorageAdapter`."""
        self.base_path = tempfile.mkdtemp()
        self.adapter = SimpleStorageAdapter(self.base_path)

        self.workspace_path = tempfile.mkdtemp(dir=self.base_path)
        self.source_path = os.path.join(self.workspace_path, 'src')
        self.upload_id \
            = self.workspace_path.split(self.base_path, 1)[1].lstrip('/')
        self.mock_workspace = mock.MagicMock(
            spec=UploadWorkspace,
            source_path=f'{self.upload_id}/src',
            ancillary_path=f'{self.upload_id}/src/anc',
            removed_path=f'{self.upload_id}/removed',
            base_path=str(self.upload_id)
        )

        def get_path(f, *a, is_ancillary=False, is_removed=False):
            pre = 'src'
            if is_ancillary is True:
                pre = 'src/anc'
            if is_removed is True:
                pre = 'removed'

            if hasattr(f, 'path'):
                return f'{self.upload_id}/{pre}/{f.path}'
            return f'{self.upload_id}/{pre}/{f}'

        self.mock_workspace.get_path.side_effect = get_path
        os.makedirs(self.source_path)

    def test_open(self):
        """Get a pointer to a file."""
        _, fpath = tempfile.mkstemp(dir=self.source_path)
        rel_path = fpath.split(self.source_path, 1)[1].lstrip('/')
        with open(fpath, 'w') as f:
            f.write('Thanks for all the fish')
        mock_file = mock.MagicMock(path=rel_path)

        with self.adapter.open(self.mock_workspace, mock_file) as f:
            self.assertEqual(f.read(), 'Thanks for all the fish')

        for mode in ['r', 'rb', 'w', 'wb']:
            with self.adapter.open(self.mock_workspace, mock_file, mode) as f:
                self.assertEqual(f.mode, mode, 'Opens file in specified mode')

    def test_getsize(self):
        """Get the size in bytes of a file."""
        _, fpath = tempfile.mkstemp(dir=self.source_path)
        rel_path = fpath.split(self.source_path, 1)[1].lstrip('/')
        with open(fpath, 'w') as f:
            f.write('Thanks for all the fish')
        mock_file = mock.MagicMock(path=rel_path)

        self.assertEqual(self.adapter.getsize(self.mock_workspace, mock_file),
                         os.path.getsize(fpath))

    def test_cmp(self):
        """Compare two files."""
        _, fpath = tempfile.mkstemp(dir=self.source_path)
        rel_path = fpath.split(self.source_path, 1)[1].lstrip('/')
        with open(fpath, 'w') as f:
            f.write('Thanks for all the fish')
        mock_file = mock.MagicMock(path=rel_path)

        _, fpath2 = tempfile.mkstemp(dir=self.source_path)
        rel_path2 = fpath2.split(self.source_path, 1)[1].lstrip('/')
        with open(fpath2, 'w') as f:
            f.write('Thanks for all the fiish')
        mock_file2 = mock.MagicMock(path=rel_path2)

        self.assertFalse(
            self.adapter.cmp(self.mock_workspace, mock_file, mock_file2),
            'The two files are not the same'
        )

        _, fpath3 = tempfile.mkstemp(dir=self.source_path)
        rel_path3 = fpath3.split(self.source_path, 1)[1].lstrip('/')
        with open(fpath3, 'w') as f:
            f.write('Thanks for all the fish')
        mock_file3 = mock.MagicMock(path=rel_path3)

        self.assertTrue(
            self.adapter.cmp(self.mock_workspace, mock_file, mock_file3),
            'The two fiiles are the same'
        )

    def test_delete_a_file(self):
        """Delete a file."""
        _, fpath = tempfile.mkstemp(dir=self.source_path)
        rel_path = fpath.split(self.source_path, 1)[1].lstrip('/')
        with open(fpath, 'w') as f:
            f.write('Thanks for all the fish')
        mock_file = mock.MagicMock(path=rel_path, is_directory=False)

        self.adapter.delete(self.mock_workspace, mock_file)
        self.assertFalse(os.path.exists(fpath), 'The file is deleted')

    def test_delete_a_directory(self):
        """Delete a directory."""
        dpath = tempfile.mkdtemp(dir=self.source_path)
        rel_dpath = dpath.split(self.source_path, 1)[1].lstrip('/')
        mock_dir = mock.MagicMock(path=rel_dpath, is_directory=True)

        _, fpath = tempfile.mkstemp(dir=dpath)
        with open(fpath, 'w') as f:
            f.write('Thanks for all the fish')

        self.adapter.delete(self.mock_workspace, mock_dir)
        self.assertFalse(os.path.exists(dpath), 'The directory is deleted')
        self.assertFalse(os.path.exists(fpath), 'The file is deleted')

    def test_copy_file(self):
        """Copy a file to a new path."""
        _, fpath = tempfile.mkstemp(dir=self.source_path)
        rel_path = fpath.split(self.source_path, 1)[1].lstrip('/')
        with open(fpath, 'w') as f:
            f.write('Thanks for all the fish')
        mock_file = mock.MagicMock(path=rel_path, is_directory=False)
        new_path = os.path.join(self.source_path, 'alt')
        new_rel_path = new_path.split(self.source_path, 1)[1].lstrip('/')
        mock_new_file = mock.MagicMock(path=new_rel_path)

        self.adapter.copy(self.mock_workspace, mock_file, mock_new_file)
        with self.adapter.open(self.mock_workspace, mock_new_file) as f:
            self.assertEqual(f.read(), 'Thanks for all the fish')

    def test_move_file(self):
        """Move a file to a new path."""
        _, fpath = tempfile.mkstemp(dir=self.source_path)
        rel_path = fpath.split(self.source_path, 1)[1].lstrip('/')
        with open(fpath, 'w') as f:
            f.write('Thanks for all the fish')
        mock_file = mock.MagicMock(path=rel_path,
                                   is_directory=False,
                                   is_ancillary=False,
                                   is_removed=False)

        new_path = os.path.join(self.source_path, 'new')
        new_r_path = new_path.split(self.source_path, 1)[1].lstrip('/')
        self.adapter.move(self.mock_workspace, mock_file, rel_path, new_r_path)

        mock_file.path = new_r_path
        with self.adapter.open(self.mock_workspace, mock_file) as f:
            self.assertEqual(f.read(), 'Thanks for all the fish')

    def test_create_file(self):
        """Create a new (empty) file."""
        mock_file = mock.MagicMock(path='foo.txt', is_directory=False)
        self.adapter.create(self.mock_workspace, mock_file)
        self.assertTrue(
            os.path.exists(os.path.join(self.source_path, 'foo.txt')),
            'The file is created'
        )

    def test_create_file_without_parent_directories(self):
        """Create a new (empty) file in a non-existant directory."""
        mock_file = mock.MagicMock(path='baz/foo.txt',
                                   is_directory=False,
                                   is_ancillary=False,
                                   is_removed=False)
        self.adapter.create(self.mock_workspace, mock_file)
        self.assertTrue(
            os.path.exists(os.path.join(self.source_path, 'baz/foo.txt')),
            'The file is created'
        )


class TestQuarantineStorage(TestCase):
    """Test behavior of a :class:`.QuarantineStorageAdapter`."""

    def setUp(self):
        """We have a :class:`.QuarantineStorageAdapter`."""
        self.base_path = tempfile.mkdtemp(prefix='permanent')
        self.q_base_path = tempfile.mkdtemp(prefix='quarantine')
        self.adapter = QuarantineStorageAdapter(self.base_path,
                                                self.q_base_path)
        self.upload_id = 1234
        self.workspace_path = os.path.join(self.base_path, str(self.upload_id))
        self.q_workspace_path \
            = os.path.join(self.q_base_path, str(self.upload_id))
        self.source_path = os.path.join(self.workspace_path, 'src')
        self.q_source_path = os.path.join(self.q_workspace_path, 'src')

        self.mock_workspace = mock.MagicMock(
            spec=UploadWorkspace,
            source_path=f'{self.upload_id}/src',
            ancillary_path=f'{self.upload_id}/src/anc',
            removed_path=f'{self.upload_id}/removed',
            base_path=str(self.upload_id)
        )

        def get_path(f, *a, is_ancillary=False, is_removed=False):
            pre = 'src'
            if is_ancillary is True:
                pre = 'src/anc'
            if is_removed is True:
                pre = 'removed'

            if hasattr(f, 'path'):
                return f'{self.upload_id}/{pre}/{f.path}'
            return f'{self.upload_id}/{pre}/{f}'

        self.mock_workspace.get_path.side_effect = get_path
        os.makedirs(self.source_path)
        os.makedirs(self.q_source_path)

    def test_open(self):
        """Get a pointer to a file."""
        _, fpath = tempfile.mkstemp(dir=self.q_source_path)
        rel_path = fpath.split(self.q_source_path, 1)[1].lstrip('/')
        with open(fpath, 'w') as f:
            f.write('Thanks for all the fish')
        mock_file = mock.MagicMock(path=rel_path, is_persisted=False,
                                   is_directory=False,
                                   is_ancillary=False,
                                   is_removed=False,
                                   spec=UploadedFile)

        with self.adapter.open(self.mock_workspace, mock_file) as f:
            self.assertEqual(f.read(), 'Thanks for all the fish')

        for mode in ['r', 'rb', 'w', 'wb']:
            with self.adapter.open(self.mock_workspace, mock_file, mode) as f:
                self.assertEqual(f.mode, mode, 'Opens file in specified mode')

    def test_getsize(self):
        """Get the size in bytes of a file."""
        _, fpath = tempfile.mkstemp(dir=self.q_source_path)
        rel_path = fpath.split(self.q_source_path, 1)[1].lstrip('/')
        with open(fpath, 'w') as f:
            f.write('Thanks for all the fish')
        mock_file = mock.MagicMock(path=rel_path, is_persisted=False,
                                   is_directory=False,
                                   is_ancillary=False,
                                   is_removed=False,
                                   spec=UploadedFile)

        self.assertEqual(self.adapter.getsize(self.mock_workspace, mock_file),
                         os.path.getsize(fpath))

    def test_cmp(self):
        """Compare two files."""
        _, fpath = tempfile.mkstemp(dir=self.q_source_path)
        rel_path = fpath.split(self.q_source_path, 1)[1].lstrip('/')
        with open(fpath, 'w') as f:
            f.write('Thanks for all the fish')
        mock_file = mock.MagicMock(path=rel_path, is_persisted=False,
                                   is_directory=False,
                                   is_ancillary=False,
                                   is_removed=False,
                                   spec=UploadedFile)

        _, fpath2 = tempfile.mkstemp(dir=self.q_source_path)
        rel_path2 = fpath2.split(self.q_source_path, 1)[1].lstrip('/')
        with open(fpath2, 'w') as f:
            f.write('Thanks for all the fiish')
        mock_file2 = mock.MagicMock(path=rel_path2, is_persisted=False,
                                    is_directory=False,
                                    is_ancillary=False,
                                    is_removed=False,
                                    spec=UploadedFile)

        self.assertFalse(
            self.adapter.cmp(self.mock_workspace, mock_file, mock_file2),
            'The two files are not the same'
        )

        _, fpath3 = tempfile.mkstemp(dir=self.q_source_path)
        rel_path3 = fpath3.split(self.q_source_path, 1)[1].lstrip('/')
        with open(fpath3, 'w') as f:
            f.write('Thanks for all the fish')
        mock_file3 = mock.MagicMock(path=rel_path3, is_persisted=False,
                                    is_directory=False,
                                    is_ancillary=False,
                                    is_removed=False,
                                    spec=UploadedFile)

        self.assertTrue(
            self.adapter.cmp(self.mock_workspace, mock_file, mock_file3),
            'The two fiiles are the same'
        )
    #
    def test_delete_a_file(self):
        """Delete a file."""
        _, fpath = tempfile.mkstemp(dir=self.q_source_path)
        rel_path = fpath.split(self.q_source_path, 1)[1].lstrip('/')
        with open(fpath, 'w') as f:
            f.write('Thanks for all the fish')
        mock_file = mock.MagicMock(path=rel_path, is_directory=False,
                                   is_ancillary=False,
                                   is_removed=False,
                                   is_persisted=False,
                                   spec=UploadedFile)

        self.adapter.delete(self.mock_workspace, mock_file)
        self.assertFalse(os.path.exists(fpath), 'The file is deleted')

    def test_delete_a_directory(self):
        """Delete a directory."""
        dpath = tempfile.mkdtemp(dir=self.q_source_path)
        rel_dpath = dpath.split(self.q_source_path, 1)[1].lstrip('/')
        mock_dir = mock.MagicMock(path=rel_dpath, is_directory=True,
                                  is_persisted=False,
                                  is_ancillary=False,
                                  is_removed=False,
                                  spec=UploadedFile)

        _, fpath = tempfile.mkstemp(dir=dpath)
        with open(fpath, 'w') as f:
            f.write('Thanks for all the fish')

        self.adapter.delete(self.mock_workspace, mock_dir)
        self.assertFalse(os.path.exists(dpath), 'The directory is deleted')
        self.assertFalse(os.path.exists(fpath), 'The file is deleted')

    def test_copy_file(self):
        """Copy a file to a new path."""
        _, fpath = tempfile.mkstemp(dir=self.q_source_path)
        rel_path = fpath.split(self.q_source_path, 1)[1].lstrip('/')
        with open(fpath, 'w') as f:
            f.write('Thanks for all the fish')
        mock_file = mock.MagicMock(path=rel_path, is_directory=False,
                                   is_persisted=False,
                                   is_ancillary=False,
                                   is_removed=False,
                                   spec=UploadedFile)
        new_path = os.path.join(self.q_source_path, 'alt')
        new_rel_path = new_path.split(self.q_source_path, 1)[1].lstrip('/')
        mock_new_file = mock.MagicMock(path=new_rel_path,
                                       is_persisted=False,
                                       is_directory=False,
                                       is_ancillary=False,
                                       is_removed=False,
                                       spec=UploadedFile)

        self.adapter.copy(self.mock_workspace, mock_file, mock_new_file)
        with self.adapter.open(self.mock_workspace, mock_new_file) as f:
            self.assertEqual(f.read(), 'Thanks for all the fish')

    def test_move_file(self):
        """Move a file to a new path."""
        _, fpath = tempfile.mkstemp(dir=self.q_source_path)
        rel_path = fpath.split(self.q_source_path, 1)[1].lstrip('/')
        rel_base_path = fpath.split(self.q_base_path, 1)[1].lstrip('/')
        with open(fpath, 'w') as f:
            f.write('Thanks for all the fish')
        mock_file = mock.MagicMock(path=rel_path, is_directory=False,
                                   is_persisted=False,
                                   is_ancillary=False,
                                   is_removed=False,
                                   spec=UploadedFile)

        new_path = os.path.join(self.q_source_path, 'new')
        new_rel_base_path = new_path.split(self.q_base_path, 1)[1].lstrip('/')
        new_r_path = new_path.split(self.q_source_path, 1)[1].lstrip('/')

        self.adapter.move(self.mock_workspace, mock_file, rel_path, new_r_path)

        mock_file = mock.MagicMock(path=new_r_path, is_directory=False,
                                   is_persisted=False,
                                   is_ancillary=False,
                                   is_removed=False,
                                   spec=UploadedFile)
        with self.adapter.open(self.mock_workspace, mock_file) as f:
            self.assertEqual(f.read(), 'Thanks for all the fish')

    def test_create_file(self):
        """Create a new (empty) file."""
        mock_file = mock.MagicMock(path='foo.txt', is_directory=False,
                                   is_persisted=False,
                                   is_ancillary=False,
                                   is_removed=False,
                                   spec=UploadedFile)
        self.adapter.create(self.mock_workspace, mock_file)
        self.assertTrue(
            os.path.exists(os.path.join(self.q_source_path, 'foo.txt')),
            'The file is created'
        )

    def test_create_file_without_parent_directories(self):
        """Create a new (empty) file in a non-existant directory."""
        mock_file = mock.MagicMock(path='baz/foo.txt', is_directory=False,
                                   is_persisted=False,
                                   is_ancillary=False,
                                   is_removed=False,
                                   spec=UploadedFile)
        self.adapter.create(self.mock_workspace, mock_file)
        self.assertTrue(
            os.path.exists(os.path.join(self.q_source_path, 'baz/foo.txt')),
            'The file is created'
        )

    def test_persist(self):
        """Persist a file from quarantine to permanent storage."""
        _, fpath = tempfile.mkstemp(dir=self.q_source_path)
        rel_path = fpath.split(self.q_source_path, 1)[1].lstrip('/')
        with open(fpath, 'w') as f:
            f.write('Thanks for all the fish')
        mock_file = mock.MagicMock(path=rel_path, is_directory=False,
                                   is_persisted=False,
                                   is_ancillary=False,
                                   is_removed=False,
                                   spec=UploadedFile)
        self.adapter.persist(self.mock_workspace, mock_file)
        self.assertTrue(mock_file.is_persisted, 'File is marked as persisted')
        self.assertFalse(os.path.exists(fpath), 'Original file does not exist')
        with self.adapter.open(self.mock_workspace, mock_file, 'r') as f:
            self.assertEqual(f.read(), 'Thanks for all the fish')

    def test_persist_directory(self):
        """Persist a directory from quarantine to permanent storage."""
        dpath = tempfile.mkdtemp(dir=self.q_source_path)
        rel_dpath = dpath.split(self.q_source_path, 1)[1].lstrip('/')
        mock_dir = mock.MagicMock(path=rel_dpath, is_directory=True,
                                  is_persisted=False,
                                  is_ancillary=False,
                                  is_removed=False,
                                  spec=UploadedFile)

        _, fpath = tempfile.mkstemp(dir=dpath)
        rel_path = fpath.split(self.q_source_path, 1)[1].lstrip('/')
        with open(fpath, 'w') as f:
            f.write('Thanks for all the fish')

        mock_dir = mock.MagicMock(path=rel_dpath, is_directory=True,
                                  is_persisted=False,
                                  is_ancillary=False,
                                  is_removed=False,
                                  spec=UploadedFile)
        self.adapter.persist(self.mock_workspace, mock_dir)
        self.assertTrue(mock_dir.is_persisted, 'Dir is marked as persisted')
        self.assertFalse(os.path.exists(fpath), 'Original dir does not exist')

        # Child file is also moved.
        mock_file = mock.MagicMock(path=rel_path,
                                   spec=UploadedFile,
                                   is_directory=False,
                                   is_persisted=True,
                                   is_ancillary=False,
                                   is_removed=False)
        with self.adapter.open(self.mock_workspace, mock_file, 'r') as f:
            self.assertEqual(f.read(), 'Thanks for all the fish')


class TestStorageWithWorkspace(TestCase):
    """Test using a SimpleStorageAdapter with an UploadWorkspace."""

    def setUp(self):
        """We have a :class:`.SimpleStorageAdapter`."""
        self.base_path = tempfile.mkdtemp()
        self.adapter = SimpleStorageAdapter(self.base_path)
        self.mock_strategy = mock.MagicMock()
        self.wks = UploadWorkspace(
            upload_id=1234,
            submission_id=None,
            owner_user_id='98765',
            archive=None,
            created_datetime=datetime.now(),
            modified_datetime=datetime.now(),
            strategy=self.mock_strategy,
            storage=self.adapter
        )

    def tearDown(self):
        shutil.rmtree(self.base_path)

    def test_get_source_path(self):
        """Source path is based on the upload ID and class-specific prefix."""
        self.assertEqual(self.wks.source_path,
                         f'{self.wks.upload_id}/{self.wks.SOURCE_PREFIX}')
        self.assertFalse(self.wks.source_path.startswith('/'),
                         'Must return a relative path')

    def test_get_paths(self):
        self.assertTrue(self.wks.get_full_path('foo')
                        .endswith(f'/{self.wks.upload_id}/src/foo'))
        self.assertTrue(self.wks.get_full_path('foo', is_ancillary=True)
                        .endswith(f'/{self.wks.upload_id}/src/anc/foo'))
        self.assertTrue(self.wks.get_full_path('foo', is_removed=True)
                        .endswith(f'/{self.wks.upload_id}/removed/foo'))
        self.assertTrue(self.wks.get_full_path('foo', is_persisted=True)
                        .endswith(f'/{self.wks.upload_id}/src/foo'))

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
                                   path='path/to/file')
        self.assertEqual(self.wks.get_path(mock_file),
                         f'{self.wks.removed_path}/path/to/file',
                         'File path is inside workspace.')
        self.assertFalse(self.wks.get_path(mock_file).startswith('/'),
                         'Must return a relative path')

    def test_get_full_path(self):
        """Can get a full path to a file on disk, using a storage adapter."""
        u_file = self.wks.create('path/to/file', is_ancillary=False,
                                 is_directory=False,)
        self.assertEqual(
            self.wks.get_full_path(u_file),
            os.path.join(self.base_path,
                         f'{self.wks.source_path}/path/to/file'),
            'File path is inside workspace.'
        )
