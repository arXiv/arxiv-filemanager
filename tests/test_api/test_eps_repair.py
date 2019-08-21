"""Tests related to repair of EPS files."""

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


# TODO: I'm a bit unclear about why this is an API test. Some of these are not
# working correctly -- unsure whether this is because it's actually not
# working, or there is something wonky with the tests.
class TestEPSRepair(TestCase):
    """Test repair of EPS files."""

    DATA_PATH = os.path.join(os.path.split(os.path.abspath(__file__))[0], '..')
    TEST_FILES_STRIP_PS = os.path.join(DATA_PATH,
                                       'test_files_strip_postscript')

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

    def test_eps_repair(self):
        test_filename = 'dos_eps_1.eps'
        fpath = os.path.join(self.DATA_PATH, 'type_test_files', test_filename)
        fname = os.path.basename(fpath)
        response = self.client.post('/filemanager/api/',
                                    data={
                                        'file': (open(fpath, 'rb'), fname),
                                    },
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

        self.assertIn('readiness', response_data, 'Readiness is indicated')

        # self.assertEqual(response_data['readiness'],
                        #  Readiness.READY_WITH_WARNINGS.value,
                        #  "Expect warnings from stripping TIFF from EPS file.")

        # Make sure we are seeing errors
        warnings = defaultdict(list)
        for _, name, msg in response_data['errors']:
            warnings[name].append(msg)
        self.assertIn('Leading TIFF preview stripped',
                      ' '.join(warnings[fname]))

        # Now let's grab file content and verify that it matches expected
        # reference_path file.

        # Check if content file exists
        response = self.client.head(
            f"/filemanager/api/{upload_id}/{test_filename}/content",
            headers={'Authorization': self.token}
        )
        self.assertEqual(response.status_code, status.OK)
        self.assertIn('ETag', response.headers, "Returns an ETag header")

        # Download content file
        response = self.client.get(
            f"/filemanager/api/{upload_id}/{test_filename}/content",
            headers={'Authorization': self.token}
        )
        self.assertEqual(response.status_code, status.OK)
        self.assertIn('ETag', response.headers, "Returns an ETag header")

        workdir = tempfile.mkdtemp()

        # Write out file (to save temporary directory where we saved
        # source_log)
        content_file_path = os.path.join(workdir, test_filename)
        with open(content_file_path, 'wb') as fileH:
            fileH.write(response.data)

        logger.debug(content_file_path)
        # Compare downloaded file (content_file_path) against reference_path
        # file.
        reference_filename = 'dos_eps_1_stripped.eps'
        reference_path = os.path.join(self.TEST_FILES_STRIP_PS,
                                      reference_filename)
        # Compared fixed file to a reference_path stripped version of file.
        is_same = filecmp.cmp(content_file_path, reference_path, shallow=False)
        self.assertTrue(is_same, f"Repair EPS file '{test_filename}'.")

#         # Try encapsulate Postscript with trailing TIFF
#
#         # Trying to replicate bib/bbl upload behavior
#         # Lets upload a file before uploading the zero length file
#         test_filename = 'dos_eps_2.eps'
#         filepath1 = os.path.join(testfiles_dir, test_filename)
#         filename1 = os.path.basename(filepath1)
#         response = self.client.post(f"/filemanager/api/{upload_id}",
#                                     data={
#                                         # 'file': (io.BytesIO(b"abcdef"), 'test.jpg'),
#                                         'file': (open(filepath1, 'rb'), filename1),
#                                     },
#                                     headers={'Authorization': token},
#                                     #        content_type='application/gzip')
#                                     content_type='multipart/form-data')
#
#         # logger.debug("Upload Response:\n" + str(response.data) + "\nEnd Data")
#         # logger.debug(json.dumps(json.loads(response.data), indent=4, sort_keys=True))
#
#         self.assertEqual(response.status_code, 201, "Accepted and processed uploaded Submission Contents")
#         self.maxDiff = None
#
#         with open('schema/resources/Workspace.json') as f:
#             result_schema = json.load(f)
#
#         try:
#             jsonschema.validate(json.loads(response.data), result_schema)
#         except jsonschema.exceptions.SchemaError as e:
#             self.fail(e)
#
#         # IMPORTANT RESULT STATUS of ERRORS should stop submission from
#         # proceeding until missing .bbl is provided OR .bib is removed.
#         upload_data: Dict[str, Any] = json.loads(response.data)
#         self.assertIn('readiness', upload_data, "Returns total upload status.")
#         self.assertEqual(upload_data['readiness'], "READY_WITH_WARNINGS",
#                          "Expect warnings from stripping TIFF from EPS file.")
#
#         # Make sure we are seeing errors
#         self.assertTrue(self.search_errors("trailing TIFF preview stripped",
#                                            "warn", test_filename,
#                                            upload_data['errors']), "Expect this error to occur.")
#
#         # Check if content file exists
#         response = self.client.head(
#             f"/filemanager/api/{upload_id}/{test_filename}/content",
#             headers={'Authorization': token}
#         )
#         self.assertEqual(response.status_code, status.OK)
#         self.assertIn('ETag', response.headers, "Returns an ETag header")
#
#         # Download content file
#         response = self.client.get(
#             f"/filemanager/api/{upload_id}/{test_filename}/content",
#             headers={'Authorization': token}
#         )
#         self.assertEqual(response.status_code, status.OK)
#         self.assertIn('ETag', response.headers, "Returns an ETag header")
#
#         workdir = tempfile.mkdtemp()
#
#         # Write out file (to save temporary directory where we saved source_log)
#         content_file_path = os.path.join(workdir, test_filename)
#         fileH = open(content_file_path, 'wb')
#         fileH.write(response.data)
#         fileH.close()
#
#         # Compare downloaded file (content_file_path) against reference_path file
#         reference_filename = 'dos_eps_2_stripped.eps'
#         reference_path = os.path.join(TEST_FILES_STRIP_PS, reference_filename)
#         # Compared fixed file to a reference_path stripped version of file.
#         is_same = filecmp.cmp(content_file_path, reference_path, shallow=False)
#         self.assertTrue(is_same,
#                         f"Repair Encapsulated Postscript file '{test_filename}'.")
#
#         # Delete the workspace
#         # Create admin token for deleting upload workspace
#         admin_token = generate_token(self.app, [auth.scopes.READ_UPLOAD,
#                                                 auth.scopes.WRITE_UPLOAD,
#                                                 auth.scopes.DELETE_UPLOAD_WORKSPACE.as_global()])
#
#         response = self.client.delete(f"/filemanager/api/{upload_id}",
#                                       headers={'Authorization': admin_token}
#                                       )
#
#         # This cleans out the workspace. Comment out if you want to inspect files
#         # in workspace. Source log is saved to 'deleted_workspace_logs' directory.
#         self.assertEqual(response.status_code, status.OK, "Accepted request to delete workspace.")