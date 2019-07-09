"""Tests for :mod:`.check.top_level_directory`."""

import shutil
import tempfile
from datetime import datetime
from unittest import TestCase, mock

from ....services.storage import SimpleStorageAdapter
from ....domain import UploadWorkspace, UploadedFile
from ..top_level_directory import RemoveTopLevelDirectory


class TestRemoveTopLevelDirectoryCheck(TestCase):
    """Check :class:`.RemoveTopLevelDirectory` removes top-level directory."""

    def setUp(self):
        """Create a workspace."""
        self.basedir = tempfile.mkdtemp()
        self.mock_strategy = mock.MagicMock()
        self.storage = SimpleStorageAdapter(self.basedir)

        self.workspace = UploadWorkspace(
            upload_id=1234,
            owner_user_id='98765',
            created_datetime=datetime.now(),
            modified_datetime=datetime.now(),
            strategy=self.mock_strategy,
            storage=self.storage
        )
        self.workspace.initialize()

    def tearDown(self):
        """Remove the temporary workspace files."""
        shutil.rmtree(self.basedir)

    def test_with_tld(self):
        """The source is contained in a single top-level directory."""
        self.workspace.create('foo/baz.txt', touch=True)
        self.workspace.create('foo/bar.md', touch=True)

        self.assertTrue(self.workspace.exists('foo/baz.txt'))
        self.assertTrue(self.workspace.exists('foo/bar.md'))
        self.assertFalse(self.workspace.exists('baz.txt'))
        self.assertFalse(self.workspace.exists('bar.md'))

        checker = RemoveTopLevelDirectory()
        checker.check_workspace(self.workspace)

        self.assertFalse(self.workspace.exists('foo/baz.txt'),
                         'File no longer exists in top level directory')
        self.assertFalse(self.workspace.exists('foo/bar.md'),
                         'File no longer exists in top level directory')
        self.assertTrue(self.workspace.exists('baz.txt'),
                        'File now exists in root source directory')
        self.assertTrue(self.workspace.exists('bar.md'),
                        'File now exists in root source directory')

    def test_with_tld_in_ancillary(self):
        """Ancillary files are contained in a single top-level directory."""
        self.workspace.create('foo/bz.txt', touch=True, is_ancillary=True)
        self.workspace.create('foo/bar.md', touch=True, is_ancillary=True)

        self.assertTrue(self.workspace.exists('foo/bz.txt', is_ancillary=True))
        self.assertTrue(self.workspace.exists('foo/bar.md', is_ancillary=True))
        self.assertFalse(self.workspace.exists('bz.txt', is_ancillary=True))
        self.assertFalse(self.workspace.exists('bar.md', is_ancillary=True))

        checker = RemoveTopLevelDirectory()
        checker.check_workspace(self.workspace)

        self.assertTrue(self.workspace.exists('foo/bz.txt', is_ancillary=True),
                        'File still exists in top-level directory; ancillary'
                        ' files are not affected by this check.')
        self.assertTrue(self.workspace.exists('foo/bar.md', is_ancillary=True),
                        'File still exists in top-level directory; ancillary'
                        ' files are not affected by this check.')
        self.assertFalse(self.workspace.exists('bz.txt', is_ancillary=True))
        self.assertFalse(self.workspace.exists('bar.md', is_ancillary=True))