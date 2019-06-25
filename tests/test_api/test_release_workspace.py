"""Tests related to releasing and unreleasing a workspace."""

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
from filemanager.domain import UploadWorkspace

from .util import generate_token


class TestReleasedWorkspace(TestCase):
    """
    Test behavior of released workspace.

    Releasing workspace allows system to clean up workspace files.
    """

    DATA_PATH = os.path.join(os.path.split(os.path.abspath(__file__))[0], '..')

    def setUp(self) -> None:
        """Initialize the app, and upload + release a workspace."""
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
            'test_files_upload/1801.03879-1.tar.gz'
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

        # Release the workspace.
        self.admin_token = generate_token(self.app, [
            auth.scopes.READ_UPLOAD,
            auth.scopes.WRITE_UPLOAD,
            auth.scopes.DELETE_UPLOAD_WORKSPACE.as_global()
        ])

        response = self.client.post(
            f"/filemanager/api/{self.upload_id}/release",
            headers={'Authorization': self.admin_token}
        )
        self.assertEqual(response.status_code, status.OK, 
                         f"Release workspace '{self.upload_id}'.")

        print("Release:\n" + str(response.data) + '\n')

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
    
    def test_upload_files_to_released_workspace(self):
        """Try to upload files to a released workspace."""
        filepath = os.path.join(
            self.DATA_PATH,
            'test_files_upload/1801.03879-1.tar.gz'
        )
        fname = os.path.basename(filepath)
        response = self.client.post(f"/filemanager/api/{self.upload_id}",
                                    data={
                                        'file': (open(filepath, 'rb'), fname),
                                    },
                                    headers={'Authorization': self.token},
                                    #        content_type='application/gzip')
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, status.FORBIDDEN, 
                         "Cannot upload files to a released workspace")
        print("Upload files to released workspace:\n{response.data}\n")
    
    def test_get_status_released_workspace(self):
        """Get the status of a released workspace."""
        response = self.client.get(f"/filemanager/api/{self.upload_id}",
                                   headers={'Authorization': self.token})

        self.assertEqual(response.status_code, status.OK, 
                         "Request upload summary on released workspace (OK)")
        response_data = json.loads(response.data)
        self.assertEqual(response_data['status'], 
                         UploadWorkspace.Status.RELEASED.value)

    def test_attempt_to_delete_a_file_in_released_workspace(self):
        """Attempt to delete a file in a released workspace."""
        public_file_path = 'somefile'
        response = self.client.delete(
            f"/filemanager/api/{self.upload_id}/{public_file_path}",
            headers={'Authorization': self.token}
        )
        print(f"Delete File Response(released): '{public_file_path}'\n"
              f" {response.data}\n")
        self.assertEqual(response.status_code, status.FORBIDDEN,
                         "Cannot delete a file from a released workspace")
    
    def test_delete_all_files_in_released_workspace(self):
        """Attempt to delete all files in my workspace (normal)."""
        response = self.client.post(
            f"/filemanager/api/{self.upload_id}/delete_all",
            headers={'Authorization': self.token},
            content_type='multipart/form-data'
        )
        print("Delete All Files Response(released):\n{response.data}\n")
        self.assertEqual(response.status_code, status.FORBIDDEN, 
                         'Cannot delete files from a released workspace')

class TestUnReleasedWorkspace(TestCase):
    """
    Test behavior of unreleased workspace.

    Releasing workspace allows system to clean up workspace files.
    """

    DATA_PATH = os.path.join(os.path.split(os.path.abspath(__file__))[0], '..')

    def setUp(self) -> None:
        """Initialize the app, and upload + release a workspace."""
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
            'test_files_upload/1801.03879-1.tar.gz'
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

        # Release the workspace.
        self.admin_token = generate_token(self.app, [
            auth.scopes.READ_UPLOAD,
            auth.scopes.WRITE_UPLOAD,
            auth.scopes.DELETE_UPLOAD_WORKSPACE.as_global()
        ])

        response = self.client.post(
            f"/filemanager/api/{self.upload_id}/release",
            headers={'Authorization': self.admin_token}
        )
        self.assertEqual(response.status_code, status.OK, 
                         f"Release workspace '{self.upload_id}'.")

        print("Release:\n" + str(response.data) + '\n')

        # Now test unrelease
        response = self.client.post(
            f"/filemanager/api/{self.upload_id}/unrelease",
            headers={'Authorization': self.admin_token}
        )
        self.assertEqual(response.status_code, status.OK, 
                         f"Unrelease workspace '{self.upload_id}'.")

        print("Unrelease:\n" + str(response.data) + '\n')

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
    
    def test_upload_files_to_unreleased_workspace(self):
        """Try to upload files to an unreleased workspace."""
        filepath = os.path.join(
            self.DATA_PATH,
            'test_files_upload/1801.03879-1.tar.gz'
        )
        fname = os.path.basename(filepath)
        response = self.client.post(f"/filemanager/api/{self.upload_id}",
                                    data={
                                        'file': (open(filepath, 'rb'), fname),
                                    },
                                    headers={'Authorization': self.token},
                                    #        content_type='application/gzip')
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, status.CREATED, 
                         "Can upload files to a locked workspace")
        print("Upload files to unreleased workspace:\n{response.data}\n")
    
    def test_get_status_unreleased_workspace(self):
        """Get the status of a unreleased workspace."""
        response = self.client.get(f"/filemanager/api/{self.upload_id}",
                                   headers={'Authorization': self.token})

        self.assertEqual(response.status_code, status.OK, 
                         "Request upload summary on unreleased workspace (OK)")
        response_data = json.loads(response.data)
        self.assertEqual(response_data['status'], 
                         UploadWorkspace.Status.ACTIVE.value)

    def test_attempt_to_delete_a_file_in_unreleased_workspace(self):
        """Attempt to delete a file in an unreleased workspace."""
        public_file_path = 'somefile'
        response = self.client.delete(
            f"/filemanager/api/{self.upload_id}/{public_file_path}",
            headers={'Authorization': self.token}
        )
        print(f"Delete File Response(locked): '{public_file_path}'\n"
              f" {response.data}\n")
        self.assertEqual(response.status_code, status.NOT_FOUND,
                         "Get a normal 404 when the workspace is unreleased")
    
    def test_delete_all_files_in_unreleased_workspace(self):
        """Attempt to delete all files in my workspace (normal)."""
        response = self.client.post(
            f"/filemanager/api/{self.upload_id}/delete_all",
            headers={'Authorization': self.token},
            content_type='multipart/form-data'
        )
        print("Delete All Files Response (unreleased):\n{response.data}\n")
        self.assertEqual(response.status_code, status.OK, 
                         'Can delete files from an unreleased workspace')



#
#         # Try request that failed while upload workspace was released
#         response = self.client.post(f"/filemanager/api/{self.upload_id}/delete_all",
#                                     headers={'Authorization': token},
#                                     content_type='multipart/form-data')
#
#         self.assertEqual(response.status_code, status.OK, "Delete all user-uploaded "
#                                                     "files from released workspace.")
#
#         # Clean up after ourselves
#
#         response = self.client.delete(f"/filemanager/api/{self.upload_id}",
#                                       headers={'Authorization': admin_token}
#                                       )
#
#         self.assertEqual(response.status_code, status.OK, "Accepted request to delete workspace.")
#
#         # Done test