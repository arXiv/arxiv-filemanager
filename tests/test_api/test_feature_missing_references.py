"""Tests related to handling of missing references."""

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
from filemanager.domain import Workspace, Readiness

from .util import generate_token

logger = logging.getLogger(__name__)
logger.setLevel(int(os.environ.get('LOGLEVEL', '20')))


class TestMissingReferences(TestCase):
    """Test that exercise missing references (.bib/.bbl) logic."""

    DATA_PATH = os.path.join(os.path.split(os.path.abspath(__file__))[0], '..')

    def setUp(self) -> None:
        """Initialize the app, and upload + lock a workspace."""
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

    def test_missing_bbl_upload(self):
        """Upload source with missing required bbl file."""
        fpath = os.path.join(self.DATA_PATH,
                             'test_files_upload/bad_bib_but_no_bbl.tar')
        fname = os.path.basename(fpath)
        response = self.client.post('/filemanager/api/',
                                    data={
                                        'file': (open(fpath, 'rb'), fname),
                                    },
                                    headers={'Authorization': self.token},
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, status.CREATED,
                         "Upload should be successful")
        self.maxDiff = None

        response_data = json.loads(response.data)
        try:
            jsonschema.validate(response_data, self.schema)
        except jsonschema.exceptions.SchemaError as e:
            self.fail(e)

        # IMPORTANT: readiness of 'ERRORS' should stop submission from
        # proceeding until missing .bbl is provided OR .bib is removed.

        self.assertIn('readiness', response_data,
                      "Returns total upload status.")
        self.assertEqual(response_data['readiness'],
                         Readiness.ERRORS.value,
                         'Workspace has readiness: `ERRORS`')

        # Get upload_id from previous file upload
        test_id = response_data['upload_id']

        # Upload missing .bbl
        fpath = os.path.join(self.DATA_PATH, 'test_files_upload/final.bbl')
        fname = os.path.basename(fpath)
        response = self.client.post(f"/filemanager/api/{test_id}",
                                    data={
                                        'file': (open(fpath, 'rb'), fname),
                                    },
                                    headers={'Authorization': self.token},
                                    content_type='multipart/form-data')

        # Check response and extract upload_id from response
        self.assertEqual(response.status_code, status.CREATED)
        self.maxDiff = None

        response_data = json.loads(response.data)
        try:
            jsonschema.validate(response_data, self.schema)
        except jsonschema.exceptions.SchemaError as e:
            self.fail(e)

        # IMPORTANT: After we upload compiled .bbl file 'update_status' changes
        # from ERRORS to READY.
        self.assertIn('readiness', response_data, 'Readiness is provided')
        self.assertEqual(response_data['readiness'],
                         Readiness.READY.value,
                         'Workspace is ready with warnings')

