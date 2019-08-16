import re
import os
import json
import tempfile
import tarfile
from io import BytesIO
from http import HTTPStatus as status
from typing import Dict, Any
from unittest import TestCase
from hashlib import md5
from base64 import urlsafe_b64encode

import jsonschema

from arxiv.users import domain, auth
from arxiv.users.auth import scopes

from filemanager.factory import create_web_app
from filemanager.services import database
from filemanager.domain import Workspace
from .util import generate_token



class TestCheckpoints(TestCase):
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

    def checksum(self, filepath) -> str:
        """
        Calculate MD5 checksum for file.

        Returns
        -------
        Returns Null string if file does not exist otherwise
        return b64-encoded MD5 hash of the specified file.

        """
        if os.path.exists(filepath):
            hash_md5 = md5()
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return urlsafe_b64encode(hash_md5.digest()).decode('utf-8')

        return ""

    def unpack_tarfile(self, tarfile_path: str, target_directory: str) -> None:
        """
        Fast and dirty routine to unpack a tarfile.

        Parameters
        ----------
        tarfile_path : str
            Absolute path to the tarfile.
        target_directory : str
            Directory into which the tarfile should be unpacked.

        """
        with tarfile.open(tarfile_path) as tar:
            tar.extractall(path=target_directory)

        found = True

        while found:

            found = False

            for root_directory, _, files in os.walk(target_directory):
                for file in files:
                    if re.search('.*.tar.gz', file):
                        found = True
                        sub_filepath_ref = os.path.join(root_directory, file)
                        with tarfile.open(sub_filepath_ref) as tar:
                            tar.extractall(path=root_directory)
                        os.remove(sub_filepath_ref)

    def test_checkpoints(self) -> None:
        """
        Test various checkpoint functions.

        Returns
        -------

        """
        fdir = os.path.join(self.DATA_PATH, 'test_files_upload')

        # Create a token for writing to upload workspace
        token = generate_token(self.app, [scopes.READ_UPLOAD,
                                          scopes.WRITE_UPLOAD,
                                          scopes.DELETE_UPLOAD_FILE])

        # Create a token with checkpoint scopes with upload read/write scopes
        checkpoint_token = generate_token(self.app,
                                          [scopes.READ_UPLOAD,
                                           scopes.WRITE_UPLOAD,
                                           scopes.DELETE_UPLOAD_FILE,
                                           scopes.CREATE_UPLOAD_CHECKPOINT,
                                           scopes.READ_UPLOAD_CHECKPOINT,
                                           scopes.DELETE_UPLOAD_CHECKPOINT,
                                           scopes.RESTORE_UPLOAD_CHECKPOINT])

        # TEST INDEPENDENT CHECKPOINT REQUESTS (checkpoint/list_checkpoints/
        #       delete_checkpoint/delete_all_checkpoints/restore_checkpoint)

        # Upload tests files
        fpath = os.path.join(fdir, 'UnpackWithSubdirectories.tar.gz')
        fname = os.path.basename(fpath)
        response = self.client.post('/filemanager/api/',
                                    data={'file': (open(fpath, 'rb'), fname)},
                                    headers={'Authorization': token},
                                    content_type='multipart/form-data')

        upload_data = json.loads(response.data)
        try:
            jsonschema.validate(upload_data, self.schema)
        except jsonschema.exceptions.SchemaError as e:
            self.fail(e)

        # Let's clean out all checkpoints
        response = self.client.post(
            f"/filemanager/api/{upload_data['upload_id']}/delete_all_checkpoints",
            headers={'Authorization': checkpoint_token},
            content_type='multipart/form-data'
        )
        self.assertEqual(response.status_code, status.OK,
                         "Delete all checkpoints")

        response = self.client.post(
            f"/filemanager/api/{upload_data['upload_id']}/checkpoint",
            headers={'Authorization': token},
            content_type='multipart/form-data'
        )

        self.assertEqual(response.status_code, status.FORBIDDEN)

        # Try with correct token with checkpoint scopes
        response = self.client.post(
            f"/filemanager/api/{upload_data['upload_id']}/checkpoint",
            headers={'Authorization': checkpoint_token},
            content_type='multipart/form-data'
        )

        self.assertEqual(response.status_code, status.OK)


        # Upload different set of files - checkpoint

        # Delete all files in my workspace (normal)
        response = self.client.post(
            f"/filemanager/api/{upload_data['upload_id']}/delete_all",
            headers={'Authorization': token},
            content_type='multipart/form-data'
        )

        self.assertEqual(response.status_code, status.OK,
                         "Delete all user-uploaded files.")

        # Upload tests files
        fpath = os.path.join(fdir, 'upload2.tar.gz')
        fname = os.path.basename(fpath)
        response = self.client.post(
            f"/filemanager/api/{upload_data['upload_id']}",
            data={'file': (open(fpath, 'rb'), fname),},
            headers={'Authorization': token},
            content_type='multipart/form-data'
        )
        self.assertEqual(response.status_code, status.CREATED,
                         "Accepted and processed uploaded Submission Contents")

        upload_data = json.loads(response.data)
        try:
            jsonschema.validate(upload_data, self.schema)
        except jsonschema.exceptions.SchemaError as e:
            self.fail(e)

        response = self.client.post(
            f"/filemanager/api/{upload_data['upload_id']}/checkpoint",
            headers={'Authorization': checkpoint_token},
            content_type='multipart/form-data'
        )

        self.assertEqual(response.status_code, status.OK)

        # End second upload

        # Create unecessary checkpoint
        response = self.client.post(
            f"/filemanager/api/{upload_data['upload_id']}/checkpoint",
            headers={'Authorization': checkpoint_token},
            content_type='multipart/form-data'
        )

        self.assertEqual(response.status_code, status.OK)

        # List checkpoints
        response = self.client.get(
            f"/filemanager/api/{upload_data['upload_id']}/list_checkpoints",
            headers={'Authorization': checkpoint_token},
            content_type='multipart/form-data'
        )

        self.assertEqual(response.status_code, status.OK)

        upload_data = json.loads(response.data)

        checkpoints = upload_data['checkpoints']

        self.assertEqual(len(checkpoints), 3,
                         "So far we've created three checkpoints.")

        # Locate the first checkpoint
        for item in checkpoints:
            if item['name'] == "checkpoint_1_theuser.tar.gz":
                checkpoint_checksum = item['checksum']

        # checkpoint_checksum = checkpoints[0]['checksum']
        print(f"***Checkpoint to restore: {checkpoint_checksum}***")


        # Restore checkpoints
        response = self.client.get(
            f"/filemanager/api/{upload_data['upload_id']}/"
            f"restore_checkpoint/{checkpoint_checksum}",
            headers={'Authorization': checkpoint_token},
            content_type='multipart/form-data'
        )

        self.assertEqual(response.status_code, status.OK)

        # Check if known checkpoint exists
        response = self.client.head(
            f"/filemanager/api/{upload_data['upload_id']}"
            f"/checkpoint/{checkpoint_checksum}",
            headers={'Authorization': checkpoint_token}
        )
        self.assertEqual(response.status_code, status.OK)
        self.assertIn('ETag', response.headers, "Returns an ETag header")

        # Check whether bad/invalid checkpoint exists
        response = self.client.head(
            f"/filemanager/api/{upload_data['upload_id']}"
            "/checkpoint/0981354098324",
            headers={'Authorization': checkpoint_token}
        )
        self.assertEqual(response.status_code, status.NOT_FOUND)

        # Download content
        response = self.client.get(
            f"/filemanager/api/{upload_data['upload_id']}"
            f"/checkpoint/{checkpoint_checksum}",
            headers={'Authorization': checkpoint_token}
        )
        self.assertEqual(response.status_code, status.OK)
        self.assertIn('ETag', response.headers, "Returns an ETag header")

        workdir = tempfile.mkdtemp()
        with tarfile.open(fileobj=BytesIO(response.data)) as tar:
            tar.extractall(path=workdir)

        # Compare downloaded checksum gzipped tar to original test submission
        # gzipped tar.
        #
        # Note that this comparison WILL NOT WORK for submissions in the case
        # where the file manager has edited/modified files during the upload
        # process.
        #
        # 2019-07-18: I removed directories from the comparison, because it is
        # likely for their to be an empty ``anc`` directory in the checkpoint
        # tarball that is not present in the reference tarball, and this is a
        # reflection of an implementation detail of the workspace rather than
        # indicating fidelity of the checkpoint. By comparing paths + checksums
        # (rather than just filenames + checksums) we capture both the fidelity
        # of the files and the relevant fidelity of the directory structure.
        # -- Erick
        #
        checkpoint_checksum_dict = {}
        for root_directory, _, files in os.walk(workdir):
            for file in files:
                _, path = os.path.join(root_directory, file).split(workdir, 1)
                checkpoint_checksum_dict[path] = self.checksum(path)

        # Analyze original submission gzipped tar
        workdir_ref = tempfile.mkdtemp()
        filepath_ref = os.path.join(fdir, 'UnpackWithSubdirectories.tar.gz')

        # unpack the tar file
        self.unpack_tarfile(filepath_ref, workdir_ref)

        reference_checksum_dict = {}
        for root_directory, _, files in os.walk(workdir_ref):
            for file in files:
                _, path = os.path.join(root_directory, file).split(workdir_ref, 1)
                reference_checksum_dict[path] = self.checksum(path)

        # Create sets containing file/checksum for checkpoint and original test
        # archive
        filesetc = set(checkpoint_checksum_dict.items())
        filesetr = set(reference_checksum_dict.items())

        # Test that checkpoint and submission contain the same files.
        self.assertSetEqual(filesetc, filesetr,
                            "The checkpoint and orginal submission gzipped tar"
                            " files should contain the same files/directories")


        # Let's delete second checkpoint file
        checkpoint_checksum = checkpoints[1]['checksum']

        # Delete checkpoints
        response = self.client.delete(
            f"/filemanager/api/{upload_data['upload_id']}/"
            f"delete_checkpoint/{checkpoint_checksum}",
            headers={'Authorization': checkpoint_token},
            content_type='multipart/form-data'
        )
        self.assertEqual(response.status_code, status.OK)

        # List checkpoint to see what we have left
        response = self.client.get(
            f"/filemanager/api/{upload_data['upload_id']}/list_checkpoints",
            headers={'Authorization': checkpoint_token},
            content_type='multipart/form-data'
        )
        self.assertEqual(response.status_code, status.OK)

        upload_data = json.loads(response.data)
        checkpoints = upload_data['checkpoints']
        self.assertEqual(len(checkpoints), 2,
                         "There are two checkpoints left.")

        # Now let's blow away all checkpoints
        response = self.client.post(
            f"/filemanager/api/{upload_data['upload_id']}"
            "/delete_all_checkpoints",
            headers={'Authorization': checkpoint_token},
            content_type='multipart/form-data'
        )
        self.assertEqual(response.status_code, status.OK)

        # List checkpoint to see what we have left after remove all
        response = self.client.get(
            f"/filemanager/api/{upload_data['upload_id']}/list_checkpoints",
            headers={'Authorization': checkpoint_token},
            content_type='multipart/form-data'
        )
        self.assertEqual(response.status_code, status.OK)

        upload_data = json.loads(response.data)
        checkpoints = upload_data['checkpoints']
        self.assertEqual(len(checkpoints), 0,
                         "All checkpoints have been deleted.")

        # Try to restore a checkpoint that was deleted.
        response = self.client.delete(
            f"/filemanager/api/{upload_data['upload_id']}/"
            f"delete_checkpoint/{checkpoint_checksum}",
            headers={'Authorization': checkpoint_token},
            content_type='multipart/form-data'
        )

        self.assertEqual(response.status_code, status.NOT_FOUND)

        # Delete the workspace
        # Create admin token for deleting upload workspace
        admin_token = generate_token(self.app, [
            scopes.READ_UPLOAD,
            scopes.WRITE_UPLOAD,
            scopes.DELETE_UPLOAD_WORKSPACE.as_global()
        ])

        response = self.client.delete(
            f"/filemanager/api/{upload_data['upload_id']}",
            headers={'Authorization': admin_token}
        )

        # This cleans out the workspace. Comment out if you want to inspect
        # files in workspace. Source log is saved to 'deleted_workspace_logs'
        # directory.
        self.assertEqual(response.status_code, status.OK,
                         "Accepted request to delete workspace.")


        # NOW TEST API LEVEL CHECKPOINT VIA UPLOAD REQUEST

        # Upload tests files
        fpath = os.path.join(fdir, 'UnpackWithSubdirectories.tar.gz')
        fname = os.path.basename(fpath)
        response = self.client.post('/filemanager/api/',
                                    data={'file': (open(fpath, 'rb'), fname)},
                                    headers={'Authorization': token},
                                    content_type='multipart/form-data')
        self.assertEqual(response.status_code, status.CREATED,
                         "Accepted and processed uploaded Submission Contents")

        upload_data = json.loads(response.data)
        try:
            jsonschema.validate(upload_data, self.schema)
        except jsonschema.exceptions.SchemaError as e:
            self.fail(e)

        # Upload tests files
        fpath = os.path.join(fdir, 'upload2.tar.gz')
        fname = os.path.basename(fpath)
        response = self.client.post(
            f"/filemanager/api/{upload_data['upload_id']}"
            "/checkpoint_with_upload",
            data={'file': (open(fpath, 'rb'), fname),},
            headers={'Authorization': checkpoint_token},
            content_type='multipart/form-data'
        )
        self.assertEqual(response.status_code, status.CREATED,
                         "Accepted and processed uploaded Submission Contents")

        upload_data = json.loads(response.data)
        try:
            jsonschema.validate(upload_data, self.schema)
        except jsonschema.exceptions.SchemaError as e:
            self.fail(e)

        # List checkpoint to see what we have left after remove all
        response = self.client.get(
            f"/filemanager/api/{upload_data['upload_id']}/list_checkpoints",
            headers={'Authorization': checkpoint_token},
            content_type='multipart/form-data'
        )
        self.assertEqual(response.status_code, status.OK)

        # Delete all files and then try to create checkpoint (fail)

        # Delete all files in my workspace (success before failure)
        response = self.client.post(
            f"/filemanager/api/{upload_data['upload_id']}/delete_all",
            headers={'Authorization': token},
            content_type='multipart/form-data'
        )

        self.assertEqual(response.status_code, status.OK,
                         "Delete all user-uploaded files.")

        # Now try to create checkpoint when there are no source files.
        response = self.client.post(
            f"/filemanager/api/{upload_data['upload_id']}/checkpoint",
            headers={'Authorization': checkpoint_token},
            content_type='multipart/form-data'
        )

        self.assertEqual(response.status_code, status.BAD_REQUEST)

        # One last sneaky test for checkpoint when there are no files.
        # Let's upload a submission (with checkpoint) when there are no
        # source files.

        # Upload tests files
        fpath = os.path.join(fdir, 'upload2.tar.gz')
        fname = os.path.basename(fpath)
        response = self.client.post(
            f"/filemanager/api/{upload_data['upload_id']}"
            "/checkpoint_with_upload",
            data={'file': (open(fpath, 'rb'), fname),},
            headers={'Authorization': checkpoint_token},
            content_type='multipart/form-data'
        )
        self.assertEqual(response.status_code, status.BAD_REQUEST,
                         "Try to checkpoint with upload when there are no "
                         "existing files in workspace.")

        # Delete the workspace
        # Create admin token for deleting upload workspace
        admin_token = generate_token(self.app, [
            scopes.READ_UPLOAD,
            scopes.WRITE_UPLOAD,
            scopes.DELETE_UPLOAD_WORKSPACE.as_global()
        ])

        response = self.client.delete(
            f"/filemanager/api/{upload_data['upload_id']}",
            headers={'Authorization': admin_token})

        # This cleans out the workspace. Comment out if you want to inspect
        # files in workspace. Source log is saved to 'deleted_workspace_logs'
        # directory.
        self.assertEqual(response.status_code, status.OK,
                         "Accepted request to delete workspace.")