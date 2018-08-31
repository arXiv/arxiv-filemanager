"""Tests specifically focused on security vulnerabilities."""

import os
from unittest import TestCase, mock
from datetime import datetime
import tempfile
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

import shutil

from filemanager.process import upload

TEST_FILES_DIRECTORY = os.path.join(os.getcwd(), 'tests/test_files_upload')


class TestRelativePaths(TestCase):
    """Test uploaded archives that include relative paths."""

    @mock.patch(f'{upload.__name__}._get_base_directory')
    def test_relative_path(self, mock_get_base_dir):
        """Uploaded tarball contains a relative path two levels up."""
        UPLOAD_BASE_DIRECTORY = tempfile.mkdtemp()
        mock_get_base_dir.return_value = UPLOAD_BASE_DIRECTORY

        file_path = os.path.join(TEST_FILES_DIRECTORY, 'relative_path.tar.gz')
        with open(file_path, 'rb') as fp:
            file = FileStorage(fp)
            # Now create upload instance
            u = upload.Upload(12345)
            # Process upload
            u.process_upload(file)
        self.assertNotIn('ir.png', os.listdir(UPLOAD_BASE_DIRECTORY),
                         'File should be prevented from escaping upload'
                         ' workspace.')
