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


class TestNewUpload(TestCase):
    """Test creation of a new upload workspace."""

    DATA_PATH = os.path.join(os.path.split(os.path.abspath(__file__))[0], '..')

    def setUp(self) -> None:
        """Initialize the Flask application, and get a client for testing."""
        self.workdir = tempfile.mkdtemp()
        self.server_name = 'fooserver.localdomain'
        self.app = create_web_app()
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///'
        self.app.config['SERVER_NAME'] = self.server_name
        self.app.config['STORAGE_BASE_PATH'] = self.workdir

        # There is a bug in arxiv.base where it doesn't pick up app config
        # parameters. Until then, we pass it to os.environ.
        os.environ['JWT_SECRET'] = self.app.config.get('JWT_SECRET')
        self.client = self.app.test_client()
        # self.app.app_context().push()
        with self.app.app_context():
            database.db.create_all()

    def tearDown(self):
        """
        Clean up!

        This cleans out the workspace. Comment out if you want to inspect files
        in workspace. Source log is saved to 'deleted_workspace_logs' directory.
        """
        shutil.rmtree(self.workdir)

    def test_no_auth_token(self):
        """No auth token is included in the request."""
        response = self.client.post('/filemanager/api/',
                                    data={'file': '',},
                                    # Missing authorization field
                                    # headers={'Authorization': ''},
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, status.UNAUTHORIZED,
                         'Authorization token not passed to server')

    def test_empty_auth_token(self):
        """Authorization header is passed without valid token"""
        response = self.client.post('/filemanager/api/',
                                    data={'file': '',},
                                    # Empty token value
                                    headers={'Authorization': ''},
                                    #        content_type='application/gzip')
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, status.UNAUTHORIZED,
                         'Empty authorization token passed to server')

    def test_invalid_auth_token(self):
        """An invalid auth token is passed."""
        # Create an INVALID token for writing to upload workspace
        token = generate_token(self.app, [auth.scopes.READ_UPLOAD])
        filepath = os.path.join(self.DATA_PATH,
                                'test_files_upload/1801.03879-1.tar.gz')

        # Prepare gzipped tar submission for upload.
        filename = os.path.basename(filepath)
        response = self.client.post('/filemanager/api/',
                                    data={
                                        # 'file': (io.BytesIO(b"abcdef"), 'test.jpg'),
                                        #      'file': (open(filepath, 'rb'), 'test.tar.gz'),
                                        'file': (open(filepath, 'rb'), filename),
                                    },
                                    # Bad token - invalid permissions
                                    headers={'Authorization': token},
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, status.FORBIDDEN,
                         'Invalid authorization token passed to server')
    # TODO: Need to add tests for user who does not have permissions to act on
    # workspace This requires updating to NEW auth/z implementation. Soon!

    def test_file_payload_missing(self):
        """A file is passed, but not at the expected key."""
        # Create a VALID token for writing to upload workspace
        token = generate_token(self.app, [auth.scopes.READ_UPLOAD,
                                          auth.scopes.WRITE_UPLOAD])
        filepath = os.path.join(self.DATA_PATH,
                                'test_files_upload/1801.03879-1.tar.gz')

        # File payload missing
        response = self.client.post('/filemanager/api/',
                                    data={
                                        # File payload is missing
                                        'fileXX': (open(filepath, 'rb'), ''),
                                    },
                                    # Good Token
                                    headers={'Authorization': token},
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, status.BAD_REQUEST,
                         'Upload file payload not passed to server')

        expected_data = {'reason': 'missing file/archive payload'}
        self.assertDictEqual(json.loads(response.data), expected_data)

    def test_null_file(self):
        """
        File has an empty filename.

        Looks like this condition is not possible, though online forum noted
        possibility of null name.
        """
        token = generate_token(self.app, [auth.scopes.READ_UPLOAD,
                                          auth.scopes.WRITE_UPLOAD])

        # Filename missing or null.
        filepath = os.path.join(self.DATA_PATH,
                                'test_files_upload/1801.03879-1.tar.gz')
        response = self.client.post('/filemanager/api/',
                                    data={
                                        # filename is null
                                        'file': (open(filepath, 'rb'), ''),
                                    },
                                    # Good Token
                                    headers={'Authorization': token},
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, status.BAD_REQUEST,
                         'Valid authorization token not passed to server')

        expected_data = {
            'reason': 'file argument missing filename or file not selected'
        }
        self.assertDictEqual(json.loads(response.data), expected_data)

    def test_empty_file(self):
        """The uploaded file is empty."""
        token = generate_token(self.app, [auth.scopes.READ_UPLOAD,
                                          auth.scopes.WRITE_UPLOAD])
        # Create an empty file.
        _, filepath = tempfile.mkstemp()
        open(filepath, 'wb').close()  # touch

        # Upload empty/null file
        response = self.client.post('/filemanager/api/',
                                    data={
                                        # filename is null
                                        'file': (open(filepath, 'rb'), 'mt'),
                                    },
                                    # Good Token
                                    headers={'Authorization': token},
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, status.BAD_REQUEST,
                         'Empty file uploaded to server')

        expected_data = {'reason': 'file payload is zero length'}
        self.assertDictEqual(json.loads(response.data), expected_data)


    # Upload a submission package and perform normal operations on upload
    def test_upload_files_normal(self) -> None:
        """
        Test normal well-behaved upload requests.

        This series of tests uploads files with the expectation of success.

        The appropriate tokens are provided to various requests.
        """
        with open('schema/resources/Workspace.json') as f:
            schema = json.load(f)

        # Create a token for writing to upload workspace
        token = generate_token(self.app, [auth.scopes.READ_UPLOAD,
                                          auth.scopes.WRITE_UPLOAD,
                                          auth.scopes.DELETE_UPLOAD_FILE])

        created = datetime.now(UTC)
        modified = datetime.now(UTC)
        expected_data = {'upload_id': 5,
                         'status': "SUCCEEDED",
                         'create_datetime': created.isoformat(),
                         'modify_datetime': modified.isoformat()
                         }

        filepath = os.path.join(self.DATA_PATH,
                                'test_files_upload/1801.03879-1.tar.gz')

        # Prepare gzipped tar submission for upload
        filename = os.path.basename(filepath)

        # Post a test submission to upload API
        logger.debug(f"Token (for possible use in manual browser tests): {token}\n")

        logger.debug("\nMake request to upload gzipped tar file. \n"
              + "\t[Warnings and errors are currently printed to console.\n"
              + "\tLogs coming soon.]\n")

        response = self.client.post('/filemanager/api/',
                                    data={
                                        # 'file': (io.BytesIO(b"abcdef"), 'test.jpg'),
                                        'file': (open(filepath, 'rb'), filename),
                                    },
                                    headers={'Authorization': token},
                                    #        content_type='application/gzip')
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, 201,
                         "Accepted and processed uploaded Submission Contents")
        post_data = json.loads(response.data)
        try:
            jsonschema.validate(post_data, schema)
        except jsonschema.exceptions.SchemaError as e:
            self.fail(e)

        # Verify that the state of the upload workspace is preserved.
        location = response.headers['Location']
        _, location = location.split(f'http://{self.server_name}', 1)
        response = self.client.get(location, headers={'Authorization': token})
        self.assertEqual(response.status_code, status.OK)

        get_data = json.loads(response.data)

        self.assertEqual(post_data['upload_total_size'],
                         get_data['upload_total_size'],
                         'Upload size is consistent between requests')
        self.assertEqual(post_data['lock_state'], get_data['lock_state'],
                         'Lock state is consistent between requests')
        self.assertEqual(post_data['status'], get_data['status'],
                         'Status is consistent between requests')
        self.assertEqual(post_data['checksum'], get_data['checksum'],
                         'Checksum is consistent between requests')
        self.assertEqual(len(post_data['files']), len(get_data['files']),
                         'Number of files is consistent between requests')

        # TODO: need to look a little closer at how we think about readiness.
        # Right now, a workspace can be READY_WITH_WARNINGS on upload, but then
        # READY on subsequent status requests. Guess I'm not clear on what
        # _WITH_WARNINGS should signify -- should it be persistant warnings?
        # --Erick 2019-06-20
        #
        # self.assertEqual(post_data['readiness'], get_data['readiness'],
        #                  'Readiness is consistent between requests')