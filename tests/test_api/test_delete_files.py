"""Tests related to deleting individual files."""

import os
import json
import shutil
import tempfile
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


class TestDeleteFiles(TestCase):
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
    
    def test_delete_a_file(self):
        """Try a few valid deletions."""

        # Delete a file (normal call)
        public_file_path = "accessibilityMeta.sty"

        encoded_file_path = quote(public_file_path, safe='')
        public_file_path = encoded_file_path
        print(f"ENCODED:{public_file_path}\n")

        response = self.client.delete(
            f"/filemanager/api/{self.upload_id}/{public_file_path}",
            headers={'Authorization': self.token})
        print(f"Delete File Response:'{public_file_path}'\n{response.data}\n")
        self.assertEqual(response.status_code, status.OK,
                         "Delete an individual file: '{public_file_path}'.")
        self.assertEqual(json.loads(response.data)['reason'], 'deleted file')
    
    def test_delete_file_outside_workspace(self):
        """
        Attempt to delete a file outside the workspace.

        This file path is a potential security threat. Attempt to detect such
        deviant file deletions without alerting the client.
        """
        public_file_path = "../../subdir/this_file"
        public_file_path = quote(public_file_path, safe='')
        response = self.client.delete(
            f"/filemanager/api/{self.upload_id}/{public_file_path}",
            headers={'Authorization': self.token}
        )
        print(f"Delete hacker file path Response:'{public_file_path}'\n",
              str(response.data), '\n')
        self.assertEqual(response.status_code, status.NOT_FOUND,
                         f"Delete a file outside of workspace:"
                         f" '{public_file_path}'.")
        expected_data = {'reason': 'file not found'}
        self.assertDictEqual(json.loads(response.data), expected_data)
    
    def test_sneakily_delete_file_outside_workspace(self):
        """
        Another file path is a potential security threat. 
        
        Attempt to detect such deviant file deletions without alerting the
        client.
        """
        public_file_path = "anc/../../etc/passwd"
        public_file_path = quote(public_file_path, safe='')
        response = self.client.delete(
            f"/filemanager/api/{self.upload_id}/{public_file_path}",
            headers={'Authorization': self.token
        })
        print(f"Delete hacker file path Response:'{public_file_path}'\n",
              str(response.data), '\n')
        self.assertEqual(response.status_code, status.NOT_FOUND,
                         f"Delete a file outside of workspace:"
                         f" '{public_file_path}'.")

    def test_delete_important_system_file(self):
        """
        Attempt to delete an important system file.
        
        This generates an illegal URL so this doesn't make it to our code.
        """
        public_file_path = "/etc/passwd"
        public_file_path = quote(public_file_path, safe='')
        response = self.client.delete(
            f"/filemanager/api/{self.upload_id}/{public_file_path}",
            headers={'Authorization': self.token})
        print(f"Delete system password file Response:'{public_file_path}'\n")
        self.assertEqual(response.status_code, status.NOT_FOUND,
                         f"Delete a system file: '{public_file_path}'..")

    def test_delete_nonexistant_file(self):
        """Try to delete non-existent file."""
        public_file_path = "somedirectory/lipics-logo-bw.pdf"
        public_file_path = quote(public_file_path, safe='')
        response = self.client.delete(
            f"/filemanager/api/{self.upload_id}/{public_file_path}",
            headers={'Authorization': self.token}
        )
        print(f"Delete non-existent file Response:'{public_file_path}'\n",
              str(response.data), '\n')
        self.assertEqual(response.status_code, status.NOT_FOUND,
                         f"Delete non-existent file: '{public_file_path}'.")

    def test_delete_file_in_subdirectory(self):
        """Try to delete file in subdirectory - valid file deletion."""
        public_file_path = "anc/manuscript_Na2.7Ru4O9.tex"
        public_file_path = quote(public_file_path, safe='')
        response = self.client.delete(
            f"/filemanager/api/{self.upload_id}/{public_file_path}",
            headers={'Authorization': self.token}
        )
        print(f"Delete file in subdirectory anc Response:"
              f" '{public_file_path}'\n" + str(response.data) + '\n')
        self.assertEqual(response.status_code, status.OK,
                         f"Delete file in subdirectory: '{public_file_path}'.")
        
        # Try an delete file a second time...we'll know if first delete really
        # worked.
        public_file_path = "anc/manuscript_Na2.7Ru4O9.tex"
        public_file_path = quote(public_file_path, safe='')
        response = self.client.delete(
            f"/filemanager/api/{self.upload_id}/{public_file_path}",
            headers={'Authorization': self.token}
        )
        print(f"Delete file in subdirectory anc Response:'{public_file_path}"
              "'\n" + str(response.data) + '\n')
        self.assertEqual(response.status_code, status.NOT_FOUND,
                         f"Delete file in subdirectory: '{public_file_path}'.")

    def test_delete_another_file_in_subdirectory(self):
        """Try to delete file in subdirectory - valid file deletion."""
        public_file_path = "anc/fig8.PNG"
        public_file_path = quote(public_file_path, safe='')
        response = self.client.delete(
            f"/filemanager/api/{self.upload_id}/{public_file_path}",
            headers={'Authorization': self.token}
        )
        print(f"Delete file in subdirectory anc Response: '{public_file_path}'"
              "\n" + str(response.data) + '\n')
        self.assertEqual(response.status_code, status.OK,
                         f"Delete file in subdirectory: '{public_file_path}'.")

    def test_delete_funky_filename(self):
        """
        Try a path that is not hacky but that we know secure_filename() will
        filter out characters.
        
        Reject these filenames for now (because they're a little funny).
        """
        #
        # TODO: I suppose we could map ~/ and ./ to root of src directory.
        #
        public_file_path = "~/anc/manuscript_Na2.7Ru4O9.tex"
        public_file_path = quote(public_file_path, safe='')
        response = self.client.delete(
            f"/filemanager/api/{self.upload_id}/{public_file_path}",
            headers={'Authorization': self.token}
        )
        print(f"Delete invalid file in subdirectory anc Response: "
              "'{public_file_path}'\n" + str(response.data) + '\n')
        self.assertEqual(response.status_code, status.NOT_FOUND,
                         f"Delete file in subdirectory: '{public_file_path}'.")

    def test_delete_dot_path(self):
        """
        Delete a file that starts with ``./``
        
        Technically a legal file path, but where is client coming up with this
        path? Manually?
        """
        public_file_path = "./anc/manuscript_Na2.7Ru4O9.tex"
        public_file_path = quote(public_file_path, safe='')
        response = self.client.delete(
            f"/filemanager/api/{self.upload_id}/{public_file_path}",
            headers={'Authorization': self.token}
        )
        print(f"Delete invalid file in subdirectory anc Response: "
              f"'{public_file_path}'\n" + str(response.data) + '\n')
        self.assertEqual(response.status_code, status.NOT_FOUND,
                         f"Delete file in subdirectory: '{public_file_path}'.")