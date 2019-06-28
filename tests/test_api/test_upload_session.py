"""Tests that walk through multi-step upload workflows."""

import os
import json
import shutil
import tempfile
import io
import tarfile
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
from filemanager.domain import UploadWorkspace

from .util import generate_token

logger = logging.getLogger(__name__)
logger.setLevel(int(os.environ.get('LOGLEVEL', '20')))


class TestUploadNormalFiles(TestCase):
    """Upload a submission package and perform normal operations on upload."""

    DATA_PATH = os.path.join(os.path.split(os.path.abspath(__file__))[0], '..')

    def setUp(self) -> None:
        """Initialize the app, and upload a package with errors/warnings."""
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

    def tearDown(self):
        """Delete the workspace."""
        shutil.rmtree(self.workdir)
    
    def test_submission_workflow(self):
        """Post a test submission to upload API."""
        logger.debug(f"Token (for possible use in manual browser tests):"
              f" {self.token}\n")

        logger.debug("\nMake request to upload gzipped tar file. \n"
              "\t[Warnings and errors are currently printed to console.\n"
              "\tLogs coming soon.]\n")

        fpath = os.path.join(self.DATA_PATH, 
                             'test_files_upload/1801.03879-1.tar.gz')
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

        # Check that upload_total_size is in summary response
        self.assertIn("upload_total_size", response_data,
                      "Returns total upload size.")
        self.assertEqual(response_data["upload_total_size"], 275_781,
                         "Expected total upload size to match"
                         f" (ID: {upload_id}).")

        # Check that upload_compressed_size is in summary response
        self.assertIn("upload_compressed_size", response_data,
                      "Returns compressed upload size.")
        self.assertLess(response_data["upload_compressed_size"], 116_000,
                         "Expected total upload size to match"
                         f" (ID:{upload_id}).")

        self.assertEqual(response_data["source_format"], "tex",
                         "Check source format of TeX submission."
                         f" [ID={upload_id}]")
        
        # Get summary of upload
        response = self.client.get(f"/filemanager/api/{upload_id}",
                                   headers={'Authorization': self.token})

        self.assertEqual(response.status_code, status.OK, "File summary.")
        summary_data = json.loads(response.data)
        try:
            jsonschema.validate(summary_data, self.schema)
        except jsonschema.exceptions.SchemaError as e:
            self.fail(e)
        
        # Check for file in upload result
        file_list = summary_data['files']
        file_names = [f['name'] for f in file_list]
        self.assertIn('lipics-v2016.cls', file_names,   
                      'Uploaded file should exist in resulting file list.')
    
        # Download content before we start deleting files
        
        # Check if content exists
        response = self.client.head(
            f"/filemanager/api/{upload_id}/content",
            headers={'Authorization': self.admin_token}
        )
        self.assertEqual(response.status_code, status.OK)
        self.assertIn('ETag', response.headers, "Returns an ETag header")

        # Download content
        response = self.client.get(
            f"/filemanager/api/{upload_id}/content",
            headers={'Authorization': self.admin_token}
        )  
        self.assertEqual(response.status_code, status.OK)
        self.assertIn('ETag', response.headers, "Returns an ETag header")
        workdir = tempfile.mkdtemp(dir=self.workdir)
        with tarfile.open(fileobj=io.BytesIO(response.data)) as tar:
            tar.extractall(path=workdir)

        logger.debug(f'List directory containing downloaded content: {workdir}\:n')
        logger.debug(os.listdir(workdir))
        logger.debug(f'End List\n')

        # WARNING: THE TESTS BELOW DELETE INDIVIDUAL FILES AND THEN THE ENTIRE
        # WORKSPACE.

        # Delete a file (normal call)
        public_file_path = "lipics-logo-bw.pdf"
        encoded_file_path = quote(public_file_path, safe='')

        response = self.client.delete(
            f"/filemanager/api/{upload_id}/{public_file_path}",
            headers={'Authorization': self.token}
        )
        self.assertEqual(response.status_code, status.OK, 
                         "Can delete an individual file.")

        # Delete another file
        public_file_path = "lipics-v2016.cls"
        encoded_file_path = quote(public_file_path, safe='')

        response = self.client.delete(
            f"/filemanager/api/{upload_id}/{public_file_path}",
            headers={'Authorization': self.token}
        )
        self.assertEqual(response.status_code, status.OK, 
                         "Can delete an individual file.")
        
        # Get summary after deletions
        response = self.client.get(
            f"/filemanager/api/{upload_id}",
            headers={'Authorization': self.token}
        )

        self.assertEqual(response.status_code, status.OK, 
                         "File summary after deletions.")
        
        response_data = json.loads(response.data)
        try:
            jsonschema.validate(response_data, self.schema)
        except jsonschema.exceptions.SchemaError as e:
            self.fail(e)

        # Check that deleted file is missing from file list summary
        file_list = response_data['files']
        file_names = [f['name'] for f in file_list]
        self.assertNotIn('lipics-v2016.clsXX', file_names)

        # Now check to see if size total upload size decreased
        # Get summary and check upload_total_size
        response = self.client.get(f"/filemanager/api/{upload_id}",
                                   headers={'Authorization': self.token})

        self.assertEqual(response.status_code, status.OK, "File summary.")

        response_data = json.loads(response.data)
        try:
            jsonschema.validate(response_data, self.schema)
        except jsonschema.exceptions.SchemaError as e:
            self.fail(e)
        
        # Check that upload_total_size is in summary response
        self.assertIn('upload_total_size', response_data, 
                      "Returns total upload size.")
        self.assertNotEqual(response_data['upload_total_size'], 275_781,
                            "Expected total upload size should not match "
                            "pre - delete total")
        # upload total size is definitely smaller than original 275781 bytes
        # after we deleted a few files.
        self.assertEqual(response_data["upload_total_size"], 237_116,
                         "Expected smaller total upload size.")
        self.assertLess(response_data["upload_compressed_size"], 116_000,
                        "Expected smaller compressed upload size.")

        # Delete all files in my workspace (normal)
        response = self.client.post(f"/filemanager/api/{upload_id}/delete_all",
                                    headers={'Authorization': self.token},
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, status.OK, 
                         "Delete all user-uploaded files.")
        
        # Finally, after deleting all files, check the total upload size

        # Get summary and check upload_total_size
        response = self.client.get(f"/filemanager/api/{upload_id}",
                                   headers={'Authorization': self.token})

        self.assertEqual(response.status_code, status.OK, "File summary.")
        response_data = json.loads(response.data)
        try:
            jsonschema.validate(response_data, self.schema)
        except jsonschema.exceptions.SchemaError as e:
            self.fail(e)

        # Check that upload_total_size is in summary response
        self.assertIn("upload_total_size", response_data,
                      "Returns total upload size.")
        # Check that upload_compressed_size is in summary response
        self.assertIn("upload_compressed_size", response_data,
                      "Returns compressed upload size.")

        # upload total size is definitely smaller than original 275781 bytes
        # after we deleted everything we uploaded!!
        self.assertEqual(response_data["upload_total_size"], 0,
                         "Expected smaller total upload size after deleting"
                         " all files.")
        self.assertLess(response_data["upload_compressed_size"], 116_000,
                         "Expected smaller compressed size after deleting"
                         " all files.")

        # Let's try to upload a different source format type - HTML
        fpath = os.path.join(self.DATA_PATH, 
                             'test_files_sub_type/sampleB_html.tar.gz')
        fname = os.path.basename(fpath)
        response = self.client.post(f"/filemanager/api/{upload_id}",
                                    data={'file': (open(fpath, 'rb'), fname)},
                                    headers={'Authorization': self.token},
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, status.CREATED,
                         "Accepted and pgit rocessed uploaded Submission Contents")

        self.maxDiff = None
        response_data = json.loads(response.data)
        try:
            jsonschema.validate(response_data, self.schema)
        except jsonschema.exceptions.SchemaError as e:
            self.fail(e)
        
        self.assertEqual(response_data['source_format'], "html",
                         "Check source format of HTML submission."
                         f" [ID={upload_id}]")