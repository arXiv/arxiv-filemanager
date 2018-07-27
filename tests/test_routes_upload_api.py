"""Tests for :mod:`filemanager.routes.upload_api`."""

from unittest import TestCase, mock
from datetime import datetime
import json
import os.path
from typing import Any, Optional, Dict
from io import BytesIO
import jsonschema
import jwt

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
    @mock.patch('filemanager.controllers.upload.create_upload')
    def test_create_upload(self, mock_create_upload: Any) -> None:
        """Endpoint /filemanager/upload/create_upload returns JSON about a new upload."""

        with open('schema/resources/uploadCreate.json') as f:
            schema = json.load(f)

        # Create a token for writing to upload workspace
        token = generate_token(self.app,
                               {'scope': ['read:upload', 'write:upload']})


        created = datetime.now()
        create_data = {'upload_id': 4, 'create_datetime': created.isoformat(),
                       'url': '/filemanager/api/upload/4'}
        mock_create_upload.return_value = create_data, 201, {}

        print("\nMake 'create upload' request\n")

        response = self.client.get('/filemanager/api/create',
                                   headers={'Authorization': token})

        #  data['file'] = (io.BytesIO(b"abcdef"), 'test.jpg')
        expected_data = {'upload_id': create_data['upload_id'],
                         'create_datetime': create_data['create_datetime'],
                         'url': create_data['url']}

        self.assertEqual(response.status_code, 201)
        self.assertDictEqual(json.loads(response.data), expected_data)

        try:
            jsonschema.validate(json.loads(response.data), schema)
        except jsonschema.exceptions.SchemaError as e:
            self.fail(e)

    # Upload a submission package
    def test_upload_files(self) -> None:
        """Test uploading submission package."""
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
        print(f"\nAPI: Create upload and post upload file {filename} to server\n")

        response = self.client.get('/filemanager/api/create',
                                   headers={'Authorization': token})
        #print("**Create Response:" + str(response.data) + '\n')

        create_data: Dict[str, Any] = json.loads(response.data)

        #print(f"Upload: Created upload with Id: {create_data['upload_id']}\n")
        #print(f"Upload: Upload files URL: {create_data['url']}\n")
        # Post a test submission to upload API

        #token1 = str(token.encode("ascii"))
        print(f"Token (for possible use in manual browser tests): {token}\n")

        print("\nMake request to upload gzipped tar file. \n"
              + "\t[Warnings and errors are currently printed to console.\n"
              + "\tLogs coming soon.]\n")

        #response = self.client.post('/filemanager/upload/upload/5',
        response = self.client.post(create_data['url'],
                                    data={
                                        # 'file': (io.BytesIO(b"abcdef"), 'test.jpg'),
                                  #      'file': (open(filepath, 'rb'), 'test.tar.gz'),
                                        'file': (open(filepath, 'rb'), filename),
                                    },
                                    headers={'Authorization': token},
                                    #        content_type='application/gzip')
                                    content_type='multipart/form-data')

        self.assertEqual(response.status_code, 202, "Accepted uploaded Submission Contents")

        expected_data = {'reason': 'upload in progress'}

        self.maxDiff = None
        self.assertDictEqual(json.loads(response.data), expected_data)

        try:
            jsonschema.validate(json.loads(response.data), schema)
        except jsonschema.exceptions.SchemaError as e:
            self.fail(e)


        # Now check status
        with open('schema/resources/uploadStatus.json') as f:
            status_schema = json.load(f)

        response = self.client.get(f"/filemanager/api/upload_status/{create_data['upload_id']}",
                                   headers={'Authorization': token})
        print(f"\nRequest: /filemanager/api/upload_status/{create_data['upload_id']}")
        #print("Task Status Response (simple):\n" + str(response.data) + '\n')

        try:
            jsonschema.validate(json.loads(response.data), status_schema)
        except jsonschema.exceptions.SchemaError as e:
            self.fail(e)

        # Get summary of upload

        with open('schema/resources/uploadResult.json') as f:
            status_schema = json.load(f)

        response = self.client.get(f"/filemanager/api/upload/{create_data['upload_id']}",
                                   headers={'Authorization': token})

        print(f"\nRequest: /filemanager/api/upload/{create_data['upload_id']}")
        print("Upload Summary Response:\n" + str(response.data) + '\n')

        try:
            jsonschema.validate(json.loads(response.data), status_schema)
        except jsonschema.exceptions.SchemaError as e:
            self.fail(e)
