"""Tests for :mod:`filemanager.routes.upload_api`."""

from unittest import TestCase, mock
from datetime import datetime, timedelta
from typing import Any, Optional, Dict, List
from io import BytesIO
from http import HTTPStatus as status
from pprint import pprint
import shutil

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

import jsonschema
import jwt
from requests.utils import quote
from flask import Flask

from filemanager.factory import create_web_app
from filemanager.services import database

from arxiv.users import domain, auth


TEST_FILES_STRIP_PS = os.path.join(os.getcwd(), 'tests/test_files_strip_postscript')

# TODO: Leaving these because either they were commented out originally, or 
# it's not clear what to do with them. --Erick 2019-06-26

# class TestAncillaryFiles(TestCase):
#     def test_download_ancillary_file(self):
#         """Download an ancillary file."""
#         response = self.client.get(
#             f"/filemanager/api/{self.upload_id}/main_a.tex/content",
#             headers={'Authorization': self.token}
#         )
#         self.assertEqual(response.status_code, status.OK)
#         self.assertIn('ETag', response.headers, "Returns an ETag header")


# class TestOneOffSitations(TestCase):
#     def xxx_test_one_off_situations(self) -> None:
#         """
#         Test to make sure response contains warnings/errors.
#         Returns
#         -------
#
#         """
#         cwd = os.getcwd()
#         testfiles_dir = os.path.join(cwd, 'tests/test_files_upload')
#
#         # Create a token for writing to upload workspace
#         token = generate_token(self.app, [auth.scopes.READ_UPLOAD,
#                                           auth.scopes.WRITE_UPLOAD,
#                                           auth.scopes.DELETE_UPLOAD_FILE])
#
#         # Trying to replicate bib/bbl upload behavior
#         # Lets upload a file before uploading the zero length file
#
#         #filepath1 = os.path.join(testfiles_dir, 'UploadRemoveFiles.tar')
#         filepath1 = os.path.join(testfiles_dir, 'only_figures_tikz_needs_pdflatx.tar.gz')
#         filename1 = os.path.basename(filepath1)
#         response = self.client.post('/filemanager/api/',
#                                     data={
#                                         # 'file': (io.BytesIO(b"abcdef"), 'test.jpg'),
#                                         'file': (open(filepath1, 'rb'), filename1),
#                                     },
#                                     headers={'Authorization': token},
#                                     #        content_type='application/gzip')
#                                     content_type='multipart/form-data')
#
#         print("Upload Response:\n")
#         print(json.dumps(json.loads(response.data), indent=4, sort_keys=True))
#
#         with open('schema/resources/Workspace.json') as f:
#             result_schema = json.load(f)
#
#         try:
#             jsonschema.validate(json.loads(response.data), result_schema)
#         except jsonschema.exceptions.SchemaError as e:
#             self.fail(e)
#
#         upload_data: Dict[str, Any] = json.loads(response.data)
#
#         # Delete the workspace
#         # Create admin token for deleting upload workspace
#         admin_token = generate_token(self.app, [auth.scopes.READ_UPLOAD,
#                                                 auth.scopes.WRITE_UPLOAD,
#                                                 auth.scopes.DELETE_UPLOAD_WORKSPACE.as_global()])
#
#         response = self.client.delete(f"/filemanager/api/{self.upload_id}",
#                                       headers={'Authorization': admin_token}
#                                       )
#
#         # This cleans out the workspace. Comment out if you want to inspect files
#         # in workspace. Source log is saved to 'deleted_workspace_logs' directory.
#         self.assertEqual(response.status_code, status.OK, "Accepted request to delete workspace.")
#
#
#     # Upload a submission package and perform normal operations on upload
#     def test_upload_files_normal(self) -> None:
#         """Test normal well-behaved upload requests.
#
#         This series of tests uploads files with the expectation of success.
#
#         The appropriate tokens are provided to various requests.
#
#         Note: Delete workspace still needs to be implemented.
#         """
#         with open('schema/resources/uploadResponse.json') as f:
#             schema = json.load(f)
#
#         # Create a token for writing to upload workspace
#         token = generate_token(self.app, [auth.scopes.READ_UPLOAD,
#                                           auth.scopes.WRITE_UPLOAD,
#                                           auth.scopes.DELETE_UPLOAD_FILE])
#
#         created = datetime.now(UTC)
#         modified = datetime.now(UTC)
#         expected_data = {'upload_id': 5,
#                          'status': "SUCCEEDED",
#                          'create_datetime': created.isoformat(),
#                          'modify_datetime': modified.isoformat()
#                          }
#
#         cwd = os.getcwd()
#         testfiles_dir = os.path.join(cwd, 'tests/test_files_upload')
#         filepath = os.path.join(testfiles_dir, '1801.03879-1.tar.gz')
#
#         # Prepare gzipped tar submission for upload
#         filename = os.path.basename(filepath)