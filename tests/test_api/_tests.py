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


# class TestAncillaryFiles(TestCase):
#     def test_download_ancillary_file(self):
#         """Download an ancillary file."""
#         response = self.client.get(
#             f"/filemanager/api/{self.upload_id}/main_a.tex/content",
#             headers={'Authorization': self.token}
#         )
#         self.assertEqual(response.status_code, status.OK)
#         self.assertIn('ETag', response.headers, "Returns an ETag header")


#

#
#
#     def test_missing_bbl_upload(self) -> None:
#         """
#         This test exercises missing references (.bib/.bbl) logic.
#
#         :return:
#         """
#         cwd = os.getcwd()
#         testfiles_dir = os.path.join(cwd, 'tests/test_files_upload')
#
#
#
#         # Create a token for writing to upload workspace
#         token = generate_token(self.app, [auth.scopes.READ_UPLOAD,
#                                           auth.scopes.WRITE_UPLOAD,
#                                           auth.scopes.DELETE_UPLOAD_FILE])
#
#         # Replicate bib/bbl upload behavior
#
#         # Lets upload submission that is missing required .bbl file.
#
#         filepath1 = os.path.join(testfiles_dir, 'bad_bib_but_no_bbl.tar')
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
#         # IMPORTANT: readiness of 'ERRORS' should stop submission from
#         # proceeding until missing .bbl is provided OR .bib is removed.
#
#         upload_data: Dict[str, Any] = json.loads(response.data)
#         self.assertIn('readiness', upload_data, "Returns total upload status.")
#         self.assertEqual(upload_data['readiness'], "ERRORS",
#                          ("Expected total upload size matches "
#                          f"(ID: {self.upload_id})"))
#
#         # Get upload_id from previous file upload
#         test_id = self.upload_id
#         # Upload missing .bbl
#         filepath = os.path.join(testfiles_dir, 'final.bbl')
#         filename = os.path.basename(filepath)
#         response = self.client.post(f"/filemanager/api/{self.upload_id}",
#                                     data={
#                                         # 'file': (io.BytesIO(b"abcdef"), 'test.jpg'),
#                                         'file': (open(filepath, 'rb'), filename),
#                                     },
#                                     headers={'Authorization': token},
#                                     #        content_type='application/gzip')
#                                     content_type='multipart/form-data')
#
#         # Check response and extract upload_id from response
#         self.assertEqual(response.status_code, 201, "Accepted and processed uploaded Submission Contents")
#
#         self.maxDiff = None
#
#         try:
#             jsonschema.validate(json.loads(response.data), result_schema)
#         except jsonschema.exceptions.SchemaError as e:
#             self.fail(e)
#
#         # IMPORTANT: After we upload compiled .bbl file 'update_status' changes
#         # from ERRORS to READY_WITH_WARNINGS.
#         upload_data: Dict[str, Any] = json.loads(response.data)
#         self.assertIn('readiness', upload_data, "Returns total upload status.")
#         self.assertEqual(upload_data['readiness'], "READY_WITH_WARNINGS",
#                          "Expected total upload size matches")
#
#         # Finally, Delete the workspace
#
#         # Create admin token for deleting upload workspace
#         admin_token = generate_token(self.app, [auth.scopes.READ_UPLOAD,
#                                                 auth.scopes.WRITE_UPLOAD,
#                                                 auth.scopes.DELETE_UPLOAD_WORKSPACE.as_global()])
#
#         response = self.client.delete(f"/filemanager/api/{test_id}",
#                                       headers={'Authorization': admin_token}
#                                       )
#     def search_errors(self, mstring: str, mtype:str, filename: str, error_list: list) -> bool:
#         """
#         Search for specific warning in errors.
#         :return:
#         """
#         for error in error_list:
#             type, filepath, message = error
#             #print(f"Look for error '{mstring}' in \n\t'{message}'")
#             if re.search(mstring, message):
#                 found = True
#
#                 if mtype and mtype != type:
#                     found = False
#
#                 if filename and filename != filepath:
#                     found = False
#
#                 if found is True:
#                     return True
#
#         return False
#
#     def search_files(self, filename: str, files: list) -> bool:
#         """
#         Check if specific file is in list.
#         :param filename:
#         :param files:
#         :return:
#         """
#         for file in files:
#             mod, name, path, size, type = file
#             if filename == name:
#                 return True
#         return False
#
#
#     def test_warnings_and_errors(self) -> None:
#         """
#
#         This test currently exercises warnings and errors logic.
#
#         :return:
#         """
#         cwd = os.getcwd()
#         testfiles_dir = os.path.join(cwd, 'tests/test_files_upload')
#
#
#
#         # Create a token for writing to upload workspace
#         token = generate_token(self.app, [auth.scopes.READ_UPLOAD,
#                                           auth.scopes.WRITE_UPLOAD,
#                                           auth.scopes.DELETE_UPLOAD_FILE])
#
#         # Trying to replicate bib/bbl upload behavior
#         # Lets upload a file before uploading the zero length file
#
#         filepath1 = os.path.join(testfiles_dir, 'UploadRemoveFiles.tar')
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
#         #print("Upload Response:\n" + str(response.data) + "\nEnd Data")
#         #print(json.dumps(json.loads(response.data), indent=4, sort_keys=True))
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
#         # IMPORTANT RESULT readiness of ERRORS should stop submission from
#         # proceeding until missing .bbl is provided OR .bib is removed.
#         upload_data: Dict[str, Any] = json.loads(response.data)
#         self.assertIn('readiness', upload_data, "Returns total upload status.")
#         self.assertEqual(upload_data['readiness'], "ERRORS",
#                          "Expected total upload size matches")
#
#         # Make sure we are seeing errors
#         self.assertTrue(self.search_errors("Removed file 'remove.desc' \[File not allowed].",
#                                            "warn", "remove.desc",
#                                            upload_data['errors']), "Expect this error to occur.")
#
#         self.assertFalse(self.search_files('remove.desc', upload_data['files']), "File was removed")
#
#         self.assertTrue(self.search_errors("Removed file '.junk' \[File not allowed]",
#                                            "warn", ".junk",
#                                            upload_data['errors']), "Expect this error to occur.")
#
#         self.assertTrue(self.search_errors("Removed the file 'core' \[File not allowed].",
#                                            "warn", "core",
#                                            upload_data['errors']), "Expect this error to occur.")
#
#         self.assertTrue(self.search_errors("REMOVING standard style files for Paul",
#                                            "warn", "diagrams.sty",
#                                            upload_data['errors']), "Expect this error to occur.")
#
#         self.assertTrue(self.search_errors("File 'zero.txt' is empty \(size is zero\)",
#                                            "warn", "zero.txt",
#                                            upload_data['errors']), "Expect this error to occur.")
#
#         self.assertTrue(self.search_errors("Removed file 'xxx.cshrc' \[File not allowed].",
#                                            "warn", "",
#                                            upload_data['errors']), "Expect this error to occur.")
#
#         self.assertTrue(self.search_errors("Removed the file 'uufiles' \[File not allowed].",
#                                            "warn", "uufiles",
#                                            upload_data['errors']), "Expect this error to occur.")
#
#         self.assertTrue(self.search_errors("Removed file 'xxx.cshrc' \[File not allowed].",
#                                            "warn", "xxx.cshrc",
#                                            upload_data['errors']), "Expect this error to occur.")
#
#         self.assertTrue(self.search_errors("Removed file 'final.aux' due to name conflict",
#                                            "warn", "final.aux",
#                                            upload_data['errors']), "Expect this error to occur.")
#
#         self.assertTrue(self.search_errors("We do not run bibtex in the auto",
#                                            "warn", "final.bib",
#                                            upload_data['errors']), "Expect this error to occur.")
#
#         self.assertTrue(self.search_errors("Removed the file 'final.bib'. Using 'final.bbl' for references.",
#                                            "warn", "final.bib",
#                                            upload_data['errors']), "Expect this error to occur.")
#
#         self.assertTrue(self.search_errors("Removing file 'aa.dem' on the assumption that it is the example "
#                                            + "file for the Astronomy and Astrophysics macro package aa.cls.",
#                                            "warn", "aa.dem",
#                                            upload_data['errors']), "Expect this error to occur.")
#
#         self.assertTrue(self.search_errors("Removed file 'aa.dem'.",
#                                            "warn", "aa.dem",
#                                            upload_data['errors']), "Expect this error to occur.")
#
#         self.assertTrue(self.search_errors("WILL REMOVE standard revtex4 style",
#                                            "warn", "revtex4.cls",
#                                            upload_data['errors']), "Expect this error to occur.")
#
#         self.assertTrue(self.search_errors("Found hyperlink-compatible package 'espcrc2.sty'.",
#                                            "warn", "espcrc2.sty",
#                                            upload_data['errors']), "Expect this error to occur.")
#
#         self.assertTrue(self.search_errors("Your submission has been rejected because",
#                                            "fatal", "something.doc",
#                                            upload_data['errors']), "Expect this error to occur.")
#
#         self.assertTrue(self.search_errors("Removed file 'final.synctex'.",
#                                            "warn", "final.synctex",
#                                            upload_data['errors']), "Expect this error to occur.")
#
#         self.assertTrue(self.search_errors("Removed file 'final.out' due to name conflict.",
#                                            "warn", "final.out",
#                                            upload_data['errors']), "Expect this error to occur.")
#
#         # Uploaded DOC file is causing fatal error
#         filepath2 = os.path.join(testfiles_dir, 'README.md')
#         filename2 = os.path.basename(filepath2)
#         filename2 = '00README.XXX'
#         response = self.client.post(f"/filemanager/api/{self.upload_id}",
#                                     data={
#                                         # 'file': (io.BytesIO(b"abcdef"), 'test.jpg'),
#                                         'file': (open(filepath2, 'rb'), filename2),
#                                     },
#                                     headers={'Authorization': token},
#                                     #        content_type='application/gzip')
#                                     content_type='multipart/form-data')
#
#         self.assertEqual(response.status_code, 201, "Accepted and processed uploaded Submission Contents")
#
#         try:
#             jsonschema.validate(json.loads(response.data), result_schema)
#         except jsonschema.exceptions.SchemaError as e:
#             self.fail(e)
#
#         upload_data: Dict[str, Any] = json.loads(response.data)
#
#         amsg = ("Status returned to 'READY'."
#                 " Removed file causing fatal error."
#                 f" (ID:{self.upload_id})")
#         self.assertEqual(upload_data['readiness'], "READY", amsg)
#
#         # Upload files that we will warn about - but not remove.
#
#         filepath2 = os.path.join(testfiles_dir, 'FilesToWarnAbout.tar')
#         filename2 = os.path.basename(filepath2)
#         response = self.client.post(f"/filemanager/api/{self.upload_id}",
#                                     data={
#                                         # 'file': (io.BytesIO(b"abcdef"), 'test.jpg'),
#                                         'file': (open(filepath2, 'rb'), filename2),
#                                     },
#                                     headers={'Authorization': token},
#                                     #        content_type='application/gzip')
#                                     content_type='multipart/form-data')
#
#         #print("AFTER UPLOAD FILES TO WARN ON")
#         #print(json.dumps(json.loads(response.data), indent=4, sort_keys=True))
#
#         upload_data: Dict[str, Any] = json.loads(response.data)
#
#         # Normal emacs backup file
#         self.assertTrue(self.search_errors("File 'submission.tex~' may be a backup file. "\
#                                            "Please inspect and remove extraneous backup files.",
#                                            "warn", "submission.tex_",
#                                            upload_data['errors']), "Expect this error to occur.")
#
#         # Optional, we translate tilde to underscore thus this file appears. Leave just in case.
#         self.assertTrue(self.search_errors("File 'submission.tex_' may be a backup file. " \
#                                            "Please inspect and remove extraneous backup files.",
#                                            "warn", "submission.tex_",
#                                            upload_data['errors']), "Expect this error to occur.")
#
#         # Detect renaming of filename with tilde - since we loose original file name
#         self.assertTrue(self.search_errors("Attempting to rename submission.tex~ to submission.tex_.",
#                                            "warn", "submission.tex_",
#                                            upload_data['errors']), "Expect this error to occur.")
#
#         # Another backup file
#         self.assertTrue(self.search_errors("File 'submission.tex.bak' may be a backup file. "\
#                                            "Please inspect and remove extraneous backup files.",
#                                            "warn", "submission.tex.bak",
#                                            upload_data['errors']), "Expect this error to occur.")
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
#     def test_eps_repair(self) -> None:
#         """
#         This test is intended to be manually edited for debugging purposes.
#
#         This test currently exercises missing .bbl logic.
#
#         :return:
#         """
#         cwd = os.getcwd()
#         testfiles_dir = os.path.join(cwd, 'tests/test_files_strip_postscript')
#
#
#
#         # Create a token for writing to upload workspace
#         token = generate_token(self.app, [auth.scopes.READ_UPLOAD,
#                                           auth.scopes.WRITE_UPLOAD,
#                                           auth.scopes.DELETE_UPLOAD_FILE])
#
#         # Trying to replicate bib/bbl upload behavior
#         # Lets upload a file before uploading the zero length file
#         test_filename = 'dos_eps_1.eps'
#         filepath1 = os.path.join(testfiles_dir, test_filename)
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
#         #print("Upload Response:\n" + str(response.data) + "\nEnd Data")
#         #print(json.dumps(json.loads(response.data), indent=4, sort_keys=True))
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
#         self.assertTrue(self.search_errors("leading TIFF preview stripped",
#                                            "warn", test_filename,
#                                            upload_data['errors']), "Expect this error to occur.")
#
#         # Now let's grab file content and verify that it matches expected
#         # reference_path file.
#
#         # Check if content file exists
#         response = self.client.head(
#             f"/filemanager/api/{self.upload_id}/{test_filename}/content",
#             headers={'Authorization': token}
#         )
#         self.assertEqual(response.status_code, status.OK)
#         self.assertIn('ETag', response.headers, "Returns an ETag header")
#
#         # Download content file
#         response = self.client.get(
#             f"/filemanager/api/{self.upload_id}/{test_filename}/content",
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
#         reference_filename = 'dos_eps_1_stripped.eps'
#         reference_path = os.path.join(TEST_FILES_STRIP_PS, reference_filename)
#         # Compared fixed file to a reference_path stripped version of file.
#         is_same = filecmp.cmp(content_file_path, reference_path, shallow=False)
#         self.assertTrue(is_same,
#                         f"Repair Encapsulated Postscript file '{test_filename}'.")
#
#         # Try encapsulate Postscript with trailing TIFF
#
#         # Trying to replicate bib/bbl upload behavior
#         # Lets upload a file before uploading the zero length file
#         test_filename = 'dos_eps_2.eps'
#         filepath1 = os.path.join(testfiles_dir, test_filename)
#         filename1 = os.path.basename(filepath1)
#         response = self.client.post(f"/filemanager/api/{self.upload_id}",
#                                     data={
#                                         # 'file': (io.BytesIO(b"abcdef"), 'test.jpg'),
#                                         'file': (open(filepath1, 'rb'), filename1),
#                                     },
#                                     headers={'Authorization': token},
#                                     #        content_type='application/gzip')
#                                     content_type='multipart/form-data')
#
#         # print("Upload Response:\n" + str(response.data) + "\nEnd Data")
#         # print(json.dumps(json.loads(response.data), indent=4, sort_keys=True))
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
#             f"/filemanager/api/{self.upload_id}/{test_filename}/content",
#             headers={'Authorization': token}
#         )
#         self.assertEqual(response.status_code, status.OK)
#         self.assertIn('ETag', response.headers, "Returns an ETag header")
#
#         # Download content file
#         response = self.client.get(
#             f"/filemanager/api/{self.upload_id}/{test_filename}/content",
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
#         response = self.client.delete(f"/filemanager/api/{self.upload_id}",
#                                       headers={'Authorization': admin_token}
#                                       )
#
#         # This cleans out the workspace. Comment out if you want to inspect files
#         # in workspace. Source log is saved to 'deleted_workspace_logs' directory.
#         self.assertEqual(response.status_code, status.OK, "Accepted request to delete workspace.")
#
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
#
#         # Post a test submission to upload API
#
#         print(f"Token (for possible use in manual browser tests): {token}\n")
#
#         print("\nMake request to upload gzipped tar file. \n"
#               + "\t[Warnings and errors are currently printed to console.\n"
#               + "\tLogs coming soon.]\n")
#
#         response = self.client.post('/filemanager/api/',
#                                     data={
#                                         # 'file': (io.BytesIO(b"abcdef"), 'test.jpg'),
#                                         'file': (open(filepath, 'rb'), filename),
#                                     },
#                                     headers={'Authorization': token},
#                                     #        content_type='application/gzip')
#                                     content_type='multipart/form-data')
#
#         self.assertEqual(response.status_code, 201,
#                          "Accepted and processed uploaded Submission Contents")
#
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
#         upload_data: Dict[str, Any] = json.loads(response.data)
#
#         # Check that upload_total_size is in summary response
#         self.assertIn("upload_total_size", upload_data,
#                       "Returns total upload size.")
#         self.assertEqual(upload_data["upload_total_size"], 275_781,
#                          "Expected total upload size to match"
#                          f" (ID:{self.upload_id}).")
#
#         # Check that upload_compressed_size is in summary response
#         self.assertIn("upload_compressed_size", upload_data,
#                       "Returns compressed upload size.")
#         self.assertLess(upload_data["upload_compressed_size"], 116_000,
#                          "Expected total upload size to match"
#                          f" (ID:{self.upload_id}).")
#
#         self.assertEqual(upload_data["source_format"], "tex",
#                          "Check source format of TeX submission."
#                          f" [ID={self.upload_id}]")
#
#         # Get summary of upload
#
#         # with open('schema/resources/Workspace.json') as f:
#         #   status_schema = json.load(f)
#
#         response = self.client.get(f"/filemanager/api/{self.upload_id}",
#                                    headers={'Authorization': token})
#
#         self.assertEqual(response.status_code, status.OK, "File summary.")
#         try:
#             jsonschema.validate(json.loads(response.data), result_schema)
#         except jsonschema.exceptions.SchemaError as e:
#             self.fail(e)
#
#         # Check for file in upload result
#         summary_data: Dict[str, Any] = json.loads(response.data)
#         file_list = summary_data['files']
#         found = next((item for item in file_list if item["name"] == "lipics-v2016.cls"), False)
#         if next((item for item in file_list if item["name"] == "lipics-v2016.cls"), False):
#             print(f"FOUND UPLOADED FILE (Right Answer!): 'lipics-v2016.cls'")
#         else:
#             print(f"UPLOADED FILE NOT FOUND: 'lipics-v2016.cls' OOPS!")
#
#         self.assertTrue(found, "Uploaded file should exist in resulting file list.")
#
#         # Download content before we start deleting files
#
#         admin_token = generate_token(self.app, [auth.scopes.READ_UPLOAD,
#                                                 auth.scopes.WRITE_UPLOAD,
#                                                 auth.scopes.DELETE_UPLOAD_WORKSPACE.as_global()])
#
#         # Check if content exists
#         response = self.client.head(
#             f"/filemanager/api/{self.upload_id}/content",
#             headers={'Authorization': admin_token}
#         )
#         self.assertEqual(response.status_code, status.OK)
#         self.assertIn('ETag', response.headers, "Returns an ETag header")
#
#         # Download content
#         response = self.client.get(
#             f"/filemanager/api/{self.upload_id}/content",
#             headers={'Authorization': admin_token}
#         )
#         self.assertEqual(response.status_code, status.OK)
#         self.assertIn('ETag', response.headers, "Returns an ETag header")
#         workdir = tempfile.mkdtemp()
#         with tarfile.open(fileobj=BytesIO(response.data)) as tar:
#             tar.extractall(path=workdir)
#
#         print(f'List directory containing downloaded content: {workdir}\:n')
#         print(os.listdir(workdir))
#         print(f'End List\n')
#
#         # WARNING: THE TESTS BELOW DELETE INDIVIDUAL FILES AND THEN THE ENTIRE WORKSPACE
#
#         # Delete a file (normal call)
#         public_file_path = "lipics-logo-bw.pdf"
#         from requests.utils import quote
#         encoded_file_path = quote(public_file_path, safe='')
#
#         # response = self.client.delete(f"/filemanager/api/{self.upload_id}/{encoded_file_path}",
#         response = self.client.delete(f"/filemanager/api/{self.upload_id}/{public_file_path}",
#                                       headers={'Authorization': token})
#
#         self.assertEqual(response.status_code, status.OK, "Delete an individual file.")
#
#         # Delete another file
#         public_file_path = "lipics-v2016.cls"
#         encoded_file_path = quote(public_file_path, safe='')
#
#         # response = self.client.delete(f"/filemanager/api/{self.upload_id}/{encoded_file_path}",
#         response = self.client.delete(f"/filemanager/api/{self.upload_id}/{public_file_path}",
#                                       headers={'Authorization': token})
#         self.assertEqual(response.status_code, status.OK, "Delete an individual file.")
#
#         # Get summary after deletions
#         response = self.client.get(f"/filemanager/api/{self.upload_id}",
#                                    headers={'Authorization': token})
#
#         self.assertEqual(response.status_code, status.OK, "File summary after deletions.")
#
#         try:
#             jsonschema.validate(json.loads(response.data), result_schema)
#         except jsonschema.exceptions.SchemaError as e:
#             self.fail(e)
#
#         # Check that deleted file is missing from file list summary
#         summary_data: Dict[str, Any] = json.loads(response.data)
#         file_list = summary_data['files']
#         found = next((item for item in file_list if item["name"] == "lipics-v2016.clsXX"), False)
#         self.assertFalse(found, "Uploaded file should exist in resulting file list.")
#
#         if next((item for item in file_list if item["name"] == public_file_path), False):
#             print(f"FOUND DELETED FILE (Wrong Answer): '{public_file_path}'")
#         else:
#             print(f"DELETED FILE NOT FOUND (Right Answer!): '{public_file_path}'")
#
#         # Now check to see if size total upload size decreased
#         # Get summary and check upload_total_size
#         response = self.client.get(f"/filemanager/api/{self.upload_id}",
#                                    headers={'Authorization': token})
#
#         self.assertEqual(response.status_code, status.OK, "File summary.")
#         try:
#             jsonschema.validate(json.loads(response.data), result_schema)
#         except jsonschema.exceptions.SchemaError as e:
#             self.fail(e)
#         upload_data: Dict[str, Any] = json.loads(response.data)
#
#         # Check that upload_total_size is in summary response
#         self.assertIn('upload_total_size', upload_data, "Returns total upload size.")
#         self.assertNotEqual(upload_data['upload_total_size'], 275781,
#                             "Expected total upload size should not match "
#                             "pre - delete total")
#         # upload total size is definitely smaller than original 275781 bytes
#         # after we deleted a few files.
#         self.assertEqual(upload_data["upload_total_size"], 237_116,
#                          "Expected smaller total upload size.")
#         self.assertLess(upload_data["upload_compressed_size"], 116_000,
#                         "Expected smaller compressed upload size.")
#
#         # Delete all files in my workspace (normal)
#         response = self.client.post(f"/filemanager/api/{self.upload_id}/delete_all",
#                                     headers={'Authorization': token},
#                                     content_type='multipart/form-data')
#
#         self.assertEqual(response.status_code, status.OK, "Delete all user-uploaded files.")
#
#         # Finally, after deleting all files, check the total upload size
#
#         # Get summary and check upload_total_size
#         response = self.client.get(f"/filemanager/api/{self.upload_id}",
#                                    headers={'Authorization': token})
#
#         self.assertEqual(response.status_code, status.OK, "File summary.")
#         try:
#             jsonschema.validate(json.loads(response.data), result_schema)
#         except jsonschema.exceptions.SchemaError as e:
#             self.fail(e)
#
#         upload_data: Dict[str, Any] = json.loads(response.data)
#
#         # Check that upload_total_size is in summary response
#         self.assertIn("upload_total_size", upload_data,
#                       "Returns total upload size.")
#         # Check that upload_compressed_size is in summary response
#         self.assertIn("upload_compressed_size", upload_data,
#                       "Returns compressed upload size.")
#
#         # upload total size is definitely smaller than original 275781 bytes
#         # after we deleted everything we uploaded!!
#         self.assertEqual(upload_data["upload_total_size"], 0,
#                          "Expected smaller total upload size after deleting"
#                          " all files.")
#         self.assertEqual(upload_data["upload_compressed_size"], 0,
#                          "Expected smaller compressed size after deleting"
#                          " all files.")
#
#         # Let's try to upload a different source format type - HTML
#         testfiles_dir = os.path.join(cwd, 'tests/test_files_sub_type')
#         filepath = os.path.join(testfiles_dir, 'sampleB_html.tar.gz')
#
#         # Prepare gzipped tar submission for upload
#         filename = os.path.basename(filepath)
#
#         # Post a test submission to upload API
#
#         response = self.client.post(f"/filemanager/api/{self.upload_id}",
#                                     data={
#                                         # 'file': (io.BytesIO(b"abcdef"), 'test.jpg'),
#                                         'file': (open(filepath, 'rb'), filename),
#                                     },
#                                     headers={'Authorization': token},
#                                     #        content_type='application/gzip')
#                                     content_type='multipart/form-data')
#
#         self.assertEqual(response.status_code, 201,
#                          "Accepted and processed uploaded Submission Contents")
#
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
#         upload_data: Dict[str, Any] = json.loads(response.data)
#
#         self.assertEqual(upload_data['source_format'], "html",
#                          ("Check source format of HTML submission."
#                           f" [ID={self.upload_id}]"))
#
#         # DONE TESTS, NOW CLEANUP
#
#         # Delete the workspace
#
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
#         # At this point workspace has been removed/deleted.
