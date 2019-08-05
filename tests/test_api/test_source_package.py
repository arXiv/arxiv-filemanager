"""Tests related to the source package."""

import os
import io
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


class TestSourcePackage(TestCase):
    """The source package is a gzipped tarball of the source and anc files."""

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
        self.original_checksum = response.headers.get('ETag')

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

    def test_source_package_exists(self):
        """The source package is available when the workspace is created."""
        response = self.client.head(
            f'/filemanager/api/{self.upload_id}/content',
            headers={'Authorization': self.token}
        )
        self.assertEqual(response.status_code, status.OK)

    def test_source_package_checksum_is_stable(self):
        """Checksum should not change while the workspace does not change."""
        response = self.client.head(
            f'/filemanager/api/{self.upload_id}/content',
            headers={'Authorization': self.token}
        )
        first_checksum = response.headers.get('ETag')
        self.assertIsNotNone(first_checksum)
        self.assertEqual(first_checksum, self.original_checksum)

        response = self.client.head(
            f'/filemanager/api/{self.upload_id}/content',
            headers={'Authorization': self.token}
        )
        second_checksum = response.headers.get('ETag')
        self.assertEqual(first_checksum, second_checksum)

        response = self.client.get(
            f'/filemanager/api/{self.upload_id}/content',
            headers={'Authorization': self.token}
        )
        third_checksum = response.headers.get('ETag')
        self.assertEqual(first_checksum, third_checksum)

    def test_source_package_checksum_changes(self):
        """When the workspace changes, so does the checksum."""
        response = self.client.head(
            f'/filemanager/api/{self.upload_id}/content',
            headers={'Authorization': self.token}
        )
        first_checksum = response.headers.get('ETag')
        self.assertIsNotNone(first_checksum)

        response = self.client.post(
            f'/filemanager/api/{self.upload_id}',
            data={'file': (io.BytesIO(b'foocontent'), 'foo.txt'),},
            headers={'Authorization': self.token},
            content_type='multipart/form-data'
        )

        second_checksum = response.headers.get('ETag')
        self.assertIsNotNone(second_checksum)
        self.assertNotEqual(first_checksum, second_checksum)

        response = self.client.head(
            f'/filemanager/api/{self.upload_id}/content',
            headers={'Authorization': self.token}
        )

        third_checksum = response.headers.get('ETag')
        self.assertIsNotNone(third_checksum)
        self.assertEqual(second_checksum, third_checksum)

