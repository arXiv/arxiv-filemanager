"""Tests ancillary file handling."""

import os
from unittest import TestCase, mock
from datetime import datetime
import tempfile
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

import shutil

from filemanager.process import upload


class TestUploadAncillaryFile(TestCase):
    """Test uploading an ancillary file."""

    @mock.patch(f'{upload.__name__}._get_base_directory')
    def test_upload_ancillary(self, mock_get_base_dir):
        """Uploaded file is marked as ancillary."""
        UPLOAD_BASE_DIRECTORY = tempfile.mkdtemp()
        mock_get_base_dir.return_value = UPLOAD_BASE_DIRECTORY
        _, fpath = tempfile.mkstemp(suffix='.md')
        with open(fpath, 'w') as f:
            f.write('Some content')

        with open(fpath, 'rb') as fp:
            file = FileStorage(fp)
            # Now create upload instance
            u = upload.Upload(12345)
            # Process upload
            u.process_upload(file, ancillary=True)

        ancillary_path = u.get_ancillary_path()
        _, fname = os.path.split(fpath)
        self.assertIn(fname, os.listdir(ancillary_path),
                      'File should be stored in the ancillary directory')
