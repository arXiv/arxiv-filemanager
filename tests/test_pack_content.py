"""Tests related to packing source content for download."""

import os
from unittest import TestCase, mock
from datetime import datetime
import tempfile
import tarfile
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

import shutil

from filemanager.domain import UploadWorkspace, FileType
from filemanager.services.storage import SimpleStorageAdapter
from filemanager.process.strategy import SynchronousCheckingStrategy
from filemanager.process.check import get_default_checkers

TEST_FILES_DIRECTORY = os.path.join(os.getcwd(), 'tests/test_files_upload')


class TestPackContent(TestCase):

    DATA_PATH = os.path.split(os.path.abspath(__file__))[0]

    def setUp(self):
        """We have a workspace."""
        self.base_path = tempfile.mkdtemp()
        self.upload_id = 5432
        self.workspace_path = os.path.join(self.base_path, str(self.upload_id))
        os.makedirs(self.workspace_path)

        self.workspace = UploadWorkspace(
            upload_id=self.upload_id,
            submission_id=None,
            owner_user_id='98765',
            archive=None,
            created_datetime=datetime.now(),
            modified_datetime=datetime.now(),
            strategy=SynchronousCheckingStrategy(),
            storage=SimpleStorageAdapter(self.base_path),
            checkers=get_default_checkers()
        )

        self.write_upload('test_files_upload/upload5.tar.gz')
        self.workspace.perform_checks()

    def tearDown(self):
        """Remove the temporary directory for files."""
        shutil.rmtree(self.base_path)

    def write_upload(self, relpath, altname=None,
                     file_type=FileType.UNKNOWN):
        """
        Write the upload into the workspace.

        We'll use a similar pattern when doing this in Flask.
        """
        filepath = os.path.join(self.DATA_PATH, relpath)
        if altname is None and '/' in relpath:
            filename = relpath.split('/')[1]
        elif altname is None:
            filename = relpath
        else:
            filename = altname
        new_file = self.workspace.create(filename, file_type=file_type)
        with self.workspace.open(new_file, 'wb') as dest:
            with open(filepath, 'rb') as source:
                dest.write(source.read())
        return new_file

    def test_pack_content(self):
        """Generate a tarball from the upload content."""
        expected = self.workspace.get_full_path(f'{self.upload_id}.tar.gz',
                                                is_system=True)

        self.workspace.source_package.pack()
        content_path = self.workspace.source_package.full_path

        self.assertEqual(content_path, expected,
                         "Returns path to content file")
        self.assertTrue(os.path.exists(content_path), "Content file exists")
        self.assertTrue(tarfile.is_tarfile(content_path),
                        "Created file is a tarball")

        tar = tarfile.open(content_path)
        self.assertIn('upload5.pdf', [ti.name for ti in tar],
                      "Includes content from original file")

    def test_content_checksum(self):
        """Generate a checksum based on the tarball content."""
        self.workspace.source_package.pack()
        self.assertEqual(self.workspace.source_package.checksum,
                         self.workspace.source_package.checksum,
                         'The checksum should remain the same.')


    def test_get_content(self):
        """Generate a pointer to the content tarball."""
        self.workspace.source_package.pack()
        with self.workspace.source_package.open() as pointer:
            self.assertTrue(hasattr(pointer, 'read'), "Yields an IO")
