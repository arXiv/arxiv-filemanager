"""Tests related to locking and unlocking a workspace."""

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
from filemanager.domain import UploadWorkspace

from .util import generate_token

logger = logging.getLogger(__name__)
logger.setLevel(int(os.environ.get('LOGLEVEL', '20')))


class TestLockedWorkspace(TestCase):
    """
    Test behavior of locked workspace.

    Locking workspace prevents updates to workspace.
    """

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

        # Lock the workspace.
        self.admin_token = generate_token(self.app, [
            auth.scopes.READ_UPLOAD,
            auth.scopes.WRITE_UPLOAD,
            auth.scopes.DELETE_UPLOAD_WORKSPACE.as_global()
        ])
        response = self.client.post(
            f"/filemanager/api/{self.upload_id}/lock",
            headers={'Authorization': self.admin_token}
        )
        self.assertEqual(response.status_code, status.OK,
                         f"Lock workspace '{self.upload_id}'.")

        logger.debug("Lock:\n" + str(response.data) + '\n')

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

    def test_upload_files_to_locked_workspace(self):
        """Try to upload files to a locked workspace."""
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
                         "Cannot upload files to a locked workspace")
        logger.debug("Upload files to locked workspace:\n{response.data}\n")

    def test_get_status_locked_workspace(self):
        """Get the status of a locked workspace."""
        response = self.client.get(f"/filemanager/api/{self.upload_id}",
                                   headers={'Authorization': self.token})

        self.assertEqual(response.status_code, status.OK,
                         "Request upload summary on locked workspace (OK)")
        response_data = json.loads(response.data)
        self.assertEqual(response_data['lock_state'],
                         UploadWorkspace.LockState.LOCKED.value)

    def test_attempt_to_delete_a_file_in_locked_workspace(self):
        """Attempt to delete a file in a locked workspace."""
        public_file_path = 'somefile'
        response = self.client.delete(
            f"/filemanager/api/{self.upload_id}/{public_file_path}",
            headers={'Authorization': self.token}
        )
        logger.debug(f"Delete File Response(locked): '{public_file_path}'\n"
              f" {response.data}\n")
        self.assertEqual(response.status_code, status.FORBIDDEN,
                         "Cannot delete a file from a locked workspace")

    def test_delete_all_files_in_locked_workspace(self):
        """Attempt to delete all files in my workspace (normal)."""
        response = self.client.post(
            f"/filemanager/api/{self.upload_id}/delete_all",
            headers={'Authorization': self.token},
            content_type='multipart/form-data'
        )
        logger.debug("Delete All Files Response(locked):\n{response.data}\n")
        self.assertEqual(response.status_code, status.FORBIDDEN,
                         'Cannot delete files from a locked workspace')

class TestUnLockedWorkspace(TestCase):
    """
    Test behavior of workspace that has been locked and then unlocked.

    Locking workspace prevents updates to workspace.
    """

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

        # Lock the workspace.
        self.admin_token = generate_token(self.app, [
            auth.scopes.READ_UPLOAD,
            auth.scopes.WRITE_UPLOAD,
            auth.scopes.DELETE_UPLOAD_WORKSPACE.as_global()
        ])
        response = self.client.post(
            f"/filemanager/api/{self.upload_id}/lock",
            headers={'Authorization': self.admin_token}
        )
        self.assertEqual(response.status_code, status.OK,
                         f"Lock workspace '{self.upload_id}'.")

        logger.debug("Lock:\n" + str(response.data) + '\n')

        # Now unlock.
        response = self.client.post(
            f"/filemanager/api/{self.upload_id}/unlock",
            headers={'Authorization': self.admin_token}
        )
        self.assertEqual(response.status_code, status.OK,
                         f"Unlock workspace '{self.upload_id}'.")

        logger.debug("Unlock:\n{response.data}\n")

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

    def test_upload_files_to_unlocked_workspace(self):
        """Try to upload files to an unlocked workspace."""
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
        logger.debug("Upload files to unlocked workspace:\n{response.data}\n")

    def test_get_status_unlocked_workspace(self):
        """Get the status of a unlocked workspace."""
        response = self.client.get(f"/filemanager/api/{self.upload_id}",
                                   headers={'Authorization': self.token})

        self.assertEqual(response.status_code, status.OK,
                         "Request upload summary on unlocked workspace (OK)")
        response_data = json.loads(response.data)
        self.assertEqual(response_data['lock_state'],
                         UploadWorkspace.LockState.UNLOCKED.value)

    def test_attempt_to_delete_a_file_in_unlocked_workspace(self):
        """Attempt to delete a file in an unlocked workspace."""
        public_file_path = 'somefile'
        response = self.client.delete(
            f"/filemanager/api/{self.upload_id}/{public_file_path}",
            headers={'Authorization': self.token}
        )
        logger.debug(f"Delete File Response(locked): '{public_file_path}'\n"
              f" {response.data}\n")
        self.assertEqual(response.status_code, status.NOT_FOUND,
                         "Get a normal 404 when the workspace is unlocked")

    def test_delete_all_files_in_unlocked_workspace(self):
        """Attempt to delete all files in my workspace (normal)."""
        response = self.client.post(
            f"/filemanager/api/{self.upload_id}/delete_all",
            headers={'Authorization': self.token},
            content_type='multipart/form-data'
        )
        logger.debug("Delete All Files Response (unlocked):\n{response.data}\n")
        self.assertEqual(response.status_code, status.OK,
                         'Can delete files from an unlocked workspace')