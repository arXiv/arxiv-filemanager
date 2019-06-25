"""Tests related to uploading to an existing workspace."""

import os
import json
import shutil
import tempfile
from datetime import datetime
from unittest import TestCase, mock
from http import HTTPStatus as status

from pytz import UTC
import jsonschema

from arxiv.users import domain, auth

from filemanager.factory import create_web_app
from filemanager.services import database

from .util import generate_token


class TestUploadToExistingWorkspace(TestCase):
    """
    Test various failure conditions on existing workspaces.

    The same function handles new upload request so we will not repeat
    basic argument failures that have been covered already.

    TODO: Add tests for locked/released workspaces on upload requests.
    TODO: Lock/unlock, release/unrelease. (when implements)
    TODO: Add size checks (when implemented)
    """

    DATA_PATH = os.path.join(os.path.split(os.path.abspath(__file__))[0], '..')

    def setUp(self) -> None:
        """Initialize the Flask application, and get a client for testing."""
        self.server_name = 'fooserver.localdomain'
        self.app = create_web_app()
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///'
        self.app.config['SERVER_NAME'] = self.server_name

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
                                               auth.scopes.WRITE_UPLOAD])

    def test_upload_to_nonexistant_workspace(self) -> None:
        """Upload file to non existent workspace!! Yikes!"""


        created = datetime.now(UTC)
        modified = datetime.now(UTC)
        expected_data = {'upload_id': 5,
                         'status': "SUCCEEDED",
                         'create_datetime': created.isoformat(),
                         'modify_datetime': modified.isoformat()}

        # Prepare gzipped tar submission for upload.
        filepath = os.path.join(self.DATA_PATH,
                                'test_files_upload/1801.03879-1.tar.gz')
        fname = os.path.basename(filepath)

        # Post a test submission to upload API
        bad_upload_id = '9999'
        response = self.client.post(f'/filemanager/api/{bad_upload_id}',
                                    data={
                                        'file': (open(filepath, 'rb'), fname),
                                    },
                                    headers={'Authorization': self.token},
                                    #        content_type='application/gzip')
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, status.NOT_FOUND,
                         "Accepted uploaded Submission Contents")
        expected_data = {'reason': 'upload workspace not found'}
        self.maxDiff = None
        self.assertDictEqual(json.loads(response.data), expected_data)

    def test_get_nonexistant_workspace(self) -> None:
        """Attempt to get a workspace that does not exist."""
        bad_upload_id = '9999'
        response = self.client.get(f"/filemanager/api/{bad_upload_id}",
                                   headers={'Authorization': self.token})

        self.assertEqual(response.status_code, status.NOT_FOUND,
                         "Accepted uploaded Submission Contents")
        expected_data = {'reason': 'upload workspace not found'}
        self.maxDiff = None
        self.assertDictEqual(json.loads(response.data), expected_data)