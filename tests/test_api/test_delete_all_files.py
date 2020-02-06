"""Tests related to deleting all files in a workspace."""

import os
import json
import shutil
import tempfile
import logging
from datetime import datetime
from unittest import TestCase, mock
from http import HTTPStatus as status

import jsonschema
from requests.utils import quote
from pytz import UTC

from arxiv.users import domain, auth

from filemanager.factory import create_web_app
from filemanager.services import database

from .util import generate_token

logger = logging.getLogger(__name__)
logger.setLevel(int(os.environ.get('LOGLEVEL', '20')))


class TestDeleteAllFiles(TestCase):
    """
    Test delete file operation.

    These tests will focus on triggering delete failures.
    """

    DATA_PATH = os.path.join(os.path.split(os.path.abspath(__file__))[0], '..')

    def setUp(self) -> None:
        """Initialize the Flask application, and get a client for testing."""
        self.workdir = tempfile.mkdtemp()
        self.server_name = 'fooserver.localdomain'
        self.app = create_web_app()
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['SERVER_NAME'] = self.server_name
        self.app.config['STORAGE_BASE_PATH'] = self.workdir

        # There is a bug in arxiv.base where it doesn't pick up app config
        # parameters. Until then, we pass it to os.environ.
        os.environ['JWT_SECRET'] = self.app.config.get('JWT_SECRET')
        self.client = self.app.test_client()
        # self.app.app_context().push()
        with self.app.app_context():
            database.db.create_all()

        with open('schema/resources/Workspace.json') as f:
            self.schema = json.load(f)

        # Create a token for writing to upload workspace
        self.token = generate_token(self.app, [auth.scopes.READ_UPLOAD,
                                               auth.scopes.WRITE_UPLOAD,
                                               auth.scopes.DELETE_UPLOAD_FILE])

        # Upload a gzipped tar archive package containing files to delete.
        filepath = os.path.join(
            self.DATA_PATH,
            'test_files_upload/UploadWithANCDirectory.tar.gz'
        )
        fname = os.path.basename(filepath)

        # Upload some files so we can download them.
        response = self.client.post(
            '/filemanager/api/',
            data={'file': (open(filepath, 'rb'), fname),},
            headers={'Authorization': self.token},
            content_type='multipart/form-data'
        )

        self.assertEqual(response.status_code, status.CREATED,
                         "Accepted and processed uploaded Submission Contents")

        self.original_upload_data = json.loads(response.data)
        self.upload_id = self.original_upload_data['upload_id']

    def tearDown(self):
        """Delete the workspace."""
        # Create admin token for deleting upload workspace
        admin_token = generate_token(self.app, [
            auth.scopes.READ_UPLOAD,
            auth.scopes.WRITE_UPLOAD,
            auth.scopes.DELETE_UPLOAD_WORKSPACE.as_global()
        ])

        response = self.client.delete(f"/filemanager/api/{self.upload_id}",
                                      headers={'Authorization': admin_token})

        # This cleans out the workspace. Comment out if you want to inspect
        # files in workspace. Source log is saved to 'deleted_workspace_logs'
        # directory.
        self.assertEqual(response.status_code, status.OK,
                         "Accepted request to delete workspace.")

    def test_delete_all_files(self):
        """Delete all files in my workspace (normal)."""
        response = self.client.post(
            f"/filemanager/api/{self.upload_id}/delete_all",
            headers={'Authorization': self.token},
            content_type='multipart/form-data'
        )

        self.assertEqual(response.status_code, status.OK,
                         "Delete all user-uploaded files.")
        self.assertNotEqual(json.loads(response.data)['source_format'], 'tex',
                            'Source format should be cleared on a delete_all')

        response = self.client.get(f"/filemanager/api/{self.upload_id}",
                                   headers={'Authorization': self.token})
        self.assertEqual(response.status_code, status.OK,
                         'Workspace is still available')
        response_data = json.loads(response.data)
        self.assertEqual(len(response_data['files']), 0,
                         'All of the files are deleted')

        # Try an delete an individual file ...we'll know if delete all files really worked.
        public_file_path = "anc/manuscript_Na2.7Ru4O9.tex"
        public_file_path = quote(public_file_path, safe='')
        response = self.client.delete(
            f"/filemanager/api/{self.upload_id}/{public_file_path}",
            headers={'Authorization': self.token}
        )
        logger.debug(f"Delete already deleted file in subdirectory anc"
                     f" Response: '{public_file_path}'\n{response.data}\n")
        self.assertEqual(response.status_code, status.NOT_FOUND,
                         f"Delete already deleted file in subdirectory:"
                         f" '{public_file_path}'.")

        expected_data = {'reason': 'file not found'}
        self.assertDictEqual(json.loads(response.data), expected_data)

    def test_delete_all_nonexistant_files(self):
        """
        Delete all files from a non-existant workspace.

        There are really not many exceptions we can generate as long as the
        upload workspace exists. If upload workspace exists this command will
        remove all files and directories under src directory. At this point I
        don't anticipate generating exception when src directory is already
        empty.

        """
        # Delete all files in my workspace (that doesn't exist)
        response = self.client.post(f"/filemanager/api/999999/delete_all",
                                    headers={'Authorization': self.token},
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, status.NOT_FOUND,
                         "Delete all user-uploaded files for non-existent"
                         " workspace.")

        expected_data = {'reason': 'workspace not found'}
        self.assertDictEqual(json.loads(response.data), expected_data)