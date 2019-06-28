"""Tests related to deleting a workspace."""

import os
import json
import shutil
import tempfile
import logging
from datetime import datetime
from unittest import TestCase, mock
from http import HTTPStatus as status

from pytz import UTC
import jsonschema

from arxiv.users import domain, auth

from filemanager.factory import create_web_app
from filemanager.services import database

from .util import generate_token

logger = logging.getLogger(__name__)
logger.setLevel(int(os.environ.get('LOGLEVEL', '20')))


class TestDeleteWorkspace(TestCase):
    """Test deletion of the workspace."""

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

        # Upload some files so we can delete them
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
        """
        Clean up!

        This cleans out the workspace. Comment out if you want to inspect files
        in workspace. Source log is saved to 'deleted_workspace_logs' directory.
        """
        shutil.rmtree(self.workdir)

    def test_delete_workspace(self):
        """Make a DELETE request with sufficient privileges."""
        admin_token = generate_token(self.app, [
            auth.scopes.READ_UPLOAD,
            auth.scopes.WRITE_UPLOAD,
            auth.scopes.READ_UPLOAD_SERVICE_LOGS,
            auth.scopes.DELETE_UPLOAD_WORKSPACE.as_global()
        ])

        response = self.client.delete(f"/filemanager/api/{self.upload_id}",
                                      headers={'Authorization': admin_token})

        self.assertEqual(response.status_code, status.OK,
                         "Accepted request to delete workspace.")

    def test_delete_workspace_underprivileged(self):
        """Make a DELETE request without sufficient privileges."""
        admin_token = generate_token(self.app, [
            auth.scopes.READ_UPLOAD,
            auth.scopes.WRITE_UPLOAD,
            auth.scopes.READ_UPLOAD_SERVICE_LOGS
        ])

        response = self.client.delete(f"/filemanager/api/{self.upload_id}",
                                      headers={'Authorization': admin_token})

        self.assertEqual(response.status_code, status.FORBIDDEN,
                         "Accepted request to delete workspace.")


# TODO: Need to add more tests for auth/z for submitter and admin
class TestDeleteAnotherWorkspace(TestCase):
    """Tests for deleting the entire workspace."""

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
        self.admin_token = generate_token(self.app, [
            auth.scopes.READ_UPLOAD,
            auth.scopes.WRITE_UPLOAD,
            auth.scopes.DELETE_UPLOAD_WORKSPACE.as_global()
        ])

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
        self.client.delete(
            f"/filemanager/api/{self.upload_id}",
            headers={'Authorization': self.admin_token}
        )

    def test_delete_workspace(self):
        """Request to delete workspace with valid authz."""
        response = self.client.delete(
            f"/filemanager/api/{self.upload_id}",
            headers={'Authorization': self.admin_token}
        )
        self.assertEqual(response.status_code, status.OK, "Delete workspace.")

        # Let's try to delete the same workspace again
        response = self.client.delete(
            f"/filemanager/api/{self.upload_id}",
            headers={'Authorization': self.admin_token}
        )
        logger.debug("Delete Response:\n" + str(response.data) + '\n')

        self.assertEqual(response.status_code, status.NOT_FOUND, 
                         "Delete non-existent workspace.")

    def test_delete_nonsense_workspace_id(self):
        """Try and delete a non-sense upload_id."""
        response = self.client.delete(
            f"/filemanager/api/34+14",
            headers={'Authorization': self.admin_token}
        )

        self.assertEqual(response.status_code, status.NOT_FOUND, 
                         "Delete workspace using bogus upload_id.")

    def test_delete_malicious_workspace_id(self):
        """Try and delete a non-sense upload_id."""
        response = self.client.delete(
            f"/filemanager/api/../../etc/passwd",
            headers={'Authorization': self.admin_token}
        )

        self.assertEqual(response.status_code, status.NOT_FOUND, 
                         "Delete workspace using bogus upload_id.")
