"""Tests pertaining to the compressed source package."""

from unittest import TestCase
import io
import time
import os
from datetime import datetime, timedelta
from pytz import UTC

from werkzeug.datastructures import FileStorage

from ..upload import Upload

TEST_FILES_DIRECTORY = os.path.join(os.getcwd(), 'tests/test_files_upload')


class TestCompressedUpload(TestCase):
    def setUp(self):
        """Create a new upload workspace."""
        self.workspace = Upload(12345678)
        self.fpath = os.path.join(TEST_FILES_DIRECTORY, 'upload7.tar.gz')

    def tearDown(self):
        """Remove the temporary workspace."""
        self.workspace.remove_workspace()

    def test_content_package_stale(self):
        """The content package is stale when it does not exist."""
        with open(self.fpath, 'rb') as f:
            self.workspace.process_upload(FileStorage(f))

        self.assertTrue(self.workspace.content_package_stale,
                        "The package is stale because it does not exist")
        self.workspace.pack_content()
        self.assertFalse(self.workspace.content_package_stale,
                         "The package is not stale, because we just packed it")

    def test_content_package_exists(self):
        """The content package does not exist...until it does."""
        with open(self.fpath, 'rb') as f:
            self.workspace.process_upload(FileStorage(f))

        self.assertFalse(self.workspace.content_package_exists,
                         "It does not exist yet")
        self.workspace.pack_content()
        self.assertTrue(self.workspace.content_package_exists,
                        "It certainly exists now, because we just packed it")

    def test_content_package_modified(self):
        """Get the datetime when the content was last modified."""
        with open(self.fpath, 'rb') as f:
            self.workspace.process_upload(FileStorage(f))

        with self.assertRaises(FileNotFoundError):
            # The package does not exist yet.
            self.workspace.content_package_modified
        self.workspace.pack_content()
        delta = datetime.now(UTC) - self.workspace.content_package_modified
        self.assertLess(delta, timedelta(seconds=1),
                        "The package was just modified")

    def test_content_package_size(self):
        """Get the size of the package."""
        self.assertLess(self.workspace.content_package_size, 2_000,
                        "The package is basically empty, but it has a"
                        " directory inside that takes some space.")

        # Staleness has seconds precision, so it won't register as stale unless
        # we give it (literally) a second.
        time.sleep(1)
        with open(self.fpath, 'rb') as f:
            self.workspace.process_upload(FileStorage(f))

        self.assertGreater(self.workspace.content_package_size, 2_000,
                           "The package has some content in it now")
        self.assertTrue(self.workspace.content_package_exists,
                        "It certainly exists now, because we just packed it")
        self.assertFalse(self.workspace.content_package_stale,
                         "The package is not stale, because we just packed it")

        self.workspace.remove_workspace()
        self.assertEqual(self.workspace.content_package_size, 0,
                         "It's all gone")
