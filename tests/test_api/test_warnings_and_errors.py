"""Tests related to warning and error logic."""

import os
import json
import shutil
import tempfile
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


class TestWarningsAndErrors(TestCase):
    """Test warning and error behavior."""

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

    def tearDown(self):
        """Delete the workspace."""
        shutil.rmtree(self.workdir)

    def test_warnings_and_errors(self) -> None:
        """This test currently exercises warnings and errors logic."""#
        fpath = os.path.join(self.DATA_PATH, 
                             'test_files_upload/UploadRemoveFiles.tar')
        fname = os.path.basename(fpath)
        response = self.client.post('/filemanager/api/',
                                    data={
                                        'file': (open(fpath, 'rb'), fname),
                                    },
                                    headers={'Authorization': self.token},
                                    content_type='multipart/form-data')
        self.assertEqual(response.status_code, status.CREATED, 
                         "Accepted and processed uploaded Submission Contents")
        self.maxDiff = None

        response_data = json.loads(response.data)
        try:
            jsonschema.validate(response_data, self.schema)
        except jsonschema.exceptions.SchemaError as e:
            self.fail(e)

        self.assertIn('readiness', response_data, 'Indicates readiness')
        # self.assertEqual(response_data['readiness'], 
        #                  UploadWorkspace.Readiness.ERRORS,
        #                  'Workspace has errors')

        # Make sure we are seeing errors
        warnings = defaultdict(list)
        fatal_errors = defaultdict(list)
        info_errors = defaultdict(list)
        for level, name, msg in response_data['errors']:
            if level == 'warn':
                warnings[name].append(msg)
            elif level == 'fatal':
                fatal_errors[name].append(msg)
            elif level == 'info':
                info_errors[name].append(msg)
        
        files = {f['name']: f for f in response_data['files']}

        self.assertIn("Removed file 'remove.desc' [File not allowed].", 
                      info_errors['remove.desc'])
        self.assertNotIn('remove.desc', files, 'File ware removed')

        self.assertIn("Removed file '.junk' [File not allowed].", 
                      info_errors['.junk'])
        self.assertNotIn('.junk', files, 'File was removed')

        self.assertIn("Removed file 'core' [File not allowed].", 
                      info_errors['core'])
        self.assertNotIn('core', files, 'File was removed')

        self.assertIn("REMOVING standard style files for Paul", 
                      ' '.join(info_errors['diagrams.sty']))
        self.assertNotIn('diagrams.sty', files, 'File was removed')

        self.assertIn("Removed file 'zero.txt' [file is empty].", 
                      info_errors['zero.txt'])
        self.assertNotIn('zero.txt', files, 'File was removed')

        self.assertIn("Removed file 'xxx.cshrc' [File not allowed].", 
                      info_errors['xxx.cshrc'])
        self.assertNotIn('xxx.cshrc', files, 'File was removed')

        self.assertIn("Removed file 'uufiles' [File not allowed].", 
                      info_errors['uufiles'])
        self.assertNotIn('uufiles', files, 'File was removed')

        self.assertIn("Removed file 'final.aux' due to name conflict.", 
                      info_errors['final.aux'])
        self.assertNotIn('final.aux', files, 'File was removed')
        
        self.assertIn("We do not run bibtex in the auto", 
                      ' '.join(warnings['final.bib']))
        self.assertIn(
            "Removed the file 'final.bib'. Using 'final.bbl' for references.", 
            info_errors['final.bib']
        )
        self.assertNotIn('final.bib', files, 'File was removed')

        self.assertIn(
            "Removing file 'aa.dem' on the assumption that it is the example "
            "file for the Astronomy and Astrophysics macro package aa.cls.",
            info_errors['aa.dem']
        )
        self.assertNotIn('aa.dem', files, 'File was removed')

        self.assertIn("WILL REMOVE standard revtex4 style", 
                      ' '.join(info_errors['revtex4.cls']))
        self.assertNotIn('revtex4.cls', files, 'File was removed')

        self.assertIn("Found hyperlink-compatible package 'espcrc2.sty'.", 
                      ' '.join(info_errors['espcrc2.sty']))
        self.assertNotIn('espcrc2.sty', files, 'File was removed')

        self.assertIn("Your submission has been rejected because", 
                      ' '.join(fatal_errors['something.doc']))
        
        self.assertIn("Removed file 'final.synctex'.", 
                      ' '.join(info_errors['final.synctex']))
        self.assertNotIn('final.synctex', files, 'File was removed')

        self.assertIn("Removed file 'final.out' due to name conflict", 
                      ' '.join(info_errors['final.out']))
        self.assertNotIn('final.out', files, 'File was removed')
    
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