"""Tests related to packing source content for download."""

import os
from unittest import TestCase, mock
from datetime import datetime
import tempfile
import tarfile
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

import shutil

from filemanager.process import upload

TEST_FILES_DIRECTORY = os.path.join(os.getcwd(), 'tests/test_files_upload')


class TestPackContent(TestCase):
    @mock.patch(f'{upload.__name__}._get_base_directory')
    def setUp(self, mock_get_base_dir):
        """Create a new upload workspace."""
        self.base_directory = tempfile.mkdtemp()
        mock_get_base_dir.return_value = self.base_directory
        file_path = os.path.join(TEST_FILES_DIRECTORY, 'upload5.tar.gz')
        self.upload_id = 12345
        with open(file_path, 'rb') as fp:
            # Now create upload instance
            self.upload = upload.Upload(self.upload_id)
            # Process upload
            self.upload.process_upload(FileStorage(fp))

    @mock.patch(f'{upload.__name__}._get_base_directory')
    def test_get_content_path(self, mock_get_base_dir):
        """Generate the intended path for the content tarball."""
        mock_get_base_dir.return_value = self.base_directory
        expected = os.path.join(self.base_directory, str(self.upload_id),
                                f'{self.upload_id}.tar.gz')
        self.assertEqual(self.upload.get_content_path(), expected)

    @mock.patch(f'{upload.__name__}._get_base_directory')
    def test_pack_content(self, mock_get_base_dir):
        """Generate a tarball from the upload content."""
        mock_get_base_dir.return_value = self.base_directory
        expected = os.path.join(self.base_directory, str(self.upload_id),
                                f'{self.upload_id}.tar.gz')

        content_path = self.upload.pack_content()

        self.assertEqual(content_path, expected,
                         "Returns path to content file")
        self.assertTrue(os.path.exists(content_path), "Content file exists")
        self.assertTrue(tarfile.is_tarfile(content_path),
                        "Created file is a tarball")

        tar = tarfile.open(content_path)
        self.assertIn('upload5.pdf', [ti.name for ti in tar],
                      "Includes content from original file")

    @mock.patch(f'{upload.__name__}._get_base_directory')
    def test_content_checksum(self, mock_get_base_dir):
        """Generate a checksum based on the tarball content."""
        mock_get_base_dir.return_value = self.base_directory
        self.upload.pack_content()
        checksum = self.upload.content_checksum()
        self.assertEqual(checksum, self.upload.content_checksum(),
                         'The checksum should remain the same.')


    @mock.patch(f'{upload.__name__}._get_base_directory')
    def test_get_content(self, mock_get_base_dir):
        """Generate a pointer to the content tarball."""
        mock_get_base_dir.return_value = self.base_directory
        pointer = self.upload.get_content()
        self.assertTrue(hasattr(pointer, 'read'), "Returns an IO")
