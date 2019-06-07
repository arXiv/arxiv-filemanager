"""Tests pertaining to the compressed source package."""

from unittest import TestCase
import io
import os
from datetime import datetime, timedelta
from pytz import UTC

from werkzeug.datastructures import FileStorage

from ..upload import Upload

TEST_FILES_DIRECTORY = os.path.join(os.getcwd(), 'tests/test_files_upload')


class TestCompressedUpload(TestCase):
    def setUp(self) -> None:
        """Create a new upload workspace."""
        self.workspace = Upload(12345678)
        self.fpath = os.path.join(TEST_FILES_DIRECTORY, 'upload7.tar.gz')

    def tearDown(self) -> None:
        """Remove the temporary workspace."""
        self.workspace.remove_workspace()

    def test_content_package_stale(self) -> None:
        """The content package is stale when it does not exist."""
        with open(self.fpath, 'rb') as f:
            self.workspace.process_upload(FileStorage(f))

        self.assertTrue(self.workspace.content_package_stale,
                        "The package is stale because it does not exist")
        self.workspace.pack_content()
        self.assertFalse(self.workspace.content_package_stale,
                         "The package is not stale, because we just packed it")

    def test_content_package_exists(self) -> None:
        """The content package does not exist...until it does."""
        with open(self.fpath, 'rb') as f:
            self.workspace.process_upload(FileStorage(f))

        self.assertFalse(self.workspace.content_package_exists,
                         "It does not exist yet")
        self.workspace.pack_content()
        self.assertTrue(self.workspace.content_package_exists,
                        "It certainly exists now, because we just packed it")

    def test_content_package_modified(self) -> None:
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

    def test_content_package_size(self) -> None:
        """Get the size of the package."""
        self.assertEqual(self.workspace.content_package_size, 0,
                         "There is no content")

        with open(self.fpath, 'rb') as f:
            self.workspace.process_upload(FileStorage(f))

        self.assertGreater(self.workspace.content_package_size, 0,
                           "The package has some content in it now")
        self.assertTrue(self.workspace.content_package_exists,
                        "It certainly exists now, because we just packed it")
        self.assertFalse(self.workspace.content_package_stale,
                         "The package is not stale, because we just packed it")

    def test_content_package_size_after_removing_workspace(self) -> None:
        """The entire workspace is removed."""
        with open(self.fpath, 'rb') as f:
            self.workspace.process_upload(FileStorage(f))

        self.workspace.remove_workspace()
        self.assertEqual(self.workspace.content_package_size, 0, "All gone!")

        self.workspace = Upload(12345678)
        self.assertEqual(self.workspace.content_package_size, 0, "Still gone!")

    def test_content_package_size_after_removing_all_files(self) -> None:
        """All of the files are removed from the workspace."""
        with open(self.fpath, 'rb') as f:
            self.workspace.process_upload(FileStorage(f))
        self.assertGreater(self.workspace.content_package_size, 0,
                           "The package has some content in it now")

        self.workspace.client_remove_all_files()
        self.assertEqual(self.workspace.content_package_size, 0, "All gone!")

        self.workspace = Upload(12345678)
        self.assertEqual(self.workspace.content_package_size, 0, "Still gone!")

    def test_content_package_size_after_removing_a_file(self) -> None:
        """One of the files is removed from the workspace."""
        with open(self.fpath, 'rb') as f:
            self.workspace.process_upload(FileStorage(f))
        original_size = int(self.workspace.content_package_size)
        self.assertGreater(original_size, 0,
                           "The package has some content in it now")

        self.workspace.client_remove('bicycle.gif')
        self.assertLess(self.workspace.content_package_size, original_size,
                        "The package is smaller than it was before")

    def test_get_content(self) -> None:
        """Get a pointer to the package."""
        with self.assertRaises(FileNotFoundError):
            self.workspace.get_content()

        with open(self.fpath, 'rb') as f:
            self.workspace.process_upload(FileStorage(f))

        pointer = self.workspace.get_content()
        self.assertIsInstance(pointer, io.BufferedReader)
