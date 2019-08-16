"""Tests specifically focused on security vulnerabilities."""

import os
import json
import shutil
import tempfile
import filecmp
import logging
from datetime import datetime
from unittest import TestCase, mock
from http import HTTPStatus as status
from pprint import pprint
from collections import defaultdict

import jsonschema
from requests.utils import quote
from pytz import UTC

from arxiv.users import domain, auth

from filemanager.factory import create_web_app
from filemanager.services import database
from filemanager.domain import Workspace

from .util import generate_token

logger = logging.getLogger(__name__)
logger.setLevel(int(os.environ.get('LOGLEVEL', '20')))


class TestRelativePaths(TestCase):
    """Test uploaded archives that include relative paths."""

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

    def tearDown(self):
        """Delete the workspace."""
        shutil.rmtree(self.workdir)

    def test_relative_path(self):
        """Uploaded tarball contains a relative path two levels up."""
        fpath = os.path.join(self.DATA_PATH, 'test_files_upload',
                             'relative_path.tar.gz')
        fname = os.path.basename(fpath)
        response = self.client.post('/filemanager/api/',
                                    data={'file': (open(fpath, 'rb'), fname)},
                                    headers={'Authorization': self.token},
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, status.CREATED,
                         "Accepted and processed uploaded Submission Contents")
        self.maxDiff = None
        response_data = json.loads(response.data)
        upload_id = response_data['upload_id']
        try:
            jsonschema.validate(response_data, self.schema)
        except jsonschema.exceptions.SchemaError as e:
            self.fail(e)

        self.assertNotIn('ir.png', os.listdir(self.workdir),
                         'File should be prevented from escaping upload'
                         ' workspace.')


class TestRelativePathsQuarantine(TestCase):
    """Test archives that include relative paths, using quarantine storage."""

    DATA_PATH = os.path.join(os.path.split(os.path.abspath(__file__))[0], '..')

    def setUp(self) -> None:
        """Initialize the Flask application, and get a client for testing."""
        self.workdir = tempfile.mkdtemp()
        self.quardir = tempfile.mkdtemp()
        self.server_name = 'fooserver.localdomain'
        self.app = create_web_app()
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['SERVER_NAME'] = self.server_name
        self.app.config['STORAGE_BASE_PATH'] = self.workdir
        self.app.config['STORAGE_QUARANTINE_PATH'] = self.workdir
        self.app.config['STORAGE_BACKEND'] = 'quarantine'

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

    def tearDown(self):
        """Delete the workspace."""
        shutil.rmtree(self.workdir)

    def test_relative_path(self):
        """Uploaded tarball contains a relative path two levels up."""
        fpath = os.path.join(self.DATA_PATH, 'test_files_upload',
                             'relative_path.tar.gz')
        fname = os.path.basename(fpath)
        response = self.client.post('/filemanager/api/',
                                    data={'file': (open(fpath, 'rb'), fname)},
                                    headers={'Authorization': self.token},
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, status.CREATED,
                         "Accepted and processed uploaded Submission Contents")
        self.maxDiff = None
        response_data = json.loads(response.data)
        upload_id = response_data['upload_id']
        try:
            jsonschema.validate(response_data, self.schema)
        except jsonschema.exceptions.SchemaError as e:
            self.fail(e)

        self.assertNotIn('ir.png', os.listdir(self.workdir),
                         'File should be prevented from escaping upload'
                         ' workspace.')
