"""Runs checks against an :class:`.UploadWorkspace`."""

import os
import tempfile
import shutil
from datetime import datetime

from unittest import TestCase, mock

from filemanager.domain import UploadWorkspace, UploadedFile, FileType
from filemanager.process.strategy import SynchronousCheckingStrategy
from filemanager.process.check import get_default_checkers
from filemanager.services.storage import SimpleStorageAdapter

parent, _ = os.path.split(os.path.abspath(__file__))
DATA_PATH = os.path.join(parent, 'test_files_upload')


class TestTarGZUpload(TestCase):
    def setUp(self):
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

    def tearDown(self):
        shutil.rmtree(self.base_path)

    def test_sample(self):
        filename = '1801.03879-1.tar.gz'
        filepath = os.path.join(DATA_PATH, filename)
        new_file = self.workspace.create(filename)
        with self.workspace.open(new_file, 'wb') as dest:
            with open(filepath, 'rb') as source:
                dest.write(source.read())

        self.workspace.perform_checks()
        type_counts = self.workspace.get_file_type_counts()
        self.assertEqual(self.workspace.file_count, type_counts['all_files'])
        self.assertEqual(type_counts[FileType.TEXAUX], 3)
        self.assertEqual(type_counts[FileType.PDF], 2)
        self.assertEqual(type_counts[FileType.LATEX2e], 1)

        self.assertEqual(self.workspace.source_type,
                         UploadWorkspace.SourceType.TEX,
                         'Upload is TeX')
