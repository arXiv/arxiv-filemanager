"""Tests for :mod:`filemanager.routes.upload_api`."""

from unittest import TestCase, mock
from datetime import datetime
import json
import os.path
from typing import Any, Optional, Dict
from io import BytesIO
import jsonschema
import jwt
from requests.utils import quote
from flask import Flask
from filemanager.factory import create_web_app
from filemanager.services import uploads


# Generate authentication token
def generate_token(app: Flask, claims: dict) -> str:
    """Helper function for generating a JWT."""
    secret = app.config.get('JWT_SECRET')
    return jwt.encode(claims, secret, algorithm='HS256')  # type: ignore


class TestUploadAPIRoutes(TestCase):
    """Sample tests for upload external API routes."""

    def setUp(self) -> None:
        """Initialize the Flask application, and get a client for testing."""
        self.app = create_web_app()
        self.client = self.app.test_client()
        self.app.app_context().push()
        uploads.db.create_all()

    # Provide general statistics on the upload service. Primarily intended to
    # indicate normal operation or exception conditions. This information will be
    # expanded greatly in coming weeks
    # @mock.patch('zero.controllers.upload.status')
    # def test_service_status(self, mock_get_baz: Any) -> None:
    def test_service_status(self) -> None:
        """Endpoint /filemanager/upload/status<int> returns JSON about file management service."""

        with open('schema/resources/serviceStatus.json') as f:
            schema = json.load(f)

        print("\nMake service-level 'status' request\n")

        # response = self.client.get('/zero/upload/create')
        response = self.client.get('/filemanager/api/status')

        expected_data = {'status': 'OK', 'total_uploads': 1}
        print(response)
        self.assertEqual(response.status_code, 200)
        self.assertDictEqual(json.loads(response.data), expected_data)

        try:
            jsonschema.validate(json.loads(response.data), schema)
        except jsonschema.exceptions.SchemaError as e:
            self.fail(e)

    # Create upload folder/container
    def test_create_upload_failures(self) -> None:
        """Endpoint /filemanager/upload/create_upload returns JSON about a new upload."""

        # No token
        response = self.client.post('/filemanager/api/',
                                    data={
                                        'file': '',
                                    },
                                    # Missing authorization field
                                    #headers={'Authorization': ''},
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, 403, 'Authorization token not passed to server')

        # Authorization argument without valid token
        response = self.client.post('/filemanager/api/',
                                    data={
                                        'file': '',
                                    },
                                    # Empty token value
                                    headers={'Authorization': ''},
                                    #        content_type='application/gzip')
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, 403, 'Empty authorization token passed to server')

        # Create an INVALID token for writing to upload workspace
        token = generate_token(self.app,
                               {'scope': ['delete:upload', 'hack:upload']})

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
        token = generate_token(self.app,
                               {'scope': ['read:upload', 'write:upload']})

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

        expected_data = {'reason': ['missing file/archive payload']}
        self.assertDictEqual(json.loads(response.data), expected_data)

        # TODO: Looks like this condition is not possible, though online forum
        # noted possibility of null name.

        # Filename missing or null
        response = self.client.post('/filemanager/api/',
                                    data={
                                        # filename is null
                                        #'file': (open(filepath, 'rb'), ''),
                                        'file': (open(filepath, 'rb'), ''),
                                    },
                                    # Good Token
                                    headers={'Authorization': token},
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, 400, 'Valid authorization token not passed to server')

        expected_data = {'reason': ['missing file/archive payload']}
        self.assertDictEqual(json.loads(response.data), expected_data)

        # Set up new test

        #testfiles_dir = os.path.join(cwd, 'tests/test_files_upload')
        testfiles_dir = '/tmp'
        filepath = os.path.join(testfiles_dir, 'nullfile')

        # Upload empty/null file
        response = self.client.post('/filemanager/api/',
                                    data={
                                        # filename is null
                                        # 'file': (open(filepath, 'rb'), ''),
                                        'file': (open(filepath, 'rb'), 'Empty'),
                                    },
                                    # Good Token
                                    headers={'Authorization': token},
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, 400, 'Empty file uploaded to server')

        expected_data = {'reason': ['file payload is zero length']}
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
        token = generate_token(self.app,
                               {'scope': ['read:upload', 'write:upload']})

        created = datetime.now()
        modified = datetime.now()
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

        #token1 = str(token.encode("ascii"))
        print(f"Token (for possible use in manual browser tests): {token}\n")

        print("\nMake request to upload gzipped tar file to non existent workspace. \n"
              + "\t[Warnings and errors are currently printed to console.\n"
              + "\tLogs coming soon.]\n")

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

        expected_data = {'reason': ['upload workspace not found']}

        self.maxDiff = None
        self.assertDictEqual(json.loads(response.data), expected_data)

        response = self.client.get(f"/filemanager/api/{bad_upload_id}",
                                   headers={'Authorization': token})

        self.assertEqual(response.status_code, 404, "Accepted uploaded Submission Contents")

        expected_data = {'reason': ['upload workspace not found']}

        self.maxDiff = None
        self.assertDictEqual(json.loads(response.data), expected_data)

        # TODO: Add tests for locked/released workspaces on upload requests.
        # TODO: Lock/unlock, release/unrelease. (when implements)

        # TODO: Add size checks (when implemented)


    def test_delete_file(self) -> None:
        """
        Test delete file operation.

        These tests will focus on triggering delete failures.

        """
        # Create a token for writing to upload workspace
        token = generate_token(self.app,
                               {'scope': ['read:upload', 'write:upload']})


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
        # public_file_path = "../../subdir/this_file"
        # public_file_path = "this_file"
        #public_file_path = "lipics-logo-bw.pdf"
        public_file_path = "accessibilityMeta.sty"

        encoded_file_path = quote(public_file_path, safe='')
        public_file_path = encoded_file_path
        print(f"ENCODED:{public_file_path}\n")

        response = self.client.delete(f"/filemanager/api/{upload_data['upload_id']}/{public_file_path}",
                                      headers={'Authorization': token})
        print(f"Delete File Response:'{public_file_path}'\n" + str(response.data) + '\n')
        self.assertEqual(response.status_code, 200,
                         "Delete an individual file: '{public_file_path}'.")

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

    def test_delete_all_files(self) -> None:
        """
        Test delete file operation.

        These tests will focus on triggering delete failures.

        """
        # Create a token for writing to upload workspace
        token = generate_token(self.app,
                               {'scope': ['read:upload', 'write:upload']})

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
        print("Delete All Files Response:\n" + str(response.data) + '\n')
        self.assertEqual(response.status_code, 200, "Delete all user-uploaded files.")

        # There are really not many exceptions we can generate as long as the upload workspace
        # exists. If upload workspace exists this command will remove all files and directories
        # under src directory. At this point I don't anticipate generating exception when src
        # directory is already empty.

        # Delete all files in my workspace (normal)
        response = self.client.post(f"/filemanager/api/999999/delete_all",
                                    headers={'Authorization': token},
                                    content_type='multipart/form-data')
        print("Delete All Files for invalid workspace Response:\n" + str(response.data) + '\n')
        self.assertEqual(response.status_code, 404,
                         "Delete all user-uploaded files for non-existent workspace.")



        # Try an delete an individual file ...we'll know if delete all files really worked.
        public_file_path = "anc/manuscript_Na2.7Ru4O9.tex"
        public_file_path = quote(public_file_path, safe='')
        response = self.client.delete(f"/filemanager/api/{upload_data['upload_id']}/{public_file_path}",
                                      headers={'Authorization': token})
        print(f"Delete already deleted file in subdirectory anc Response:'{public_file_path}'\n" + str(response.data) + '\n')
        self.assertEqual(response.status_code, 404,
                         f"Delete already deleted file in subdirectory: '{public_file_path}'.")


    def test_delete_upload_workspace(self) -> None:
        """
        Test delete file operation.

        These tests will focus on triggering delete failures.

        """

        # TODO: Need to work on this code after imlementing delete workspace.

        # Create a token for writing to upload workspace
        token = generate_token(self.app,
                               {'scope': ['read:upload', 'write:upload']})

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

        admin_token = generate_token(self.app,
                                     {'scope': ['read:upload', 'write:upload',
                                                'admin:upload']})
        print(f"ADMIN Token (for possible use in manual browser tests): {admin_token}\n")

        response = self.client.delete(f"/filemanager/api/{upload_data['upload_id']}",
                                      headers={'Authorization': admin_token}
                                      )

        # print("Delete Response:\n" + str(response.data) + '\n')

        self.assertEqual(response.status_code, 200, "Delete workspace.")

        # Let's try to delete the same workspace again

        response = self.client.delete(f"/filemanager/api/{upload_data['upload_id']}",
                                      headers={'Authorization': admin_token}
                                      )

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






    # Upload a submission package
    def test_upload_files_normal(self) -> None:
        """Test normal well-behaved upload.

        This series of tests uploads files with the expectation of success.

        The appropriate tokens are provided to various requests.

        Note: Delete workspace still needs to be implemented.
        """
        with open('schema/resources/uploadResponse.json') as f:
            schema = json.load(f)

        # Create a token for writing to upload workspace
        token = generate_token(self.app,
                               {'scope': ['read:upload', 'write:upload']})

        created = datetime.now()
        modified = datetime.now()
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
                                  #      'file': (open(filepath, 'rb'), 'test.tar.gz'),
                                        'file': (open(filepath, 'rb'), filename),
                                    },
                                    headers={'Authorization': token},
                                    #        content_type='application/gzip')
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, 201, "Accepted and processed uploaded Submission Contents")

        self.maxDiff = None

        with open('schema/resources/uploadResult.json') as f:
            summary_schema = json.load(f)

        try:
            jsonschema.validate(json.loads(response.data), summary_schema)
        except jsonschema.exceptions.SchemaError as e:
            self.fail(e)

        upload_data: Dict[str, Any] = json.loads(response.data)

        # Get summary of upload

        with open('schema/resources/uploadResult.json') as f:
            status_schema = json.load(f)

        response = self.client.get(f"/filemanager/api/{upload_data['upload_id']}",
                                   headers={'Authorization': token})

        try:
            jsonschema.validate(json.loads(response.data), status_schema)
        except jsonschema.exceptions.SchemaError as e:
            self.fail(e)

        # Delete a file (normal call)
        #public_file_path = "../../subdir/this_file"
        #public_file_path = "this_file"
        public_file_path = "lipics-logo-bw.pdf"
        from requests.utils import quote
        encoded_file_path = quote(public_file_path, safe='')
        #encoded_file_path = public_file_path
        print(f"ENCODED:{encoded_file_path}\n")
        #response = self.client.delete(f"/filemanager/api/{upload_data['upload_id']}/{encoded_file_path}",
        response = self.client.delete(f"/filemanager/api/{upload_data['upload_id']}/{public_file_path}",
                                   headers={'Authorization': token})
        print("Delete File Response:\n" + str(response.data) + '\n')
        self.assertEqual(response.status_code, 200, "Delete an individual file.")

        # Delete all files in my workspace (normal)
        response = self.client.post(f"/filemanager/api/{upload_data['upload_id']}/delete_all",
                                   headers={'Authorization': token},
                                   content_type='multipart/form-data')
        print("Delete All Files Response:\n" + str(response.data) + '\n')
        self.assertEqual(response.status_code, 200, "Delete all user-uploaded files.")

        # Delete the workspace

        # Create admin token for deleting upload workspace
        admin_token = generate_token(self.app,
                                   {'scope': ['read:upload', 'write:upload',
                                              'admin:upload']})
        print(f"ADMIN Token (for possible use in manual browser tests): {admin_token}\n")

        response = self.client.delete(f"/filemanager/api/{upload_data['upload_id']}",
                                      headers={'Authorization': admin_token}
                                      )

        #print("Delete Response:\n" + str(response.data) + '\n')

        # This cleans out the workspace. Comment out if you want to inspect files
        # in workspace. Source log is saved to 'deleted_workspace_logs' directory.
        self.assertEqual(response.status_code, 200, "Accepted request to delete workspace.")
