"""Tests related to downloading individual files."""

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


class TestIndividualFileContentDownload(TestCase):
    """
    Test download of individual content files.

    Try our best to break things.
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
        filepath = os.path.join(self.DATA_PATH,
                                'test_files_upload/upload2.tar.gz')
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
    
    def test_file_exists(self):
        """Check if content file exists."""
        response = self.client.head(
            f"/filemanager/api/{self.upload_id}/main_a.tex/content",
            headers={'Authorization': self.token}
        )
        self.assertEqual(response.status_code, status.OK)
        self.assertIn('ETag', response.headers, "Returns an ETag header")

    def test_download_content_file(self):
        """Download content file."""
        response = self.client.get(
            f"/filemanager/api/{self.upload_id}/main_a.tex/content",
            headers={'Authorization': self.token}
        )
        self.assertEqual(response.status_code, status.OK)
        self.assertIn('ETag', response.headers, "Returns an ETag header")

        # TODO: do we need this in tests? -- Erick 2019-06-22
        #
        # Write out file (to save temporary directory where we saved
        # source_log).
        log_path = os.path.join(self.workdir, "main_a.tex")
        with open(log_path, 'wb') as fileH:
            fileH.write(response.data)

        logger.debug(f'List downloaded content directory: {self.workdir}\n')
        logger.debug(os.listdir(self.workdir))
    
    def test_head_nonexistant_content_file(self):
        """Test HEAD for file that doesn't exist."""
        response = self.client.head(
            f"/filemanager/api/{self.upload_id}/doesntexist.tex/content",
            headers={'Authorization': self.token}
        )
        self.assertEqual(response.status_code, status.NOT_FOUND,
                         "Trying to check non-existent should fail.")
    
    def test_download_nonexistant_content_file(self):
        """Test for file that doesn't exist."""

        # Try to download non-existent file anyways
        response = self.client.get(
            f"/filemanager/api/{self.upload_id}/doesntexist.tex/content",
            headers={'Authorization': self.token}
        )
        self.assertEqual(response.status_code, status.NOT_FOUND)
    
    def test_download_file_outside_workspace(self):
        """Try to be naughty and download something outside of workspace."""
        # Assume these crazy developers stick their workspaces in an obvious
        # place like /tmp/filemanagement/submissions/<upload_id>
        crazy_path = "../../../etc/passwd"
        quote_crazy_path = quote(crazy_path, safe='')
        response = self.client.head(
            f"/filemanager/api/{self.upload_id}/{quote_crazy_path}/content",
            headers={'Authorization': self.token}
        )

        self.assertEqual(response.status_code, status.NOT_FOUND,
                         "Trying to check non-existent should fail.")