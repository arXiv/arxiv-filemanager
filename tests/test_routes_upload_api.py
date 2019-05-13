"""Tests for :mod:`filemanager.routes.upload_api`."""

from unittest import TestCase, mock
from datetime import datetime, timedelta
from pytz import UTC
import json
import tempfile
import filecmp
from io import BytesIO
import tarfile
import os
import re
import uuid
import os.path
from typing import Any, Optional, Dict, List
from io import BytesIO
import jsonschema
import jwt
from requests.utils import quote
from flask import Flask
from filemanager.factory import create_web_app
from filemanager.services import uploads

from arxiv.users import domain, auth
from http import HTTPStatus as status

from hashlib import md5
from base64 import urlsafe_b64encode

TEST_FILES_STRIP_PS = os.path.join(os.getcwd(), 'tests/test_files_strip_postscript')


# Generate authentication token
def generate_token(app: Flask, scope: List[str]) -> str:
    """Helper function for generating a JWT."""
    secret = app.config.get('JWT_SECRET')
    start = datetime.now(tz=UTC)
    end = start + timedelta(seconds=36000)  # Make this as long as you want.
    user_id = '1'
    email = 'foo@bar.com'
    username = 'theuser'
    first_name = 'Jane'
    last_name = 'Doe'
    suffix_name = 'IV'
    affiliation = 'Cornell University'
    rank = 3
    country = 'us'
    default_category = 'astro-ph.GA'
    submission_groups = 'grp_physics'
    endorsements = 'astro-ph.CO,astro-ph.GA'
    session = domain.Session(
        session_id=str(uuid.uuid4()),
        start_time=start, end_time=end,
        user=domain.User(
            user_id=user_id,
            email=email,
            username=username,
            name=domain.UserFullName(first_name, last_name, suffix_name),
            profile=domain.UserProfile(
                affiliation=affiliation,
                rank=int(rank),
                country=country,
                default_category=domain.Category(default_category),
                submission_groups=submission_groups.split(',')
            )
        ),
        authorizations=domain.Authorizations(
            scopes=scope,
            endorsements=[domain.Category(cat.split('.', 1))
                          for cat in endorsements.split(',')]
        )
    )
    token = auth.tokens.encode(session, secret)
    return token


def checksum(filepath) -> str:
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

def UnpackTarFile(tarfile_path: str, target_directory: str) -> None:
    """
    Fast and dirty routine to unpack
    Parameters
    ----------
    file
    target_directory

    """
    with tarfile.open(tarfile_path) as tar:
        tar.extractall(path=target_directory)

    found = True

    while found:

        found = False

        for root_directory, directories, files in os.walk(target_directory):
            for file in files:
                if re.search('.*.tar.gz', file):
                    found = True
                    sub_filepath_ref = os.path.join(root_directory, file)
                    with tarfile.open(sub_filepath_ref) as tar:
                        tar.extractall(path=root_directory)
                    os.remove(sub_filepath_ref)


class TestUploadAPIRoutes(TestCase):
    """Sample tests for upload external API routes."""

    def setUp(self) -> None:
        """Initialize the Flask application, and get a client for testing."""
        # There is a bug in arxiv.base where it doesn't pick up app config
        # parameters. Until then, we pass it to os.environ.
        self.app = create_web_app()
        os.environ['JWT_SECRET'] = self.app.config.get('JWT_SECRET')
        self.client = self.app.test_client()
        self.app.app_context().push()
        uploads.db.create_all()

    # # Provide general statistics on the upload service. Primarily intended to
    # # indicate normal operation or exception conditions. This information will be
    # # expanded greatly in coming weeks
    # # @mock.patch('zero.controllers.upload.status')
    # # def test_service_status(self, mock_get_baz: Any) -> None:
    # def test_service_status(self) -> None:
    #     """Endpoint /filemanager/upload/status<int> returns JSON about file management service."""
    #
    #     with open('schema/resources/serviceStatus.json') as f:
    #         schema = json.load(f)
    #
    #     print("\nMake service-level 'status' request\n")
    #
    #     # response = self.client.get('/zero/upload/create')
    #     response = self.client.get('/filemanager/api/status')
    #
    #     expected_data = {'status': 'OK', 'total_uploads': 1}
    #     print(response)
    #     self.assertEqual(response.status_code, 200)
    #     self.assertDictEqual(json.loads(response.data), expected_data)
    #
    #     try:
    #         jsonschema.validate(json.loads(response.data), schema)
    #     except jsonschema.exceptions.SchemaError as e:
    #         self.fail(e)

    # Create upload folder/container
    def test_create_upload_failures(self) -> None:
        """Endpoint /filemanager/upload/create_upload returns JSON about a new upload."""

        # No token
        response = self.client.post('/filemanager/api/',
                                    data={
                                        'file': '',
                                    },
                                    # Missing authorization field
                                    # headers={'Authorization': ''},
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, 401, 'Authorization token not passed to server')

        # Authorization argument without valid token
        response = self.client.post('/filemanager/api/',
                                    data={
                                        'file': '',
                                    },
                                    # Empty token value
                                    headers={'Authorization': ''},
                                    #        content_type='application/gzip')
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, 401, 'Empty authorization token passed to server')

        # Create an INVALID token for writing to upload workspace
        token = generate_token(self.app, [auth.scopes.READ_UPLOAD])

        # Create path to test file
        cwd = os.getcwd()
        testfiles_dir = os.path.join(cwd, 'tests/test_files_upload')
        filepath = os.path.join(testfiles_dir, '1801.03879-1.tar.gz')

        # Prepare gzipped tar submission for upload
        filename = os.path.basename(filepath)

        # Missing 'file' argument
        response = self.client.post('/filemanager/api/',
                                    data={
                                        # 'file': (io.BytesIO(b"abcdef"), 'test.jpg'),
                                        #      'file': (open(filepath, 'rb'), 'test.tar.gz'),
                                        'file': (open(filepath, 'rb'), filename),
                                    },
                                    # Bad token - invalid permissions
                                    headers={'Authorization': token},
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, 403, 'Invalid authorization token passed to server')

        # TODO: Need to add tests for user who does not have permissions to act on workspace
        #       This requires updating to NEW auth/z implementation. Soon!

        # Create a VALID token for writing to upload workspace
        token = generate_token(self.app, [auth.scopes.READ_UPLOAD,
                                          auth.scopes.WRITE_UPLOAD])

        # File payload missing
        response = self.client.post('/filemanager/api/',
                                    data={
                                        # File payload is missing
                                        'fileXX': (open(filepath, 'rb'), ''),
                                    },
                                    # Good Token
                                    headers={'Authorization': token},
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, 400, 'Upload file payload not passed to server')

        expected_data = {'reason': 'missing file/archive payload'}
        self.assertDictEqual(json.loads(response.data), expected_data)

        # TODO: Looks like this condition is not possible, though online forum
        # noted possibility of null name.

        # Filename missing or null
        response = self.client.post('/filemanager/api/',
                                    data={
                                        # filename is null
                                        'file': (open(filepath, 'rb'), ''),
                                    },
                                    # Good Token
                                    headers={'Authorization': token},
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, 400, 'Valid authorization token not passed to server')

        expected_data = {'reason': 'file argument missing filename or file not selected'}
        self.assertDictEqual(json.loads(response.data), expected_data)

        # Set up new test

        # testfiles_dir = os.path.join(cwd, 'tests/test_files_upload')
        testfiles_dir = '/tmp'
        filepath = os.path.join(testfiles_dir, 'nullfile')
        open(filepath, 'wb').close()  # touch

        # Upload empty/null file
        response = self.client.post('/filemanager/api/',
                                    data={
                                        # filename is null
                                        'file': (open(filepath, 'rb'), 'Empty'),
                                    },
                                    # Good Token
                                    headers={'Authorization': token},
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, 400, 'Empty file uploaded to server')

        expected_data = {'reason': 'file payload is zero length'}
        self.assertDictEqual(json.loads(response.data), expected_data)

        # TODO: Think of other potential create upload errors.

    # Upload a submission package
    def test_existing_upload_failures(self) -> None:
        """Test various failure conditions on existing workspaces.

        The same function handles new upload request so we will not repeat
        basic argument failures that have been covered already"""

        with open('schema/resources/uploadResult.json') as f:
            schema = json.load(f)

        # Create a token for writing to upload workspace
        token = generate_token(self.app, [auth.scopes.READ_UPLOAD,
                                          auth.scopes.WRITE_UPLOAD])

        created = datetime.now(UTC)
        modified = datetime.now(UTC)
        expected_data = {'upload_id': 5,
                         'status': "SUCCEEDED",
                         'create_datetime': created.isoformat(),
                         'modify_datetime': modified.isoformat()
                         }

        cwd = os.getcwd()
        testfiles_dir = os.path.join(cwd, 'tests/test_files_upload')
        filepath = os.path.join(testfiles_dir, '1801.03879-1.tar.gz')

        # Prepare gzipped tar submission for upload
        filename = os.path.basename(filepath)

        # Post a test submission to upload API

        bad_upload_id = '9999'

        # Upload file to non existent workspace!! Yikes!
        response = self.client.post(f'/filemanager/api/{bad_upload_id}',
                                    data={
                                        'file': (open(filepath, 'rb'), filename),
                                    },
                                    headers={'Authorization': token},
                                    #        content_type='application/gzip')
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, 404, "Accepted uploaded Submission Contents")

        expected_data = {'reason': 'upload workspace not found'}

        self.maxDiff = None
        self.assertDictEqual(json.loads(response.data), expected_data)

        response = self.client.get(f"/filemanager/api/{bad_upload_id}",
                                   headers={'Authorization': token})

        self.assertEqual(response.status_code, 404, "Accepted uploaded Submission Contents")

        expected_data = {'reason': 'upload workspace not found'}

        self.maxDiff = None
        self.assertDictEqual(json.loads(response.data), expected_data)

        # TODO: Add tests for locked/released workspaces on upload requests.
        # TODO: Lock/unlock, release/unrelease. (when implements)

        # TODO: Add size checks (when implemented)

    def test_various_log_download_requests(self) -> None:
        """
        Test service and source log download requests.

        Returns
        -------
        Requested log file.

        """
        # Create a token for writing to upload workspace
        token = generate_token(self.app, [auth.scopes.READ_UPLOAD,
                                          auth.scopes.WRITE_UPLOAD,
                                          auth.scopes.DELETE_UPLOAD_FILE])

        # Upload a gzipped tar archive package containing files to delete.
        cwd = os.getcwd()
        testfiles_dir = os.path.join(cwd, 'tests/test_files_upload')
        upload_package_name = 'upload2.tar.gz'
        filepath = os.path.join(testfiles_dir, upload_package_name)
        # Prepare gzipped tar submission for upload
        filename = os.path.basename(filepath)

        # Upload some files so we can delete them
        # response = self.client.post('/filemanager/api/',
        response = self.client.post('/filemanager/api/',
                                    data={
                                        'file': (open(filepath, 'rb'), filename),
                                    },
                                    headers={'Authorization': token},
                                    #        content_type='application/gzip')
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, 201, "Accepted and processed uploaded Submission Contents")

        upload_data: Dict[str, Any] = json.loads(response.data)

        # Create unauthorized admin token (can't read logs)
        admin_token = generate_token(self.app, [auth.scopes.READ_UPLOAD,
                                                auth.scopes.WRITE_UPLOAD,
                                                auth.scopes.DELETE_UPLOAD_WORKSPACE.as_global()])

        # Source logs

        # Attempt to check if source log exists
        response = self.client.head(
            f"/filemanager/api/{upload_data['upload_id']}/log",
            headers={'Authorization': admin_token}
        )
        self.assertEqual(response.status_code, status.FORBIDDEN)

        response = self.client.get(
            f"/filemanager/api/{upload_data['upload_id']}/log",
            headers={'Authorization': admin_token}
        )
        self.assertEqual(response.status_code, status.FORBIDDEN)

        # Add READ_UPLOAD_LOGS authorization to admin token
        admin_token = generate_token(self.app, [auth.scopes.READ_UPLOAD,
                                                auth.scopes.WRITE_UPLOAD,
                                                auth.scopes.READ_UPLOAD_LOGS,
                                                auth.scopes.DELETE_UPLOAD_WORKSPACE.as_global()])

        # Attempt to check if source log exists
        response = self.client.head(
            f"/filemanager/api/{upload_data['upload_id']}/log",
            headers={'Authorization': admin_token}
        )
        self.assertEqual(response.status_code, status.OK)
        self.assertIn('ETag', response.headers, "Returns an ETag header")

        response = self.client.get(
            f"/filemanager/api/{upload_data['upload_id']}/log",
            headers={'Authorization': admin_token}
        )
        self.assertEqual(response.status_code, status.OK)
        self.assertIn('ETag', response.headers, "Returns an ETag header")

        # Look for something in upload source log
        self.assertIn(rb'unpack gzipped upload2.tar.gz to dir', response.data,
                      'Test that upload file is in log.')

        # Write service log to file
        workdir = tempfile.mkdtemp()
        upload_log_filename = "upload_log_" + str(upload_data['upload_id'])
        log_path = os.path.join(workdir, upload_log_filename)
        fileH = open(log_path, 'wb')
        fileH.write(response.data)
        fileH.close()

        # Highlight log download. Remove at some point.
        print(f"FYI: SAVED UPLOAD SOURCE LOG FILE TO DISK: {log_path}\n")

        # Service logs

        # Try to check whether log exits without appropriate authorization
        response = self.client.head(
            f"/filemanager/api/log",
            headers={'Authorization': admin_token}
        )
        self.assertEqual(response.status_code, status.FORBIDDEN)

        response = self.client.get(
            f"/filemanager/api/log",
            headers={'Authorization': admin_token}
        )
        self.assertEqual(response.status_code, status.FORBIDDEN)

        # Create admin token for deleting upload workspace
        admin_token = generate_token(self.app, [auth.scopes.READ_UPLOAD,
                                                auth.scopes.WRITE_UPLOAD,
                                                auth.scopes.READ_UPLOAD_SERVICE_LOGS,
                                                auth.scopes.DELETE_UPLOAD_WORKSPACE.as_global()])

        # Try to check whether log exits with correct authorization
        response = self.client.head(
            f"/filemanager/api/log",
            headers={'Authorization': admin_token}
        )
        self.assertEqual(response.status_code, status.OK)
        self.assertIn('ETag', response.headers, "Returns an ETag header")

        # Try to download service log
        response = self.client.get(
            f"/filemanager/api/log",
            headers={'Authorization': admin_token}
        )
        self.assertEqual(response.status_code, status.OK)
        self.assertIn('ETag', response.headers, "Returns an ETag header")

        # Write service log to file (to save temporary directory where we saved source_log)
        log_path = os.path.join(workdir, "service_log")
        fileH = open(log_path, 'wb')
        fileH.write(response.data)
        fileH.close()

        # Highlight log download. Remove at some point.
        print(f"FYI: SAVED SERVICE LOG FILE TO DISK AT: {log_path}\n")

        # Delete the workspace

        response = self.client.delete(f"/filemanager/api/{upload_data['upload_id']}",
                                      headers={'Authorization': admin_token}
                                      )

        # This cleans out the workspace. Comment out if you want to inspect files
        # in workspace. Source log is saved to 'deleted_workspace_logs' directory.
        self.assertEqual(response.status_code, 200, "Accepted request to delete workspace.")

    def test_individual_file_content_download(self) -> None:
        """
        Test download of individual content files.

        Try our best to break things.

        """
        # Create a token for writing to upload workspace
        token = generate_token(self.app, [auth.scopes.READ_UPLOAD,
                                          auth.scopes.WRITE_UPLOAD,
                                          auth.scopes.DELETE_UPLOAD_FILE])

        # Upload a gzipped tar archive package containing files to delete.
        cwd = os.getcwd()
        testfiles_dir = os.path.join(cwd, 'tests/test_files_upload')
        upload_package_name = 'upload2.tar.gz'
        filepath = os.path.join(testfiles_dir, upload_package_name)
        # Prepare gzipped tar submission for upload
        filename = os.path.basename(filepath)

        # Upload some files so we can delete them
        # response = self.client.post('/filemanager/api/',
        response = self.client.post('/filemanager/api/',
                                    data={
                                        'file': (open(filepath, 'rb'), filename),
                                    },
                                    headers={'Authorization': token},
                                    #        content_type='application/gzip')
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, 201, "Accepted and processed uploaded Submission Contents")

        upload_data: Dict[str, Any] = json.loads(response.data)


        # Check if content file exists
        response = self.client.head(
            f"/filemanager/api/{upload_data['upload_id']}/main_a.tex/content",
            headers={'Authorization': token}
        )
        self.assertEqual(response.status_code, status.OK)
        self.assertIn('ETag', response.headers, "Returns an ETag header")

        # Download content file
        response = self.client.get(
            f"/filemanager/api/{upload_data['upload_id']}/main_a.tex/content",
            headers={'Authorization': token}
        )
        self.assertEqual(response.status_code, status.OK)
        self.assertIn('ETag', response.headers, "Returns an ETag header")

        workdir = tempfile.mkdtemp()

        # Write out file (to save temporary directory where we saved source_log)
        log_path = os.path.join(workdir, "main_a.tex")
        fileH = open(log_path, 'wb')
        fileH.write(response.data)
        fileH.close()

        print(f'List downloaded content directory: {workdir}\n')
        print(os.listdir(workdir))


        # Test for file that doesn't exist
        response = self.client.head(
            f"/filemanager/api/{upload_data['upload_id']}/doesntexist.tex/content",
            headers={'Authorization': token}
        )
        self.assertEqual(response.status_code, status.NOT_FOUND,
                         "Trying to check non-existent should fail.")
        #self.assertIn('ETag', response.headers, "Returns an ETag header")

        # Try to download non-existent file anyways
        response = self.client.get(
            f"/filemanager/api/{upload_data['upload_id']}/doesntexist.tex/content",
            headers={'Authorization': token}
        )
        self.assertEqual(response.status_code, status.NOT_FOUND)


        # Try to be naughty and download something outside of workspace

        # Assume these crazy developers stick their workspaces in an obvious
        # place like /tmp/filemanagement/submissions/<upload_id>
        crazy_path = "../../../etc/passwd"
        quote_crazy_path = quote(crazy_path, safe='')
        response = self.client.head(
            f"/filemanager/api/{upload_data['upload_id']}/{quote_crazy_path}/content",
            headers={'Authorization': token}
        )

        self.assertEqual(response.status_code, status.NOT_FOUND,
                         "Trying to check non-existent should fail.")

        # Delete the workspace
        # Create admin token for deleting upload workspace
        admin_token = generate_token(self.app, [auth.scopes.READ_UPLOAD,
                                                auth.scopes.WRITE_UPLOAD,
                                                auth.scopes.DELETE_UPLOAD_WORKSPACE.as_global()])

        response = self.client.delete(f"/filemanager/api/{upload_data['upload_id']}",
                                      headers={'Authorization': admin_token}
                                      )

        # This cleans out the workspace. Comment out if you want to inspect files
        # in workspace. Source log is saved to 'deleted_workspace_logs' directory.
        self.assertEqual(response.status_code, 200, "Accepted request to delete workspace.")


    def test_delete_file(self) -> None:
        """
        Test delete file operation.

        These tests will focus on triggering delete failures.

        """
        # Create a token for writing to upload workspace
        token = generate_token(self.app, [auth.scopes.READ_UPLOAD,
                                          auth.scopes.WRITE_UPLOAD,
                                          auth.scopes.DELETE_UPLOAD_FILE])

        # Upload a gzipped tar archive package containing files to delete.
        cwd = os.getcwd()
        testfiles_dir = os.path.join(cwd, 'tests/test_files_upload')
        filepath = os.path.join(testfiles_dir, 'UploadWithANCDirectory.tar.gz')
        # Prepare gzipped tar submission for upload
        filename = os.path.basename(filepath)

        # Upload some files so we can delete them
        # response = self.client.post('/filemanager/api/',
        response = self.client.post('/filemanager/api/',
                                    data={
                                        # 'file': (io.BytesIO(b"abcdef"), 'test.jpg'),
                                        #      'file': (open(filepath, 'rb'), 'test.tar.gz'),
                                        'file': (open(filepath, 'rb'), filename),
                                    },
                                    headers={'Authorization': token},
                                    #        content_type='application/gzip')
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, 201, "Accepted and processed uploaded Submission Contents")

        # This upload should work but we'll check the response anyway
        with open('schema/resources/uploadResult.json') as f:
            schema = json.load(f)

        try:
            jsonschema.validate(json.loads(response.data), schema)
        except jsonschema.exceptions.SchemaError as e:
            self.fail(e)

        upload_data: Dict[str, Any] = json.loads(response.data)

        # Try a few valid deletions

        # Delete a file (normal call)
        public_file_path = "accessibilityMeta.sty"

        encoded_file_path = quote(public_file_path, safe='')
        public_file_path = encoded_file_path
        print(f"ENCODED:{public_file_path}\n")

        response = self.client.delete(f"/filemanager/api/{upload_data['upload_id']}/{public_file_path}",
                                      headers={'Authorization': token})
        print(f"Delete File Response:'{public_file_path}'\n" + str(response.data) + '\n')
        self.assertEqual(response.status_code, 200,
                         "Delete an individual file: '{public_file_path}'.")

        # expected_data = {'reason': 'deleted file'}
        # self.assertDictEqual(json.loads(response.data), expected_data)

        # Now try to break delete

        # This file path is a potential security threat. Attempt to detect such deviant
        # file deletions without alerting the client.
        public_file_path = "../../subdir/this_file"
        public_file_path = quote(public_file_path, safe='')
        response = self.client.delete(f"/filemanager/api/{upload_data['upload_id']}/{public_file_path}",
                                      headers={'Authorization': token})
        print(f"Delete hacker file path Response:'{public_file_path}'\n" + str(response.data) + '\n')
        self.assertEqual(response.status_code, 404,
                         f"Delete a file outside of workspace: '{public_file_path}'.")
        expected_data = {'reason': 'file not found'}
        self.assertDictEqual(json.loads(response.data), expected_data)

        # Another file path is a potential security threat. Attempt to detect such deviant
        # file deletions without alerting the client.
        public_file_path = "anc/../../etc/passwd"
        public_file_path = quote(public_file_path, safe='')
        response = self.client.delete(f"/filemanager/api/{upload_data['upload_id']}/{public_file_path}",
                                      headers={'Authorization': token})
        print(f"Delete hacker file path Response:'{public_file_path}'\n" + str(response.data) + '\n')
        self.assertEqual(response.status_code, 404,
                         f"Delete a file outside of workspace: '{public_file_path}'.")

        # Attempt to delete an important system file
        #
        # This generates an illegal URL so this doesn't make it to our code.
        public_file_path = "/etc/passwd"
        public_file_path = quote(public_file_path, safe='')
        response = self.client.delete(f"/filemanager/api/{upload_data['upload_id']}/{public_file_path}",
                                      headers={'Authorization': token})
        print(f"Delete system password file Response:'{public_file_path}'\n")
        self.assertEqual(response.status_code, 404,
                         f"Delete a system file: '{public_file_path}'..")

        # Try to delete non-existent file
        public_file_path = "somedirectory/lipics-logo-bw.pdf"
        public_file_path = quote(public_file_path, safe='')
        response = self.client.delete(f"/filemanager/api/{upload_data['upload_id']}/{public_file_path}",
                                      headers={'Authorization': token})
        print(f"Delete non-existent file Response:'{public_file_path}'\n" + str(response.data) + '\n')
        self.assertEqual(response.status_code, 404,
                         f"Delete non-existent file: '{public_file_path}'.")

        # Try to delete file in subdirectory - valid file deletion
        public_file_path = "anc/manuscript_Na2.7Ru4O9.tex"
        public_file_path = quote(public_file_path, safe='')
        response = self.client.delete(f"/filemanager/api/{upload_data['upload_id']}/{public_file_path}",
                                      headers={'Authorization': token})
        print(f"Delete file in subdirectory anc Response:'{public_file_path}'\n" + str(response.data) + '\n')
        self.assertEqual(response.status_code, 200,
                         f"Delete file in subdirectory: '{public_file_path}'.")

        # Try to delete file in subdirectory - valid file deletion
        public_file_path = "anc/fig8.PNG"
        public_file_path = quote(public_file_path, safe='')
        response = self.client.delete(f"/filemanager/api/{upload_data['upload_id']}/{public_file_path}",
                                      headers={'Authorization': token})
        print(f"Delete file in subdirectory anc Response:'{public_file_path}'\n" + str(response.data) + '\n')
        self.assertEqual(response.status_code, 200,
                         f"Delete file in subdirectory: '{public_file_path}'.")

        # Try an delete file a second time...we'll know if first delete really worked.
        public_file_path = "anc/manuscript_Na2.7Ru4O9.tex"
        public_file_path = quote(public_file_path, safe='')
        response = self.client.delete(f"/filemanager/api/{upload_data['upload_id']}/{public_file_path}",
                                      headers={'Authorization': token})
        print(f"Delete file in subdirectory anc Response:'{public_file_path}'\n" + str(response.data) + '\n')
        self.assertEqual(response.status_code, 404,
                         f"Delete file in subdirectory: '{public_file_path}'.")

        # Try a path that is not hacky but that we know secure_filename() will
        # filter out characters.
        #
        # Reject these filenames for now (because they're a little funny)
        #
        # TODO: I suppose we could map ~/ and ./ to root of src directory.
        #
        public_file_path = "~/anc/manuscript_Na2.7Ru4O9.tex"
        public_file_path = quote(public_file_path, safe='')
        response = self.client.delete(f"/filemanager/api/{upload_data['upload_id']}/{public_file_path}",
                                      headers={'Authorization': token})
        print(f"Delete invalid file in subdirectory anc Response:'{public_file_path}'\n" + str(response.data) + '\n')
        self.assertEqual(response.status_code, 404,
                         f"Delete file in subdirectory: '{public_file_path}'.")

        # Technically a legal file path, but where is client coming up with this path? Manually?
        public_file_path = "./anc/manuscript_Na2.7Ru4O9.tex"
        public_file_path = quote(public_file_path, safe='')
        response = self.client.delete(f"/filemanager/api/{upload_data['upload_id']}/{public_file_path}",
                                      headers={'Authorization': token})
        print(f"Delete invalid file in subdirectory anc Response:'{public_file_path}'\n" + str(response.data) + '\n')
        self.assertEqual(response.status_code, 404,
                         f"Delete file in subdirectory: '{public_file_path}'.")

        # Delete the workspace
        # Create admin token for deleting upload workspace
        admin_token = generate_token(self.app, [auth.scopes.READ_UPLOAD,
                                                auth.scopes.WRITE_UPLOAD,
                                                auth.scopes.DELETE_UPLOAD_WORKSPACE.as_global()])

        response = self.client.delete(f"/filemanager/api/{upload_data['upload_id']}",
                                      headers={'Authorization': admin_token}
                                      )

        # This cleans out the workspace. Comment out if you want to inspect files
        # in workspace. Source log is saved to 'deleted_workspace_logs' directory.
        self.assertEqual(response.status_code, 200, "Accepted request to delete workspace.")

    def test_delete_all_files(self) -> None:
        """
        Test delete file operation.

        These tests will focus on triggering delete failures.

        """
        # Create a token for writing to upload workspace
        token = generate_token(self.app, [auth.scopes.READ_UPLOAD,
                                          auth.scopes.WRITE_UPLOAD,
                                          auth.scopes.DELETE_UPLOAD_FILE])

        # Upload a gzipped tar archive package containing files to delete.
        cwd = os.getcwd()
        testfiles_dir = os.path.join(cwd, 'tests/test_files_upload')
        filepath = os.path.join(testfiles_dir, 'UploadWithANCDirectory.tar.gz')

        # Prepare gzipped tar submission for upload
        filename = os.path.basename(filepath)

        # Upload files to delete
        response = self.client.post('/filemanager/api/',
                                    data={
                                        # 'file': (io.BytesIO(b"abcdef"), 'test.jpg'),
                                        #      'file': (open(filepath, 'rb'), 'test.tar.gz'),
                                        'file': (open(filepath, 'rb'), filename),
                                    },
                                    headers={'Authorization': token},
                                    #        content_type='application/gzip')
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, 201, "Accepted and processed uploaded Submission Contents")

        # This upload should work but we'll check the response anyway
        with open('schema/resources/uploadResult.json') as f:
            schema = json.load(f)

        try:
            jsonschema.validate(json.loads(response.data), schema)
        except jsonschema.exceptions.SchemaError as e:
            self.fail(e)

        upload_data: Dict[str, Any] = json.loads(response.data)

        # Delete all files in my workspace (normal)
        response = self.client.post(f"/filemanager/api/{upload_data['upload_id']}/delete_all",
                                    headers={'Authorization': token},
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, 200, "Delete all user-uploaded files.")

        # There are really not many exceptions we can generate as long as the upload workspace
        # exists. If upload workspace exists this command will remove all files and directories
        # under src directory. At this point I don't anticipate generating exception when src
        # directory is already empty.

        # Delete all files in my workspace (that doesn't exist)
        response = self.client.post(f"/filemanager/api/999999/delete_all",
                                    headers={'Authorization': token},
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, 404,
                         "Delete all user-uploaded files for non-existent workspace.")

        expected_data = {'reason': 'upload workspace not found'}
        self.assertDictEqual(json.loads(response.data), expected_data)

        # Try an delete an individual file ...we'll know if delete all files really worked.
        public_file_path = "anc/manuscript_Na2.7Ru4O9.tex"
        public_file_path = quote(public_file_path, safe='')
        response = self.client.delete(f"/filemanager/api/{upload_data['upload_id']}/{public_file_path}",
                                      headers={'Authorization': token})
        print(f"Delete already deleted file in subdirectory anc Response:'{public_file_path}'\n" + str(
            response.data) + '\n')
        self.assertEqual(response.status_code, 404,
                         f"Delete already deleted file in subdirectory: '{public_file_path}'.")

        expected_data = {'reason': 'file not found'}
        self.assertDictEqual(json.loads(response.data), expected_data)

        # Delete the workspace
        # Create admin token for deleting upload workspace
        admin_token = generate_token(self.app, [auth.scopes.READ_UPLOAD,
                                                auth.scopes.WRITE_UPLOAD,
                                                auth.scopes.DELETE_UPLOAD_WORKSPACE.as_global()])

        response = self.client.delete(f"/filemanager/api/{upload_data['upload_id']}",
                                      headers={'Authorization': admin_token}
                                      )

        # This cleans out the workspace. Comment out if you want to inspect files
        # in workspace. Source log is saved to 'deleted_workspace_logs' directory.
        self.assertEqual(response.status_code, 200, "Accepted request to delete workspace.")


    def test_delete_upload_workspace(self) -> None:
        """
        Test delete file operation.

        These tests will focus on triggering delete failures.

        """

        # TODO: Need to work on this code after imlementing delete workspace.

        # Create a token for writing to upload workspace
        token = generate_token(self.app, [auth.scopes.READ_UPLOAD,
                                          auth.scopes.WRITE_UPLOAD])

        # Upload a gzipped tar archive package containing files to delete.
        cwd = os.getcwd()
        testfiles_dir = os.path.join(cwd, 'tests/test_files_upload')
        filepath = os.path.join(testfiles_dir, 'UploadWithANCDirectory.tar.gz')

        # Prepare gzipped tar submission for upload
        filename = os.path.basename(filepath)

        # Upload files to delete
        response = self.client.post('/filemanager/api/',
                                    data={
                                        'file': (open(filepath, 'rb'), filename),
                                    },
                                    headers={'Authorization': token},
                                    #        content_type='application/gzip')
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, 201, "Accepted and processed uploaded Submission Contents")

        # This upload should work but we'll check the response anyway
        with open('schema/resources/uploadResult.json') as f:
            schema = json.load(f)

        try:
            jsonschema.validate(json.loads(response.data), schema)
        except jsonschema.exceptions.SchemaError as e:
            self.fail(e)

        upload_data: Dict[str, Any] = json.loads(response.data)

        # Delete the workspace

        # Create admin token for deleting upload workspace

        admin_token = generate_token(
            self.app,
            [auth.scopes.READ_UPLOAD.as_global(),
             auth.scopes.WRITE_UPLOAD.as_global(),
             auth.scopes.DELETE_UPLOAD_WORKSPACE.as_global()]
        )

        response = self.client.delete(f"/filemanager/api/{upload_data['upload_id']}",
                                      headers={'Authorization': admin_token}
                                      )

        # print("Delete Response:\n" + str(response.data) + '\n')

        self.assertEqual(response.status_code, 200, "Delete workspace.")

        # Let's try to delete the same workspace again

        response = self.client.delete(f"/filemanager/api/{upload_data['upload_id']}",
                                      headers={'Authorization': admin_token}
                                      )
        print("Delete Response:\n" + str(response.data) + '\n')

        self.assertEqual(response.status_code, 404, "Delete non-existent workspace.")

        # Try and delete a non-sense upload_id
        response = self.client.delete(f"/filemanager/api/34+14",
                                      headers={'Authorization': admin_token}
                                      )

        self.assertEqual(response.status_code, 404, "Delete workspace using bogus upload_id.")

        # Try and delete a non-sense upload_id
        response = self.client.delete(f"/filemanager/api/../../etc/passwd",
                                      headers={'Authorization': admin_token}
                                      )

        self.assertEqual(response.status_code, 404, "Delete workspace using bogus upload_id.")

        # TODO: Need to add more tests for auth/z for submitter and admin


    def test_lock_unlock(self) -> None:
        """Test workspace lock and unlock requests.

        Locking workspace prevents updates to workspace.

        Returns
        -------

        """
        # Create a token for writing to upload workspace
        token = generate_token(self.app, [auth.scopes.READ_UPLOAD,
                                          auth.scopes.WRITE_UPLOAD])
        cwd = os.getcwd()
        testfiles_dir = os.path.join(cwd, 'tests/test_files_upload')
        filepath = os.path.join(testfiles_dir, '1801.03879-1.tar.gz')

        # Prepare gzipped tar submission for upload
        filename = os.path.basename(filepath)

        # Post a test submission to upload API

        response = self.client.post('/filemanager/api/',
                                    data={
                                        # 'file': (io.BytesIO(b"abcdef"), 'test.jpg'),
                                        #      'file': (open(filepath, 'rb'), 'test.tar.gz'),
                                        'file': (open(filepath, 'rb'), filename),
                                    },
                                    headers={'Authorization': token},
                                    #        content_type='application/gzip')
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, 201, "Processed uploaded Submission Contents")

        # Extract response into dictionary
        upload_data: Dict[str, Any] = json.loads(response.data)

        # Create admin token for deleting upload workspace
        admin_token = generate_token(self.app, [auth.scopes.READ_UPLOAD,
                                                auth.scopes.WRITE_UPLOAD,
                                                auth.scopes.DELETE_UPLOAD_WORKSPACE.as_global()])
        # Now test lock
        response = self.client.post(f"/filemanager/api/{upload_data['upload_id']}/lock",
                                    headers={'Authorization': admin_token}
                                    )
        self.assertEqual(response.status_code, 200, f"Lock workspace '{upload_data['upload_id']}'.")

        print("Lock:\n" + str(response.data) + '\n')

        # Try to perform actions on locked upload workspace
        response = self.client.post(f"/filemanager/api/{upload_data['upload_id']}",
                                    data={
                                        'file': (open(filepath, 'rb'), filename),
                                    },
                                    headers={'Authorization': token},
                                    #        content_type='application/gzip')
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, 403, "Upload files to locked workspace.")
        print("Upload files to locked workspace:\n" + str(response.data) + '\n')

        # Try to perform actions on locked upload workspace
        response = self.client.get(f"/filemanager/api/{upload_data['upload_id']}",
                                   headers={'Authorization': token}
                                   )

        self.assertEqual(response.status_code, 200, "Request upload summary on locked workspace (OK)")

        public_file_path = 'somefile'
        response = self.client.delete(f"/filemanager/api/{upload_data['upload_id']}/{public_file_path}",
                                      headers={'Authorization': token})
        print(f"Delete File Response(locked):'{public_file_path}'\n" + str(response.data) + '\n')
        self.assertEqual(response.status_code, 403,
                         "Delete an individual file: '{public_file_path}' from locked workspace.")

        # Delete all files in my workspace (normal)
        response = self.client.post(f"/filemanager/api/{upload_data['upload_id']}/delete_all",
                                    headers={'Authorization': token},
                                    content_type='multipart/form-data')
        print("Delete All Files Response(locked):\n" + str(response.data) + '\n')
        self.assertEqual(response.status_code, 403, "Delete all user-uploaded "
                                                    "files from locked workspace.")

        # Now test unlock
        response = self.client.post(f"/filemanager/api/{upload_data['upload_id']}/unlock",
                                    headers={'Authorization': admin_token}
                                    )
        self.assertEqual(response.status_code, 200, f"Unlock workspace '{upload_data['upload_id']}'.")

        print("Unlock:\n" + str(response.data) + '\n')

        # Try request that failed while upload workspace was locked
        response = self.client.post(f"/filemanager/api/{upload_data['upload_id']}/delete_all",
                                    headers={'Authorization': token},
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, 200, "Delete all user-uploaded "
                                                    "files from locked workspace.")

        # Clean up after ourselves

        response = self.client.delete(f"/filemanager/api/{upload_data['upload_id']}",
                                      headers={'Authorization': admin_token}
                                      )

        self.assertEqual(response.status_code, 200, "Accepted request to delete workspace.")

        # Done test

    def test_release_unrelease(self) -> None:
        """Test workspace release and unrelease requests.

        Releasing workspace allows system to clean up workspace files.

        Returns
        -------

        """

        # Create a token for writing to upload workspace
        token = generate_token(self.app, [auth.scopes.READ_UPLOAD,
                                          auth.scopes.WRITE_UPLOAD])
        cwd = os.getcwd()
        testfiles_dir = os.path.join(cwd, 'tests/test_files_upload')
        filepath = os.path.join(testfiles_dir, '1801.03879-1.tar.gz')

        # Prepare gzipped tar submission for upload
        filename = os.path.basename(filepath)

        # Post a test submission to upload API
        response = self.client.post('/filemanager/api/',
                                    data={
                                        'file': (open(filepath, 'rb'), filename),
                                    },
                                    headers={'Authorization': token},
                                    #        content_type='application/gzip')
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, 201, "Processed uploaded Submission Contents")

        # Extract response into dictionary
        upload_data: Dict[str, Any] = json.loads(response.data)

        # Create admin token for releasing upload workspace
        admin_token = generate_token(self.app, [auth.scopes.READ_UPLOAD,
                                                auth.scopes.WRITE_UPLOAD,
                                                auth.scopes.DELETE_UPLOAD_WORKSPACE.as_global()])
        # Now test release
        response = self.client.post(f"/filemanager/api/{upload_data['upload_id']}/release",
                                    headers={'Authorization': admin_token}
                                    )
        self.assertEqual(response.status_code, 200, f"Release workspace '{upload_data['upload_id']}'.")

        print("Release:\n" + str(response.data) + '\n')

        # Repeat tests

        # Try to perform actions on released upload workspace
        response = self.client.post(f"/filemanager/api/{upload_data['upload_id']}",
                                    data={
                                        'file': (open(filepath, 'rb'), filename),
                                    },
                                    headers={'Authorization': token},
                                    #        content_type='application/gzip')
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, 403, "Processed uploaded Submission Contents")

        #

        # Try to perform actions on locked upload workspace
        response = self.client.post(f"/filemanager/api/{upload_data['upload_id']}",
                                    data={
                                        'file': (open(filepath, 'rb'), filename),
                                    },
                                    headers={'Authorization': token},
                                    #        content_type='application/gzip')
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, 403, "Upload files to released workspace.")
        print("Upload files to released workspace:\n" + str(response.data) + '\n')

        # Try to perform actions on locked upload workspace
        response = self.client.get(f"/filemanager/api/{upload_data['upload_id']}",
                                   headers={'Authorization': token}
                                   )

        self.assertEqual(response.status_code, 200, "Request upload summary from released workspace (OK)")

        public_file_path = 'somefile'
        response = self.client.delete(f"/filemanager/api/{upload_data['upload_id']}/{public_file_path}",
                                      headers={'Authorization': token})
        print(f"Delete File from released workspace Response:'{public_file_path}'\n" + str(response.data) + '\n')
        self.assertEqual(response.status_code, 403,
                         "Delete an individual file: '{public_file_path}' from released workspace.")

        # Delete all files in my workspace (normal)
        response = self.client.post(f"/filemanager/api/{upload_data['upload_id']}/delete_all",
                                    headers={'Authorization': token},
                                    content_type='multipart/form-data')
        print("Delete All Files Response(released):\n" + str(response.data) + '\n')
        self.assertEqual(response.status_code, 403, "Delete all user-uploaded "
                                                    "files from released workspace.")

        #

        # Now test unrelease
        response = self.client.post(f"/filemanager/api/{upload_data['upload_id']}/unrelease",
                                    headers={'Authorization': admin_token}
                                    )
        self.assertEqual(response.status_code, 200, f"Unrelease workspace '{upload_data['upload_id']}'.")

        print("Unrelease:\n" + str(response.data) + '\n')

        # Try request that failed while upload workspace was released
        response = self.client.post(f"/filemanager/api/{upload_data['upload_id']}/delete_all",
                                    headers={'Authorization': token},
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, 200, "Delete all user-uploaded "
                                                    "files from released workspace.")

        # Clean up after ourselves

        response = self.client.delete(f"/filemanager/api/{upload_data['upload_id']}",
                                      headers={'Authorization': admin_token}
                                      )

        self.assertEqual(response.status_code, 200, "Accepted request to delete workspace.")

        # Done test


    def test_missing_bbl_upload(self) -> None:
        """
        This test exercises missing references (.bib/.bbl) logic.

        :return:
        """
        cwd = os.getcwd()
        testfiles_dir = os.path.join(cwd, 'tests/test_files_upload')



        # Create a token for writing to upload workspace
        token = generate_token(self.app, [auth.scopes.READ_UPLOAD,
                                          auth.scopes.WRITE_UPLOAD,
                                          auth.scopes.DELETE_UPLOAD_FILE])

        # Replicate bib/bbl upload behavior

        # Lets upload submission that is missing required .bbl file.

        filepath1 = os.path.join(testfiles_dir, 'bad_bib_but_no_bbl.tar')
        filename1 = os.path.basename(filepath1)
        response = self.client.post('/filemanager/api/',
                                    data={
                                        # 'file': (io.BytesIO(b"abcdef"), 'test.jpg'),
                                        'file': (open(filepath1, 'rb'), filename1),
                                    },
                                    headers={'Authorization': token},
                                    #        content_type='application/gzip')
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, 201, "Accepted and processed uploaded Submission Contents")
        self.maxDiff = None

        with open('schema/resources/uploadResult.json') as f:
            result_schema = json.load(f)

        try:
            jsonschema.validate(json.loads(response.data), result_schema)
        except jsonschema.exceptions.SchemaError as e:
            self.fail(e)

        # IMPORTANT: upload_status of 'ERRORS' should stop submission from
        # proceeding until missing .bbl is provided OR .bib is removed.

        upload_data: Dict[str, Any] = json.loads(response.data)
        self.assertIn('upload_status', upload_data, "Returns total upload status.")
        self.assertEqual(upload_data['upload_status'], "ERRORS",
                         ("Expected total upload size matches "
                         f"(ID: {upload_data['upload_id']})"))

        # Get upload_id from previous file upload
        test_id = upload_data['upload_id']
        # Upload missing .bbl
        filepath = os.path.join(testfiles_dir, 'final.bbl')
        filename = os.path.basename(filepath)
        response = self.client.post(f"/filemanager/api/{upload_data['upload_id']}",
                                    data={
                                        # 'file': (io.BytesIO(b"abcdef"), 'test.jpg'),
                                        'file': (open(filepath, 'rb'), filename),
                                    },
                                    headers={'Authorization': token},
                                    #        content_type='application/gzip')
                                    content_type='multipart/form-data')

        # Check response and extract upload_id from response
        self.assertEqual(response.status_code, 201, "Accepted and processed uploaded Submission Contents")

        self.maxDiff = None

        try:
            jsonschema.validate(json.loads(response.data), result_schema)
        except jsonschema.exceptions.SchemaError as e:
            self.fail(e)

        # IMPORTANT: After we upload compiled .bbl file 'update_status' changes
        # from ERRORS to READY_WITH_WARNINGS.
        upload_data: Dict[str, Any] = json.loads(response.data)
        self.assertIn('upload_status', upload_data, "Returns total upload status.")
        self.assertEqual(upload_data['upload_status'], "READY_WITH_WARNINGS",
                         "Expected total upload size matches")

        # Finally, Delete the workspace

        # Create admin token for deleting upload workspace
        admin_token = generate_token(self.app, [auth.scopes.READ_UPLOAD,
                                                auth.scopes.WRITE_UPLOAD,
                                                auth.scopes.DELETE_UPLOAD_WORKSPACE.as_global()])

        response = self.client.delete(f"/filemanager/api/{test_id}",
                                      headers={'Authorization': admin_token}
                                      )
    def search_errors(self, mstring: str, mtype:str, filename: str, error_list: list) -> bool:
        """
        Search for specific warning in errors.
        :return:
        """
        for error in error_list:
            type, filepath, message = error
            #print(f"Look for error '{mstring}' in \n\t'{message}'")
            if re.search(mstring, message):
                found = True

                if mtype and mtype != type:
                    found = False

                if filename and filename != filepath:
                    found = False

                if found is True:
                    return True

        return False

    def search_files(self, filename: str, files: list) -> bool:
        """
        Check if specific file is in list.
        :param filename:
        :param files:
        :return:
        """
        for file in files:
            mod, name, path, size, type = file
            if filename == name:
                return True
        return False


    def test_warnings_and_errors(self) -> None:
        """

        This test currently exercises warnings and errors logic.

        :return:
        """
        cwd = os.getcwd()
        testfiles_dir = os.path.join(cwd, 'tests/test_files_upload')



        # Create a token for writing to upload workspace
        token = generate_token(self.app, [auth.scopes.READ_UPLOAD,
                                          auth.scopes.WRITE_UPLOAD,
                                          auth.scopes.DELETE_UPLOAD_FILE])

        # Trying to replicate bib/bbl upload behavior
        # Lets upload a file before uploading the zero length file

        filepath1 = os.path.join(testfiles_dir, 'UploadRemoveFiles.tar')
        filename1 = os.path.basename(filepath1)
        response = self.client.post('/filemanager/api/',
                                    data={
                                        # 'file': (io.BytesIO(b"abcdef"), 'test.jpg'),
                                        'file': (open(filepath1, 'rb'), filename1),
                                    },
                                    headers={'Authorization': token},
                                    #        content_type='application/gzip')
                                    content_type='multipart/form-data')

        #print("Upload Response:\n" + str(response.data) + "\nEnd Data")
        #print(json.dumps(json.loads(response.data), indent=4, sort_keys=True))

        self.assertEqual(response.status_code, 201, "Accepted and processed uploaded Submission Contents")
        self.maxDiff = None

        with open('schema/resources/uploadResult.json') as f:
            result_schema = json.load(f)

        try:
            jsonschema.validate(json.loads(response.data), result_schema)
        except jsonschema.exceptions.SchemaError as e:
            self.fail(e)

        # IMPORTANT RESULT upload_status of ERRORS should stop submission from
        # proceeding until missing .bbl is provided OR .bib is removed.
        upload_data: Dict[str, Any] = json.loads(response.data)
        self.assertIn('upload_status', upload_data, "Returns total upload status.")
        self.assertEqual(upload_data['upload_status'], "ERRORS",
                         "Expected total upload size matches")

        # Make sure we are seeing errors
        self.assertTrue(self.search_errors("Removed file 'remove.desc' \[File not allowed].",
                                           "warn", "remove.desc",
                                           upload_data['errors']), "Expect this error to occur.")

        self.assertFalse(self.search_files('remove.desc', upload_data['files']), "File was removed")

        self.assertTrue(self.search_errors("Removed file '.junk' \[File not allowed]",
                                           "warn", ".junk",
                                           upload_data['errors']), "Expect this error to occur.")

        self.assertTrue(self.search_errors("Removed the file 'core' \[File not allowed].",
                                           "warn", "core",
                                           upload_data['errors']), "Expect this error to occur.")

        self.assertTrue(self.search_errors("REMOVING standard style files for Paul",
                                           "warn", "diagrams.sty",
                                           upload_data['errors']), "Expect this error to occur.")

        self.assertTrue(self.search_errors("File 'zero.txt' is empty \(size is zero\)",
                                           "warn", "zero.txt",
                                           upload_data['errors']), "Expect this error to occur.")

        self.assertTrue(self.search_errors("Removed file 'xxx.cshrc' \[File not allowed].",
                                           "warn", "",
                                           upload_data['errors']), "Expect this error to occur.")

        self.assertTrue(self.search_errors("Removed the file 'uufiles' \[File not allowed].",
                                           "warn", "uufiles",
                                           upload_data['errors']), "Expect this error to occur.")

        self.assertTrue(self.search_errors("Removed file 'xxx.cshrc' \[File not allowed].",
                                           "warn", "xxx.cshrc",
                                           upload_data['errors']), "Expect this error to occur.")

        self.assertTrue(self.search_errors("Removed file 'final.aux' due to name conflict",
                                           "warn", "final.aux",
                                           upload_data['errors']), "Expect this error to occur.")

        self.assertTrue(self.search_errors("We do not run bibtex in the auto",
                                           "warn", "final.bib",
                                           upload_data['errors']), "Expect this error to occur.")

        self.assertTrue(self.search_errors("Removed the file 'final.bib'. Using 'final.bbl' for references.",
                                           "warn", "final.bib",
                                           upload_data['errors']), "Expect this error to occur.")

        self.assertTrue(self.search_errors("Removing file 'aa.dem' on the assumption that it is the example "
                                           + "file for the Astronomy and Astrophysics macro package aa.cls.",
                                           "warn", "aa.dem",
                                           upload_data['errors']), "Expect this error to occur.")

        self.assertTrue(self.search_errors("Removed file 'aa.dem'.",
                                           "warn", "aa.dem",
                                           upload_data['errors']), "Expect this error to occur.")

        self.assertTrue(self.search_errors("WILL REMOVE standard revtex4 style",
                                           "warn", "revtex4.cls",
                                           upload_data['errors']), "Expect this error to occur.")

        self.assertTrue(self.search_errors("Found hyperlink-compatible package 'espcrc2.sty'.",
                                           "warn", "espcrc2.sty",
                                           upload_data['errors']), "Expect this error to occur.")

        self.assertTrue(self.search_errors("Your submission has been rejected because",
                                           "fatal", "something.doc",
                                           upload_data['errors']), "Expect this error to occur.")

        self.assertTrue(self.search_errors("Removed file 'final.synctex'.",
                                           "warn", "final.synctex",
                                           upload_data['errors']), "Expect this error to occur.")

        self.assertTrue(self.search_errors("Removed file 'final.out' due to name conflict.",
                                           "warn", "final.out",
                                           upload_data['errors']), "Expect this error to occur.")

        # Uploaded DOC file is causing fatal error
        filepath2 = os.path.join(testfiles_dir, 'README.md')
        filename2 = os.path.basename(filepath2)
        filename2 = '00README.XXX'
        response = self.client.post(f"/filemanager/api/{upload_data['upload_id']}",
                                    data={
                                        # 'file': (io.BytesIO(b"abcdef"), 'test.jpg'),
                                        'file': (open(filepath2, 'rb'), filename2),
                                    },
                                    headers={'Authorization': token},
                                    #        content_type='application/gzip')
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, 201, "Accepted and processed uploaded Submission Contents")

        try:
            jsonschema.validate(json.loads(response.data), result_schema)
        except jsonschema.exceptions.SchemaError as e:
            self.fail(e)

        upload_data: Dict[str, Any] = json.loads(response.data)

        amsg = ("Status returned to 'READY'."
                " Removed file causing fatal error."
                f" (ID:{upload_data['upload_id']})")
        self.assertEqual(upload_data['upload_status'], "READY", amsg)

        # Upload files that we will warn about - but not remove.

        filepath2 = os.path.join(testfiles_dir, 'FilesToWarnAbout.tar')
        filename2 = os.path.basename(filepath2)
        response = self.client.post(f"/filemanager/api/{upload_data['upload_id']}",
                                    data={
                                        # 'file': (io.BytesIO(b"abcdef"), 'test.jpg'),
                                        'file': (open(filepath2, 'rb'), filename2),
                                    },
                                    headers={'Authorization': token},
                                    #        content_type='application/gzip')
                                    content_type='multipart/form-data')

        #print("AFTER UPLOAD FILES TO WARN ON")
        #print(json.dumps(json.loads(response.data), indent=4, sort_keys=True))

        upload_data: Dict[str, Any] = json.loads(response.data)

        # Normal emacs backup file
        self.assertTrue(self.search_errors("File 'submission.tex~' may be a backup file. "\
                                           "Please inspect and remove extraneous backup files.",
                                           "warn", "submission.tex_",
                                           upload_data['errors']), "Expect this error to occur.")

        # Optional, we translate tilde to underscore thus this file appears. Leave just in case.
        self.assertTrue(self.search_errors("File 'submission.tex_' may be a backup file. " \
                                           "Please inspect and remove extraneous backup files.",
                                           "warn", "submission.tex_",
                                           upload_data['errors']), "Expect this error to occur.")

        # Detect renaming of filename with tilde - since we loose original file name
        self.assertTrue(self.search_errors("Attempting to rename submission.tex~ to submission.tex_.",
                                           "warn", "submission.tex_",
                                           upload_data['errors']), "Expect this error to occur.")

        # Another backup file
        self.assertTrue(self.search_errors("File 'submission.tex.bak' may be a backup file. "\
                                           "Please inspect and remove extraneous backup files.",
                                           "warn", "submission.tex.bak",
                                           upload_data['errors']), "Expect this error to occur.")

        # Delete the workspace
        # Create admin token for deleting upload workspace
        admin_token = generate_token(self.app, [auth.scopes.READ_UPLOAD,
                                                auth.scopes.WRITE_UPLOAD,
                                                auth.scopes.DELETE_UPLOAD_WORKSPACE.as_global()])

        response = self.client.delete(f"/filemanager/api/{upload_data['upload_id']}",
                                      headers={'Authorization': admin_token}
                                      )

        # This cleans out the workspace. Comment out if you want to inspect files
        # in workspace. Source log is saved to 'deleted_workspace_logs' directory.
        self.assertEqual(response.status_code, 200, "Accepted request to delete workspace.")


    def test_eps_repair(self) -> None:
        """
        This test is intended to be manually edited for debugging purposes.

        This test currently exercises missing .bbl logic.

        :return:
        """
        cwd = os.getcwd()
        testfiles_dir = os.path.join(cwd, 'tests/test_files_strip_postscript')



        # Create a token for writing to upload workspace
        token = generate_token(self.app, [auth.scopes.READ_UPLOAD,
                                          auth.scopes.WRITE_UPLOAD,
                                          auth.scopes.DELETE_UPLOAD_FILE])

        # Trying to replicate bib/bbl upload behavior
        # Lets upload a file before uploading the zero length file
        test_filename = 'dos_eps_1.eps'
        filepath1 = os.path.join(testfiles_dir, test_filename)
        filename1 = os.path.basename(filepath1)
        response = self.client.post('/filemanager/api/',
                                    data={
                                        # 'file': (io.BytesIO(b"abcdef"), 'test.jpg'),
                                        'file': (open(filepath1, 'rb'), filename1),
                                    },
                                    headers={'Authorization': token},
                                    #        content_type='application/gzip')
                                    content_type='multipart/form-data')

        #print("Upload Response:\n" + str(response.data) + "\nEnd Data")
        #print(json.dumps(json.loads(response.data), indent=4, sort_keys=True))

        self.assertEqual(response.status_code, 201, "Accepted and processed uploaded Submission Contents")
        self.maxDiff = None

        with open('schema/resources/uploadResult.json') as f:
            result_schema = json.load(f)

        try:
            jsonschema.validate(json.loads(response.data), result_schema)
        except jsonschema.exceptions.SchemaError as e:
            self.fail(e)

        # IMPORTANT RESULT upload_status of ERRORS should stop submission from
        # proceeding until missing .bbl is provided OR .bib is removed.
        upload_data: Dict[str, Any] = json.loads(response.data)
        self.assertIn('upload_status', upload_data, "Returns total upload status.")
        self.assertEqual(upload_data['upload_status'], "READY_WITH_WARNINGS",
                         "Expect warnings from stripping TIFF from EPS file.")

        # Make sure we are seeing errors
        self.assertTrue(self.search_errors("leading TIFF preview stripped",
                                           "warn", test_filename,
                                           upload_data['errors']), "Expect this error to occur.")

        # Now let's grab file content and verify that it matches expected
        # reference_path file.

        # Check if content file exists
        response = self.client.head(
            f"/filemanager/api/{upload_data['upload_id']}/{test_filename}/content",
            headers={'Authorization': token}
        )
        self.assertEqual(response.status_code, status.OK)
        self.assertIn('ETag', response.headers, "Returns an ETag header")

        # Download content file
        response = self.client.get(
            f"/filemanager/api/{upload_data['upload_id']}/{test_filename}/content",
            headers={'Authorization': token}
        )
        self.assertEqual(response.status_code, status.OK)
        self.assertIn('ETag', response.headers, "Returns an ETag header")

        workdir = tempfile.mkdtemp()

        # Write out file (to save temporary directory where we saved source_log)
        content_file_path = os.path.join(workdir, test_filename)
        fileH = open(content_file_path, 'wb')
        fileH.write(response.data)
        fileH.close()

        # Compare downloaded file (content_file_path) against reference_path file
        reference_filename = 'dos_eps_1_stripped.eps'
        reference_path = os.path.join(TEST_FILES_STRIP_PS, reference_filename)
        # Compared fixed file to a reference_path stripped version of file.
        is_same = filecmp.cmp(content_file_path, reference_path, shallow=False)
        self.assertTrue(is_same,
                        f"Repair Encapsulated Postscript file '{test_filename}'.")

        # Try encapsulate Postscript with trailing TIFF

        # Trying to replicate bib/bbl upload behavior
        # Lets upload a file before uploading the zero length file
        test_filename = 'dos_eps_2.eps'
        filepath1 = os.path.join(testfiles_dir, test_filename)
        filename1 = os.path.basename(filepath1)
        response = self.client.post(f"/filemanager/api/{upload_data['upload_id']}",
                                    data={
                                        # 'file': (io.BytesIO(b"abcdef"), 'test.jpg'),
                                        'file': (open(filepath1, 'rb'), filename1),
                                    },
                                    headers={'Authorization': token},
                                    #        content_type='application/gzip')
                                    content_type='multipart/form-data')

        # print("Upload Response:\n" + str(response.data) + "\nEnd Data")
        # print(json.dumps(json.loads(response.data), indent=4, sort_keys=True))

        self.assertEqual(response.status_code, 201, "Accepted and processed uploaded Submission Contents")
        self.maxDiff = None

        with open('schema/resources/uploadResult.json') as f:
            result_schema = json.load(f)

        try:
            jsonschema.validate(json.loads(response.data), result_schema)
        except jsonschema.exceptions.SchemaError as e:
            self.fail(e)

        # IMPORTANT RESULT upload_status of ERRORS should stop submission from
        # proceeding until missing .bbl is provided OR .bib is removed.
        upload_data: Dict[str, Any] = json.loads(response.data)
        self.assertIn('upload_status', upload_data, "Returns total upload status.")
        self.assertEqual(upload_data['upload_status'], "READY_WITH_WARNINGS",
                         "Expect warnings from stripping TIFF from EPS file.")

        # Make sure we are seeing errors
        self.assertTrue(self.search_errors("trailing TIFF preview stripped",
                                           "warn", test_filename,
                                           upload_data['errors']), "Expect this error to occur.")

        # Check if content file exists
        response = self.client.head(
            f"/filemanager/api/{upload_data['upload_id']}/{test_filename}/content",
            headers={'Authorization': token}
        )
        self.assertEqual(response.status_code, status.OK)
        self.assertIn('ETag', response.headers, "Returns an ETag header")

        # Download content file
        response = self.client.get(
            f"/filemanager/api/{upload_data['upload_id']}/{test_filename}/content",
            headers={'Authorization': token}
        )
        self.assertEqual(response.status_code, status.OK)
        self.assertIn('ETag', response.headers, "Returns an ETag header")

        workdir = tempfile.mkdtemp()

        # Write out file (to save temporary directory where we saved source_log)
        content_file_path = os.path.join(workdir, test_filename)
        fileH = open(content_file_path, 'wb')
        fileH.write(response.data)
        fileH.close()

        # Compare downloaded file (content_file_path) against reference_path file
        reference_filename = 'dos_eps_2_stripped.eps'
        reference_path = os.path.join(TEST_FILES_STRIP_PS, reference_filename)
        # Compared fixed file to a reference_path stripped version of file.
        is_same = filecmp.cmp(content_file_path, reference_path, shallow=False)
        self.assertTrue(is_same,
                        f"Repair Encapsulated Postscript file '{test_filename}'.")

        # Delete the workspace
        # Create admin token for deleting upload workspace
        admin_token = generate_token(self.app, [auth.scopes.READ_UPLOAD,
                                                auth.scopes.WRITE_UPLOAD,
                                                auth.scopes.DELETE_UPLOAD_WORKSPACE.as_global()])

        response = self.client.delete(f"/filemanager/api/{upload_data['upload_id']}",
                                      headers={'Authorization': admin_token}
                                      )

        # This cleans out the workspace. Comment out if you want to inspect files
        # in workspace. Source log is saved to 'deleted_workspace_logs' directory.
        self.assertEqual(response.status_code, 200, "Accepted request to delete workspace.")

    def test_checkpoints(self) -> None:
        """
        Test various checkpoint functions.

        Returns
        -------

        """
        cwd = os.getcwd()
        testfiles_dir = os.path.join(cwd, 'tests/test_files_upload')

        # Create a token for writing to upload workspace
        token = generate_token(self.app, [auth.scopes.READ_UPLOAD,
                                          auth.scopes.WRITE_UPLOAD,
                                          auth.scopes.DELETE_UPLOAD_FILE])

        # Create a token with checkpoint scopes with upload read/write scopes
        checkpoint_token = generate_token(self.app,
                                          [auth.scopes.READ_UPLOAD,
                                           auth.scopes.WRITE_UPLOAD,
                                           auth.scopes.DELETE_UPLOAD_FILE,
                                           auth.scopes.CREATE_UPLOAD_CHECKPOINT,
                                           auth.scopes.READ_UPLOAD_CHECKPOINT,
                                           auth.scopes.DELETE_UPLOAD_CHECKPOINT,
                                           auth.scopes.RESTORE_UPLOAD_CHECKPOINT
                                           ])

        # TEST INDEPENDENT CHECKPOINT REQUESTS (checkpoint/list_checkpoints/
        #       delete_checkpoint/delete_all_checkpoints/restore_checkpoint)

        # Upload tests files
        filepath1 = os.path.join(testfiles_dir, 'UnpackWithSubdirectories.tar.gz')
        filename1 = os.path.basename(filepath1)
        response = self.client.post('/filemanager/api/',
                                    data={
                                        # 'file': (io.BytesIO(b"abcdef"), 'test.jpg'),
                                        'file': (open(filepath1, 'rb'), filename1),
                                    },
                                    headers={'Authorization': token},
                                    #        content_type='application/gzip')
                                    content_type='multipart/form-data')

        with open('schema/resources/uploadResult.json') as f:
            result_schema = json.load(f)

        try:
            jsonschema.validate(json.loads(response.data), result_schema)
        except jsonschema.exceptions.SchemaError as e:
            self.fail(e)

        upload_data: Dict[str, Any] = json.loads(response.data)

        response = self.client.post(f"/filemanager/api/{upload_data['upload_id']}/checkpoint",
                                   headers={'Authorization': token},
                                   #        content_type='application/gzip')
                                   content_type='multipart/form-data')

        self.assertEqual(response.status_code, status.FORBIDDEN)

        # Try with correct token with checkpoint scopes
        response = self.client.post(f"/filemanager/api/{upload_data['upload_id']}/checkpoint",
                                    headers={'Authorization': checkpoint_token},
                                    #        content_type='application/gzip')
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, status.OK)


        # Upload different set of files - checkpoint

        # Delete all files in my workspace (normal)
        response = self.client.post(f"/filemanager/api/{upload_data['upload_id']}/delete_all",
                                    headers={'Authorization': token},
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, 200, "Delete all user-uploaded files.")

        # Upload tests files
        filepath1 = os.path.join(testfiles_dir, 'upload2.tar.gz')
        filename1 = os.path.basename(filepath1)
        response = self.client.post(f"/filemanager/api/{upload_data['upload_id']}",
                                    data={
                                        # 'file': (io.BytesIO(b"abcdef"), 'test.jpg'),
                                        'file': (open(filepath1, 'rb'), filename1),
                                    },
                                    headers={'Authorization': token},
                                    #        content_type='application/gzip')
                                    content_type='multipart/form-data')
        self.assertEqual(response.status_code, 201,
                         "Accepted and processed uploaded Submission Contents")

        with open('schema/resources/uploadResult.json') as f:
            result_schema = json.load(f)

        try:
            jsonschema.validate(json.loads(response.data), result_schema)
        except jsonschema.exceptions.SchemaError as e:
            self.fail(e)

        upload_data: Dict[str, Any] = json.loads(response.data)

        response = self.client.post(f"/filemanager/api/{upload_data['upload_id']}/checkpoint",
                                    headers={'Authorization': checkpoint_token},
                                    #        content_type='application/gzip')
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, status.OK)

        # End second upload

        # Create unecessary checkpoint

        response = self.client.post(f"/filemanager/api/{upload_data['upload_id']}/checkpoint",
                                    headers={'Authorization': checkpoint_token},
                                    #        content_type='application/gzip')
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, status.OK)

        # List checkpoints
        response = self.client.get(f"/filemanager/api/{upload_data['upload_id']}/list_checkpoints",
                                    headers={'Authorization': checkpoint_token},
                                    #        content_type='application/gzip')
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, status.OK)

        print("ListCheckpoints Response:\n")
        print(json.dumps(json.loads(response.data), indent=4, sort_keys=True))

        upload_data: Dict[str, Any] = json.loads(response.data)

        checkpoints = upload_data['checkpoints']

        self.assertEqual(len(checkpoints), 3, "So far we've created three checkpoints.")

        # Locate the first checkpoint
        for item in checkpoints:
            if item['name'] == "checkpoint_1_theuser.tar.gz":
                checkpoint_checksum = item['checksum']

        # checkpoint_checksum = checkpoints[0]['checksum']
        print(f"checkpoint to restore: {checkpoint_checksum}")


        # Restore checkpoints
        response = self.client.get(f"/filemanager/api/{upload_data['upload_id']}/"
                                   f"restore_checkpoint/{checkpoint_checksum}",
                                   headers={'Authorization': checkpoint_token},
                                   content_type='multipart/form-data')

        self.assertEqual(response.status_code, status.OK)

        print(f"RestoreCheckpoint:{checkpoint_checksum} Response:\n")
        print(json.dumps(json.loads(response.data), indent=4, sort_keys=True))

        # Check if known checkpoint exists
        response = self.client.head(
            f"/filemanager/api/{upload_data['upload_id']}/checkpoint/{checkpoint_checksum}",
            headers={'Authorization': checkpoint_token}
        )
        self.assertEqual(response.status_code, status.OK)
        self.assertIn('ETag', response.headers, "Returns an ETag header")

        # Check whether bad/invalid checkpoint exists
        response = self.client.head(
            f"/filemanager/api/{upload_data['upload_id']}/checkpoint/0981354098324",
            headers={'Authorization': checkpoint_token}
        )
        self.assertEqual(response.status_code, status.NOT_FOUND)

        # Download content
        response = self.client.get(
            f"/filemanager/api/{upload_data['upload_id']}/checkpoint/{checkpoint_checksum}",
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
        checkpoint_checksum_dict = {}
        for root_directory, directories, files in os.walk(workdir):
            for file in files:
                path = os.path.join(root_directory, file)
                checkpoint_checksum_dict[file] = checksum(path)
            for dir in directories:
                path = os.path.join(root_directory, dir)
                checkpoint_checksum_dict[dir] = dir

        # Analyze original submission gzipped tar
        workdir_ref = tempfile.mkdtemp()
        filepath_ref = os.path.join(testfiles_dir, 'UnpackWithSubdirectories.tar.gz')

        print(f"Checkpoint files:{workdir} Reference Files:{workdir_ref}\n")

        # unpack the tar file
        UnpackTarFile(filepath_ref, workdir_ref)

        reference_checksum_dict = {}
        for root_directory, directories, files in os.walk(workdir_ref):
            for file in files:
                path = os.path.join(root_directory, file)
                reference_checksum_dict[file] = checksum(path)
            for dir in directories:
                path = os.path.join(root_directory, dir)
                reference_checksum_dict[dir] = dir

        # Create sets containing file/checksum for checkpoint and original test
        # archive
        filesetc = set(checkpoint_checksum_dict.items())
        filesetr = set(reference_checksum_dict.items())

        # Test that checkpoint and submission contain the same files.
        self.assertSetEqual(filesetc, filesetr,
                            "The checkpoint and orginal submission gzipped tar"
                            " files should contain the same files/directories.")


        # Let's delete second checkpoint file
        checkpoint_checksum = checkpoints[1]['checksum']

        # Delete checkpoints
        response = self.client.delete(f"/filemanager/api/{upload_data['upload_id']}/"
                                   f"delete_checkpoint/{checkpoint_checksum}",
                                   headers={'Authorization': checkpoint_token},
                                   content_type='multipart/form-data')
        self.assertEqual(response.status_code, status.OK)

        # List checkpoint to see what we have left
        response = self.client.get(f"/filemanager/api/{upload_data['upload_id']}/list_checkpoints",
                                   headers={'Authorization': checkpoint_token},
                                   #        content_type='application/gzip')
                                   content_type='multipart/form-data')
        self.assertEqual(response.status_code, status.OK)

        upload_data: Dict[str, Any] = json.loads(response.data)
        checkpoints = upload_data['checkpoints']
        self.assertEqual(len(checkpoints), 2, "There are two checkpoints left.")

        # Now let's blow away all checkpoints
        response = self.client.post(f"/filemanager/api/{upload_data['upload_id']}/delete_all_checkpoints",
                                   headers={'Authorization': checkpoint_token},
                                   #        content_type='application/gzip')
                                   content_type='multipart/form-data')
        self.assertEqual(response.status_code, status.OK)

        # List checkpoint to see what we have left after remove all
        response = self.client.get(f"/filemanager/api/{upload_data['upload_id']}/list_checkpoints",
                                   headers={'Authorization': checkpoint_token},
                                   #        content_type='application/gzip')
                                   content_type='multipart/form-data')
        self.assertEqual(response.status_code, status.OK)

        upload_data: Dict[str, Any] = json.loads(response.data)
        checkpoints = upload_data['checkpoints']
        self.assertEqual(len(checkpoints), 0, "All checkpoints have been deleted.")


        # Try to restore a checkpoint that was deleted.
        response = self.client.delete(f"/filemanager/api/{upload_data['upload_id']}/"
                                      f"delete_checkpoint/{checkpoint_checksum}",
                                      headers={'Authorization': checkpoint_token},
                                      content_type='multipart/form-data')

        self.assertEqual(response.status_code, status.NOT_FOUND)

        # Delete the workspace
        # Create admin token for deleting upload workspace
        admin_token = generate_token(self.app, [auth.scopes.READ_UPLOAD,
                                                auth.scopes.WRITE_UPLOAD,
                                                auth.scopes.DELETE_UPLOAD_WORKSPACE.as_global()])

        response = self.client.delete(f"/filemanager/api/{upload_data['upload_id']}",
                                      headers={'Authorization': admin_token}
                                      )

        # This cleans out the workspace. Comment out if you want to inspect files
        # in workspace. Source log is saved to 'deleted_workspace_logs' directory.
        self.assertEqual(response.status_code, 200, "Accepted request to delete workspace.")


        # NOW TEST API LEVEL CHECKPOINT VIA UPLOAD REQUEST

        # Upload tests files
        filepath1 = os.path.join(testfiles_dir, 'UnpackWithSubdirectories.tar.gz')
        filename1 = os.path.basename(filepath1)
        response = self.client.post('/filemanager/api/',
                                    data={
                                        # 'file': (io.BytesIO(b"abcdef"), 'test.jpg'),
                                        'file': (open(filepath1, 'rb'), filename1),
                                    },
                                    headers={'Authorization': token},
                                    #        content_type='application/gzip')
                                    content_type='multipart/form-data')
        self.assertEqual(response.status_code, 201,
                         "Accepted and processed uploaded Submission Contents")

        with open('schema/resources/uploadResult.json') as f:
            result_schema = json.load(f)

        try:
            jsonschema.validate(json.loads(response.data), result_schema)
        except jsonschema.exceptions.SchemaError as e:
            self.fail(e)

        upload_data: Dict[str, Any] = json.loads(response.data)

        # Upload tests files
        filepath1 = os.path.join(testfiles_dir, 'Upload2.tar.gz')
        filename1 = os.path.basename(filepath1)
        response = self.client.post(f"/filemanager/api/{upload_data['upload_id']}/checkpoint_with_upload",
                                    data={
                                        # 'file': (io.BytesIO(b"abcdef"), 'test.jpg'),
                                        'file': (open(filepath1, 'rb'), filename1),
                                    },
                                    headers={'Authorization': checkpoint_token},
                                    #        content_type='application/gzip')
                                    content_type='multipart/form-data')
        self.assertEqual(response.status_code, 201,
                         "Accepted and processed uploaded Submission Contents")

        with open('schema/resources/uploadResult.json') as f:
            result_schema = json.load(f)

        try:
            jsonschema.validate(json.loads(response.data), result_schema)
        except jsonschema.exceptions.SchemaError as e:
            self.fail(e)

        upload_data: Dict[str, Any] = json.loads(response.data)

        # List checkpoint to see what we have left after remove all
        response = self.client.get(f"/filemanager/api/{upload_data['upload_id']}/list_checkpoints",
                                   headers={'Authorization': checkpoint_token},
                                   #        content_type='application/gzip')
                                   content_type='multipart/form-data')
        self.assertEqual(response.status_code, status.OK)

        # Delete the workspace
        # Create admin token for deleting upload workspace
        admin_token = generate_token(self.app, [auth.scopes.READ_UPLOAD,
                                                auth.scopes.WRITE_UPLOAD,
                                                auth.scopes.DELETE_UPLOAD_WORKSPACE.as_global()])

        response = self.client.delete(f"/filemanager/api/{upload_data['upload_id']}",
                                      headers={'Authorization': admin_token}
                                      )

        # This cleans out the workspace. Comment out if you want to inspect files
        # in workspace. Source log is saved to 'deleted_workspace_logs' directory.
        self.assertEqual(response.status_code, 200, "Accepted request to delete workspace.")


    def xxx_test_one_off_situations(self) -> None:
        """
        Test to make sure response contains warnings/errors.
        Returns
        -------

        """
        cwd = os.getcwd()
        testfiles_dir = os.path.join(cwd, 'tests/test_files_upload')

        # Create a token for writing to upload workspace
        token = generate_token(self.app, [auth.scopes.READ_UPLOAD,
                                          auth.scopes.WRITE_UPLOAD,
                                          auth.scopes.DELETE_UPLOAD_FILE])

        # Trying to replicate bib/bbl upload behavior
        # Lets upload a file before uploading the zero length file

        #filepath1 = os.path.join(testfiles_dir, 'UploadRemoveFiles.tar')
        filepath1 = os.path.join(testfiles_dir, 'only_figures_tikz_needs_pdflatx.tar.gz')
        filename1 = os.path.basename(filepath1)
        response = self.client.post('/filemanager/api/',
                                    data={
                                        # 'file': (io.BytesIO(b"abcdef"), 'test.jpg'),
                                        'file': (open(filepath1, 'rb'), filename1),
                                    },
                                    headers={'Authorization': token},
                                    #        content_type='application/gzip')
                                    content_type='multipart/form-data')

        print("Upload Response:\n")
        print(json.dumps(json.loads(response.data), indent=4, sort_keys=True))

        with open('schema/resources/uploadResult.json') as f:
            result_schema = json.load(f)

        try:
            jsonschema.validate(json.loads(response.data), result_schema)
        except jsonschema.exceptions.SchemaError as e:
            self.fail(e)

        upload_data: Dict[str, Any] = json.loads(response.data)

        # Delete the workspace
        # Create admin token for deleting upload workspace
        admin_token = generate_token(self.app, [auth.scopes.READ_UPLOAD,
                                                auth.scopes.WRITE_UPLOAD,
                                                auth.scopes.DELETE_UPLOAD_WORKSPACE.as_global()])

        response = self.client.delete(f"/filemanager/api/{upload_data['upload_id']}",
                                      headers={'Authorization': admin_token}
                                      )

        # This cleans out the workspace. Comment out if you want to inspect files
        # in workspace. Source log is saved to 'deleted_workspace_logs' directory.
        self.assertEqual(response.status_code, 200, "Accepted request to delete workspace.")


    # Upload a submission package and perform normal operations on upload
    def test_upload_files_normal(self) -> None:
        """Test normal well-behaved upload requests.

        This series of tests uploads files with the expectation of success.

        The appropriate tokens are provided to various requests.

        Note: Delete workspace still needs to be implemented.
        """
        with open('schema/resources/uploadResponse.json') as f:
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

        cwd = os.getcwd()
        testfiles_dir = os.path.join(cwd, 'tests/test_files_upload')
        filepath = os.path.join(testfiles_dir, '1801.03879-1.tar.gz')

        # Prepare gzipped tar submission for upload
        filename = os.path.basename(filepath)

        # Post a test submission to upload API

        print(f"Token (for possible use in manual browser tests): {token}\n")

        print("\nMake request to upload gzipped tar file. \n"
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

        self.maxDiff = None

        with open('schema/resources/uploadResult.json') as f:
            result_schema = json.load(f)

        try:
            jsonschema.validate(json.loads(response.data), result_schema)
        except jsonschema.exceptions.SchemaError as e:
            self.fail(e)

        upload_data: Dict[str, Any] = json.loads(response.data)

        # Check that upload_total_size is in summary response
        self.assertIn("upload_total_size", upload_data,
                      "Returns total upload size.")
        self.assertEqual(upload_data["upload_total_size"], 275_781,
                         "Expected total upload size to match"
                         f" (ID:{upload_data['upload_id']}).")

        # Check that upload_compressed_size is in summary response
        self.assertIn("upload_compressed_size", upload_data,
                      "Returns compressed upload size.")
        self.assertLess(upload_data["upload_compressed_size"], 116_000,
                         "Expected total upload size to match"
                         f" (ID:{upload_data['upload_id']}).")

        self.assertEqual(upload_data["source_format"], "tex",
                         "Check source format of TeX submission."
                         f" [ID={upload_data['upload_id']}]")

        # Get summary of upload

        # with open('schema/resources/uploadResult.json') as f:
        #   status_schema = json.load(f)

        response = self.client.get(f"/filemanager/api/{upload_data['upload_id']}",
                                   headers={'Authorization': token})

        self.assertEqual(response.status_code, 200, "File summary.")
        try:
            jsonschema.validate(json.loads(response.data), result_schema)
        except jsonschema.exceptions.SchemaError as e:
            self.fail(e)

        # Check for file in upload result
        summary_data: Dict[str, Any] = json.loads(response.data)
        file_list = summary_data['files']
        found = next((item for item in file_list if item["name"] == "lipics-v2016.cls"), False)
        if next((item for item in file_list if item["name"] == "lipics-v2016.cls"), False):
            print(f"FOUND UPLOADED FILE (Right Answer!): 'lipics-v2016.cls'")
        else:
            print(f"UPLOADED FILE NOT FOUND: 'lipics-v2016.cls' OOPS!")

        self.assertTrue(found, "Uploaded file should exist in resulting file list.")

        # Download content before we start deleting files

        admin_token = generate_token(self.app, [auth.scopes.READ_UPLOAD,
                                                auth.scopes.WRITE_UPLOAD,
                                                auth.scopes.DELETE_UPLOAD_WORKSPACE.as_global()])

        # Check if content exists
        response = self.client.head(
            f"/filemanager/api/{upload_data['upload_id']}/content",
            headers={'Authorization': admin_token}
        )
        self.assertEqual(response.status_code, status.OK)
        self.assertIn('ETag', response.headers, "Returns an ETag header")

        # Download content
        response = self.client.get(
            f"/filemanager/api/{upload_data['upload_id']}/content",
            headers={'Authorization': admin_token}
        )
        self.assertEqual(response.status_code, status.OK)
        self.assertIn('ETag', response.headers, "Returns an ETag header")
        workdir = tempfile.mkdtemp()
        with tarfile.open(fileobj=BytesIO(response.data)) as tar:
            tar.extractall(path=workdir)

        print(f'List directory containing downloaded content: {workdir}\:n')
        print(os.listdir(workdir))
        print(f'End List\n')

        # WARNING: THE TESTS BELOW DELETE INDIVIDUAL FILES AND THEN THE ENTIRE WORKSPACE

        # Delete a file (normal call)
        public_file_path = "lipics-logo-bw.pdf"
        from requests.utils import quote
        encoded_file_path = quote(public_file_path, safe='')

        # response = self.client.delete(f"/filemanager/api/{upload_data['upload_id']}/{encoded_file_path}",
        response = self.client.delete(f"/filemanager/api/{upload_data['upload_id']}/{public_file_path}",
                                      headers={'Authorization': token})

        self.assertEqual(response.status_code, 200, "Delete an individual file.")

        # Delete another file
        public_file_path = "lipics-v2016.cls"
        encoded_file_path = quote(public_file_path, safe='')

        # response = self.client.delete(f"/filemanager/api/{upload_data['upload_id']}/{encoded_file_path}",
        response = self.client.delete(f"/filemanager/api/{upload_data['upload_id']}/{public_file_path}",
                                      headers={'Authorization': token})
        self.assertEqual(response.status_code, 200, "Delete an individual file.")

        # Get summary after deletions
        response = self.client.get(f"/filemanager/api/{upload_data['upload_id']}",
                                   headers={'Authorization': token})

        self.assertEqual(response.status_code, 200, "File summary after deletions.")

        try:
            jsonschema.validate(json.loads(response.data), result_schema)
        except jsonschema.exceptions.SchemaError as e:
            self.fail(e)

        # Check that deleted file is missing from file list summary
        summary_data: Dict[str, Any] = json.loads(response.data)
        file_list = summary_data['files']
        found = next((item for item in file_list if item["name"] == "lipics-v2016.clsXX"), False)
        self.assertFalse(found, "Uploaded file should exist in resulting file list.")

        if next((item for item in file_list if item["name"] == public_file_path), False):
            print(f"FOUND DELETED FILE (Wrong Answer): '{public_file_path}'")
        else:
            print(f"DELETED FILE NOT FOUND (Right Answer!): '{public_file_path}'")

        # Now check to see if size total upload size decreased
        # Get summary and check upload_total_size
        response = self.client.get(f"/filemanager/api/{upload_data['upload_id']}",
                                   headers={'Authorization': token})

        self.assertEqual(response.status_code, 200, "File summary.")
        try:
            jsonschema.validate(json.loads(response.data), result_schema)
        except jsonschema.exceptions.SchemaError as e:
            self.fail(e)
        upload_data: Dict[str, Any] = json.loads(response.data)

        # Check that upload_total_size is in summary response
        self.assertIn('upload_total_size', upload_data, "Returns total upload size.")
        self.assertNotEqual(upload_data['upload_total_size'], 275781,
                            "Expected total upload size should not match "
                            "pre - delete total")
        # upload total size is definitely smaller than original 275781 bytes
        # after we deleted a few files.
        self.assertEqual(upload_data["upload_total_size"], 237_116,
                         "Expected smaller total upload size.")
        self.assertLess(upload_data["upload_compressed_size"], 116_000,
                        "Expected smaller compressed upload size.")

        # Delete all files in my workspace (normal)
        response = self.client.post(f"/filemanager/api/{upload_data['upload_id']}/delete_all",
                                    headers={'Authorization': token},
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, 200, "Delete all user-uploaded files.")

        # Finally, after deleting all files, check the total upload size

        # Get summary and check upload_total_size
        response = self.client.get(f"/filemanager/api/{upload_data['upload_id']}",
                                   headers={'Authorization': token})

        self.assertEqual(response.status_code, 200, "File summary.")
        try:
            jsonschema.validate(json.loads(response.data), result_schema)
        except jsonschema.exceptions.SchemaError as e:
            self.fail(e)

        upload_data: Dict[str, Any] = json.loads(response.data)

        # Check that upload_total_size is in summary response
        self.assertIn("upload_total_size", upload_data,
                      "Returns total upload size.")
        # Check that upload_compressed_size is in summary response
        self.assertIn("upload_compressed_size", upload_data,
                      "Returns compressed upload size.")

        # upload total size is definitely smaller than original 275781 bytes
        # after we deleted everything we uploaded!!
        self.assertEqual(upload_data["upload_total_size"], 0,
                         "Expected smaller total upload size after deleting"
                         " all files.")
        self.assertEqual(upload_data["upload_compressed_size"], 0,
                         "Expected smaller compressed size after deleting"
                         " all files.")

        # Let's try to upload a different source format type - HTML
        testfiles_dir = os.path.join(cwd, 'tests/test_files_sub_type')
        filepath = os.path.join(testfiles_dir, 'sampleB_html.tar.gz')

        # Prepare gzipped tar submission for upload
        filename = os.path.basename(filepath)

        # Post a test submission to upload API

        response = self.client.post(f"/filemanager/api/{upload_data['upload_id']}",
                                    data={
                                        # 'file': (io.BytesIO(b"abcdef"), 'test.jpg'),
                                        'file': (open(filepath, 'rb'), filename),
                                    },
                                    headers={'Authorization': token},
                                    #        content_type='application/gzip')
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, 201,
                         "Accepted and processed uploaded Submission Contents")

        self.maxDiff = None

        with open('schema/resources/uploadResult.json') as f:
            result_schema = json.load(f)

        try:
            jsonschema.validate(json.loads(response.data), result_schema)
        except jsonschema.exceptions.SchemaError as e:
            self.fail(e)

        upload_data: Dict[str, Any] = json.loads(response.data)

        self.assertEqual(upload_data['source_format'], "html",
                         ("Check source format of HTML submission."
                          f" [ID={upload_data['upload_id']}]"))

        # DONE TESTS, NOW CLEANUP

        # Delete the workspace

        # Create admin token for deleting upload workspace
        admin_token = generate_token(self.app, [auth.scopes.READ_UPLOAD,
                                                auth.scopes.WRITE_UPLOAD,
                                                auth.scopes.DELETE_UPLOAD_WORKSPACE.as_global()])

        response = self.client.delete(f"/filemanager/api/{upload_data['upload_id']}",
                                      headers={'Authorization': admin_token}
                                      )

        # This cleans out the workspace. Comment out if you want to inspect files
        # in workspace. Source log is saved to 'deleted_workspace_logs' directory.
        self.assertEqual(response.status_code, 200, "Accepted request to delete workspace.")

        # At this point workspace has been removed/deleted.
