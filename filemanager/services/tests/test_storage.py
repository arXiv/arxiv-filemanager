"""Tests for :mod:`.storage`."""

from unittest import TestCase, mock
import os
import tempfile
from ...domain import UploadWorkspace
from ..storage import SimpleStorageAdapter, QuarantineStorageAdapter


class TestSimpleStorage(TestCase):
    """Test behavior of a :class:`.SimpleStorageAdapter`."""

    def setUp(self):
        """We have a :class:`.SimpleStorageAdapter`."""
        self.base_path = tempfile.mkdtemp()
        self.adapter = SimpleStorageAdapter(self.base_path)

        self.w_path = tempfile.mkdtemp(dir=self.base_path)
        self.w_rel_path = self.w_path.split(self.base_path, 1)[1].lstrip('/')
        self.mock_workspace = mock.MagicMock(spec=UploadWorkspace)
        self.mock_workspace.get_path.side_effect \
            = lambda f: f'{self.w_rel_path}/{f.path}'

    def test_open(self):
        """Get a pointer to a file."""
        _, fpath = tempfile.mkstemp(dir=self.w_path)
        rel_path = fpath.split(self.w_path, 1)[1].lstrip('/')
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
        _, fpath = tempfile.mkstemp(dir=self.w_path)
        rel_path = fpath.split(self.w_path, 1)[1].lstrip('/')
        with open(fpath, 'w') as f:
            f.write('Thanks for all the fish')
        mock_file = mock.MagicMock(path=rel_path)

        self.assertEqual(self.adapter.getsize(self.mock_workspace, mock_file),
                         os.path.getsize(fpath))

    def test_cmp(self):
        """Compare two files."""
        _, fpath = tempfile.mkstemp(dir=self.w_path)
        rel_path = fpath.split(self.w_path, 1)[1].lstrip('/')
        with open(fpath, 'w') as f:
            f.write('Thanks for all the fish')
        mock_file = mock.MagicMock(path=rel_path)

        _, fpath2 = tempfile.mkstemp(dir=self.w_path)
        rel_path2 = fpath2.split(self.w_path, 1)[1].lstrip('/')
        with open(fpath2, 'w') as f:
            f.write('Thanks for all the fiish')
        mock_file2 = mock.MagicMock(path=rel_path2)

        self.assertFalse(
            self.adapter.cmp(self.mock_workspace, mock_file, mock_file2),
            'The two files are not the same'
        )

        _, fpath3 = tempfile.mkstemp(dir=self.w_path)
        rel_path3 = fpath3.split(self.w_path, 1)[1].lstrip('/')
        with open(fpath3, 'w') as f:
            f.write('Thanks for all the fish')
        mock_file3 = mock.MagicMock(path=rel_path3)

        self.assertTrue(
            self.adapter.cmp(self.mock_workspace, mock_file, mock_file3),
            'The two fiiles are the same'
        )

    def test_delete_a_file(self):
        """Delete a file."""
        _, fpath = tempfile.mkstemp(dir=self.w_path)
        rel_path = fpath.split(self.w_path, 1)[1].lstrip('/')
        with open(fpath, 'w') as f:
            f.write('Thanks for all the fish')
        mock_file = mock.MagicMock(path=rel_path, is_directory=False)

        self.adapter.delete(self.mock_workspace, mock_file)
        self.assertFalse(os.path.exists(fpath), 'The file is deleted')

    def test_delete_a_directory(self):
        """Delete a directory."""
        dpath = tempfile.mkdtemp(dir=self.w_path)
        rel_dpath = dpath.split(self.w_path, 1)[1].lstrip('/')
        mock_dir = mock.MagicMock(path=rel_dpath, is_directory=True)

        _, fpath = tempfile.mkstemp(dir=dpath)
        with open(fpath, 'w') as f:
            f.write('Thanks for all the fish')

        self.adapter.delete(self.mock_workspace, mock_dir)
        self.assertFalse(os.path.exists(dpath), 'The directory is deleted')
        self.assertFalse(os.path.exists(fpath), 'The file is deleted')

    def test_copy_file(self):
        """Copy a file to a new path."""
        _, fpath = tempfile.mkstemp(dir=self.w_path)
        rel_path = fpath.split(self.w_path, 1)[1].lstrip('/')
        with open(fpath, 'w') as f:
            f.write('Thanks for all the fish')
        mock_file = mock.MagicMock(path=rel_path, is_directory=False)
        new_path = os.path.join(self.w_path, 'alt')
        new_rel_path = new_path.split(self.w_path, 1)[1].lstrip('/')
        mock_new_file = mock.MagicMock(path=new_rel_path)

        self.adapter.copy(self.mock_workspace, mock_file, mock_new_file)
        with self.adapter.open(self.mock_workspace, mock_new_file) as f:
            self.assertEqual(f.read(), 'Thanks for all the fish')

    def test_move_file(self):
        """Move a file to a new path."""
        _, fpath = tempfile.mkstemp(dir=self.w_path)
        rel_path = fpath.split(self.w_path, 1)[1].lstrip('/')
        rel_base_path = fpath.split(self.base_path, 1)[1].lstrip('/')
        with open(fpath, 'w') as f:
            f.write('Thanks for all the fish')
        mock_file = mock.MagicMock(path=rel_path, is_directory=False)

        new_path = os.path.join(self.w_path, 'new')
        new_rel_base_path = new_path.split(self.base_path, 1)[1].lstrip('/')
        new_rel_path = new_path.split(self.w_path, 1)[1].lstrip('/')
        self.adapter.move(self.mock_workspace, mock_file, rel_base_path,
                          new_rel_base_path)
        mock_file = mock.MagicMock(path=new_rel_path, is_directory=False)
        with self.adapter.open(self.mock_workspace, mock_file) as f:
            self.assertEqual(f.read(), 'Thanks for all the fish')

    def test_create_file(self):
        """Create a new (empty) file."""
        mock_file = mock.MagicMock(path='foo.txt', is_directory=False)
        self.adapter.create(self.mock_workspace, mock_file)
        self.assertTrue(os.path.exists(os.path.join(self.w_path, 'foo.txt')),
                        'The file is created')

    def test_create_file_without_parent_directories(self):
        """Create a new (empty) file in a non-existant directory."""
        mock_file = mock.MagicMock(path='baz/foo.txt', is_directory=False)
        self.adapter.create(self.mock_workspace, mock_file)
        self.assertTrue(
            os.path.exists(os.path.join(self.w_path, 'baz/foo.txt')),
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

        self.w_path = tempfile.mkdtemp(dir=self.q_base_path)
        self.w_rel_path = self.w_path.split(self.q_base_path, 1)[1].lstrip('/')
        self.mock_workspace = mock.MagicMock(spec=UploadWorkspace)
        self.mock_workspace.get_path.side_effect \
            = lambda f: f'{self.w_rel_path}/{f.path}'

    def test_open(self):
        """Get a pointer to a file."""
        _, fpath = tempfile.mkstemp(dir=self.w_path)
        rel_path = fpath.split(self.w_path, 1)[1].lstrip('/')
        with open(fpath, 'w') as f:
            f.write('Thanks for all the fish')
        mock_file = mock.MagicMock(path=rel_path, is_persisted=False)

        with self.adapter.open(self.mock_workspace, mock_file) as f:
            self.assertEqual(f.read(), 'Thanks for all the fish')

        for mode in ['r', 'rb', 'w', 'wb']:
            with self.adapter.open(self.mock_workspace, mock_file, mode) as f:
                self.assertEqual(f.mode, mode, 'Opens file in specified mode')

    def test_getsize(self):
        """Get the size in bytes of a file."""
        _, fpath = tempfile.mkstemp(dir=self.w_path)
        rel_path = fpath.split(self.w_path, 1)[1].lstrip('/')
        with open(fpath, 'w') as f:
            f.write('Thanks for all the fish')
        mock_file = mock.MagicMock(path=rel_path, is_persisted=False)

        self.assertEqual(self.adapter.getsize(self.mock_workspace, mock_file),
                         os.path.getsize(fpath))

    def test_cmp(self):
        """Compare two files."""
        _, fpath = tempfile.mkstemp(dir=self.w_path)
        rel_path = fpath.split(self.w_path, 1)[1].lstrip('/')
        with open(fpath, 'w') as f:
            f.write('Thanks for all the fish')
        mock_file = mock.MagicMock(path=rel_path, is_persisted=False)

        _, fpath2 = tempfile.mkstemp(dir=self.w_path)
        rel_path2 = fpath2.split(self.w_path, 1)[1].lstrip('/')
        with open(fpath2, 'w') as f:
            f.write('Thanks for all the fiish')
        mock_file2 = mock.MagicMock(path=rel_path2, is_persisted=False)

        self.assertFalse(
            self.adapter.cmp(self.mock_workspace, mock_file, mock_file2),
            'The two files are not the same'
        )

        _, fpath3 = tempfile.mkstemp(dir=self.w_path)
        rel_path3 = fpath3.split(self.w_path, 1)[1].lstrip('/')
        with open(fpath3, 'w') as f:
            f.write('Thanks for all the fish')
        mock_file3 = mock.MagicMock(path=rel_path3, is_persisted=False)

        self.assertTrue(
            self.adapter.cmp(self.mock_workspace, mock_file, mock_file3),
            'The two fiiles are the same'
        )

    def test_delete_a_file(self):
        """Delete a file."""
        _, fpath = tempfile.mkstemp(dir=self.w_path)
        rel_path = fpath.split(self.w_path, 1)[1].lstrip('/')
        with open(fpath, 'w') as f:
            f.write('Thanks for all the fish')
        mock_file = mock.MagicMock(path=rel_path, is_directory=False,
                                   is_persisted=False)

        self.adapter.delete(self.mock_workspace, mock_file)
        self.assertFalse(os.path.exists(fpath), 'The file is deleted')

    def test_delete_a_directory(self):
        """Delete a directory."""
        dpath = tempfile.mkdtemp(dir=self.w_path)
        rel_dpath = dpath.split(self.w_path, 1)[1].lstrip('/')
        mock_dir = mock.MagicMock(path=rel_dpath, is_directory=True,
                                  is_persisted=False)

        _, fpath = tempfile.mkstemp(dir=dpath)
        with open(fpath, 'w') as f:
            f.write('Thanks for all the fish')

        self.adapter.delete(self.mock_workspace, mock_dir)
        self.assertFalse(os.path.exists(dpath), 'The directory is deleted')
        self.assertFalse(os.path.exists(fpath), 'The file is deleted')

    def test_copy_file(self):
        """Copy a file to a new path."""
        _, fpath = tempfile.mkstemp(dir=self.w_path)
        rel_path = fpath.split(self.w_path, 1)[1].lstrip('/')
        with open(fpath, 'w') as f:
            f.write('Thanks for all the fish')
        mock_file = mock.MagicMock(path=rel_path, is_directory=False,
                                   is_persisted=False)
        new_path = os.path.join(self.w_path, 'alt')
        new_rel_path = new_path.split(self.w_path, 1)[1].lstrip('/')
        mock_new_file = mock.MagicMock(path=new_rel_path, is_persisted=False)

        self.adapter.copy(self.mock_workspace, mock_file, mock_new_file)
        with self.adapter.open(self.mock_workspace, mock_new_file) as f:
            self.assertEqual(f.read(), 'Thanks for all the fish')

    def test_move_file(self):
        """Move a file to a new path."""
        _, fpath = tempfile.mkstemp(dir=self.w_path)
        rel_path = fpath.split(self.w_path, 1)[1].lstrip('/')
        rel_base_path = fpath.split(self.q_base_path, 1)[1].lstrip('/')
        with open(fpath, 'w') as f:
            f.write('Thanks for all the fish')
        mock_file = mock.MagicMock(path=rel_path, is_directory=False,
                                   is_persisted=False)

        new_path = os.path.join(self.w_path, 'new')
        new_rel_base_path = new_path.split(self.q_base_path, 1)[1].lstrip('/')
        new_rel_path = new_path.split(self.w_path, 1)[1].lstrip('/')

        self.adapter.move(self.mock_workspace, mock_file, rel_base_path,
                          new_rel_base_path)

        mock_file = mock.MagicMock(path=new_rel_path, is_directory=False,
                                   is_persisted=False)
        with self.adapter.open(self.mock_workspace, mock_file) as f:
            self.assertEqual(f.read(), 'Thanks for all the fish')

    def test_create_file(self):
        """Create a new (empty) file."""
        mock_file = mock.MagicMock(path='foo.txt', is_directory=False,
                                   is_persisted=False)
        self.adapter.create(self.mock_workspace, mock_file)
        self.assertTrue(os.path.exists(os.path.join(self.w_path, 'foo.txt')),
                        'The file is created')

    def test_create_file_without_parent_directories(self):
        """Create a new (empty) file in a non-existant directory."""
        mock_file = mock.MagicMock(path='baz/foo.txt', is_directory=False,
                                   is_persisted=False)
        self.adapter.create(self.mock_workspace, mock_file)
        self.assertTrue(
            os.path.exists(os.path.join(self.w_path, 'baz/foo.txt')),
            'The file is created'
        )

    def test_persist(self):
        """Persist a file from quarantine to permanent storage."""
        _, fpath = tempfile.mkstemp(dir=self.w_path)
        rel_path = fpath.split(self.w_path, 1)[1].lstrip('/')
        with open(fpath, 'w') as f:
            f.write('Thanks for all the fish')
        mock_file = mock.MagicMock(path=rel_path, is_directory=False,
                                   is_persisted=False)
        self.adapter.persist(self.mock_workspace, mock_file)
        self.assertTrue(mock_file.is_persisted, 'File is marked as persisted')
        self.assertFalse(os.path.exists(fpath), 'Original file does not exist')
        with self.adapter.open(self.mock_workspace, mock_file, 'r') as f:
            self.assertEqual(f.read(), 'Thanks for all the fish')

    def test_persist_directory(self):
        """Persist a directory from quarantine to permanent storage."""
        dpath = tempfile.mkdtemp(dir=self.w_path)
        rel_dpath = dpath.split(self.w_path, 1)[1].lstrip('/')
        mock_dir = mock.MagicMock(path=rel_dpath, is_directory=True,
                                  is_persisted=False)

        _, fpath = tempfile.mkstemp(dir=dpath)
        rel_path = fpath.split(self.w_path, 1)[1].lstrip('/')
        with open(fpath, 'w') as f:
            f.write('Thanks for all the fish')

        mock_dir = mock.MagicMock(path=rel_dpath, is_directory=True,
                                  is_persisted=False)
        self.adapter.persist(self.mock_workspace, mock_dir)
        self.assertTrue(mock_dir.is_persisted, 'Dir is marked as persisted')
        self.assertFalse(os.path.exists(fpath), 'Original dir does not exist')

        # Child file is also moved.
        mock_file = mock.MagicMock(path=rel_path, is_directory=False,
                                   is_persisted=True)
        with self.adapter.open(self.mock_workspace, mock_file, 'r') as f:
            self.assertEqual(f.read(), 'Thanks for all the fish')
