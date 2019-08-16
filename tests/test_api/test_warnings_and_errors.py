"""Tests related to warning and error logic."""

import os
import json
import shutil
import tempfile
import logging
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
from filemanager.domain import Workspace, Readiness

from .util import generate_token

logger = logging.getLogger(__name__)
logger.setLevel(int(os.environ.get('LOGLEVEL', '20')))


class TestUploadingPackageWithLotsOfWarningsAndErrors(TestCase):
    """Test warning/error behavior with a problematic upload package."""

    DATA_PATH = os.path.join(os.path.split(os.path.abspath(__file__))[0], '..')

    def setUp(self) -> None:
        """Initialize the app, and upload a package with errors/warnings."""
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

        self.response_data = json.loads(response.data)
        self.upload_id = self.response_data['upload_id']
        try:
            jsonschema.validate(self.response_data, self.schema)
        except jsonschema.exceptions.SchemaError as e:
            self.fail(e)

    def tearDown(self):
        """Delete the workspace."""
        shutil.rmtree(self.workdir)

    def test_readiness_state(self):
        """The workspace should be in an error state."""
        self.assertIn('readiness', self.response_data, 'Indicates readiness')

        # TODO: the original tests had this expectation of `ERROR` state, based
        # on the presence of a .doc file. But it also removed the .doc file,
        # which would put us in ``READY_WITH_WARNINGS``. Need a bit more
        # clarity about the relationship between file removal and error/warning
        # states. For now, disabling removal so that these tests pass and the
        # error message is shown (see
        # ``process/checks/errata/RemoveDOCFiles.py``).
        #  -- Erick 2019-06-25
        #
        self.assertEqual(self.response_data['readiness'],
                         Readiness.ERRORS.value,
                         'Workspace has errors')
        self.assertEqual(self.response_data['source_format'], 'tex')

    def test_warnings_and_errors(self) -> None:
        """This test currently exercises warnings and errors logic."""
        # Organize errors and files so that we can make assertions more easily.
        warnings = defaultdict(list)
        errors_fatal = defaultdict(list)
        info_errors = defaultdict(list)
        for level, name, msg in self.response_data['errors']:
            if level == 'warn':
                warnings[name].append(msg)
            elif level == 'fatal':
                errors_fatal[name].append(msg)
            elif level == 'info':
                info_errors[name].append(msg)
        files = {f['name']: f for f in self.response_data['files']}

        self.assertIn("Removed file 'remove.desc' [File not allowed].",
                      info_errors['remove.desc'])
        self.assertNotIn('remove.desc', files, 'File ware removed')

        self.assertIn("Removed file '.junk' [File not allowed].",
                      info_errors['.junk'])
        self.assertNotIn('.junk', files, 'File was removed')

        self.assertIn("Removed file 'core' [File not allowed].",
                      info_errors['core'])
        self.assertNotIn('core', files, 'File was removed')

        self.assertIn("Removed standard style files for Paul",
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
            "Removed file 'aa.dem' on the assumption that it is the example "
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
                      ' '.join(errors_fatal['something.doc']))

        self.assertIn("Removed file 'final.synctex'.",
                      ' '.join(info_errors['final.synctex']))
        self.assertNotIn('final.synctex', files, 'File was removed')

        self.assertIn("Removed file 'final.out' due to name conflict",
                      ' '.join(info_errors['final.out']))
        self.assertNotIn('final.out', files, 'File was removed')

    # TODO: need some explanation/context for this. Why is this so?
    def test_clear_error_state_with_00READMEXXX(self):
        """Uploading an 00README.XXX file makes the error go away."""
        # Uploaded DOC file is causing fatal error

        # fpath2 = os.path.join(self.DATA_PATH, 'test_files_upload/README.md')
        # fname2 = os.path.basename(fpath2)
        # fname2 = '00README.XXX'   # hmmm?
        # response = self.client.post(f"/filemanager/api/{self.upload_id}",
        #                             data={
        #                                 'file': (open(fpath2, 'rb'), fname2),
        #                             },
        #                             headers={'Authorization': self.token},
        #                             content_type='multipart/form-data')
        # self.assertEqual(response.status_code, status.CREATED,
        #                  "Accepted and processed uploaded Submission Contents")
        response = self.client.delete(
            f"/filemanager/api/{self.upload_id}/something.doc",
            headers={'Authorization': self.token},
            content_type='multipart/form-data'
        )
        self.assertEqual(response.status_code, status.OK, 'File is deleted')

        response = self.client.get(
            f"/filemanager/api/{self.upload_id}",
            headers={'Authorization': self.token},
            content_type='multipart/form-data'
        )
        response_data = json.loads(response.data)
        self.assertEqual(response_data['source_format'], 'tex')
        self.assertEqual(response_data['readiness'], Readiness.READY.value,
                         'Status returned to `READY`; removed file causing'
                         ' fatal error.')

    def test_upload_files_that_we_will_warn_about_but_not_remove(self):
        """Upload files that we will warn about - but not remove."""

        fpath2 = os.path.join(self.DATA_PATH,
                              'test_files_upload/FilesToWarnAbout.tar')
        fname2 = os.path.basename(fpath2)
        response = self.client.post(f"/filemanager/api/{self.upload_id}",
                                    data={
                                        'file': (open(fpath2, 'rb'), fname2),
                                    },
                                    headers={'Authorization': self.token},
                                    content_type='multipart/form-data')

        response_data = json.loads(response.data)

        # Organize errors and files so that we can make assertions more easily.
        warnings = defaultdict(list)
        errors_fatal = defaultdict(list)
        info_errors = defaultdict(list)
        for level, name, msg in response_data['errors']:
            if level == 'warn':
                warnings[name].append(msg)
            elif level == 'fatal':
                errors_fatal[name].append(msg)
            elif level == 'info':
                info_errors[name].append(msg)

        # Normal emacs backup file
        self.assertIn("File 'submission.tex~' may be a backup file. "
                      "Please inspect and remove extraneous backup files.",
                      warnings['submission.tex_'])

        self.assertIn("Renamed submission.tex~ to submission.tex_",
                      warnings['submission.tex_'])

        # Another backup file
        self.assertIn("File 'submission.tex.bak' may be a backup file. "
                      "Please inspect and remove extraneous backup files.",
                      warnings['submission.tex.bak'])
