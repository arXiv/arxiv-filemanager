"""Runs checks against an :class:`.UploadWorkspace`."""

import os
import tempfile
import shutil
from datetime import datetime

from unittest import TestCase, mock

from filemanager.domain import UploadWorkspace, UploadedFile, FileType
from filemanager.process.strategy import SynchronousCheckingStrategy
from filemanager.process.check import get_default_checkers
from filemanager.services.storage import SimpleStorageAdapter

parent, _ = os.path.split(os.path.abspath(__file__))


class TestTarGZUpload(TestCase):
    """Test checking a workspace with an uploaded tar.gz file."""

    DATA_PATH = os.path.join(os.path.split(os.path.abspath(__file__))[0],
                             'test_files_upload')

    def setUp(self):
        """We have a workspace."""
        self.base_path = tempfile.mkdtemp()
        self.upload_id = 5432
        self.workspace_path = os.path.join(self.base_path, str(self.upload_id))
        os.makedirs(self.workspace_path)

        self.workspace = UploadWorkspace(
            upload_id=self.upload_id,
            submission_id=None,
            owner_user_id='98765',
            archive=None,
            created_datetime=datetime.now(),
            modified_datetime=datetime.now(),
            strategy=SynchronousCheckingStrategy(),
            storage=SimpleStorageAdapter(self.base_path),
            checkers=get_default_checkers()
        )

    def tearDown(self):
        """Remove the temporary directory for files."""
        shutil.rmtree(self.base_path)

    def test_sample(self):
        """Test a TeX sample from an announced e-print."""
        filename = '1801.03879-1.tar.gz'
        filepath = os.path.join(self.DATA_PATH, filename)
        new_file = self.workspace.create(filename)
        with self.workspace.open(new_file, 'wb') as dest:
            with open(filepath, 'rb') as source:
                dest.write(source.read())

        self.workspace.perform_checks()
        type_counts = self.workspace.get_file_type_counts()
        self.assertEqual(self.workspace.file_count, type_counts['all_files'])
        self.assertEqual(type_counts[FileType.TEXAUX], 3)
        self.assertEqual(type_counts[FileType.PDF], 2)
        self.assertEqual(type_counts[FileType.LATEX2e], 1)

        self.assertEqual(self.workspace.source_type,
                         UploadWorkspace.SourceType.TEX,
                         'Upload is TeX')
        self.assertFalse(self.workspace.has_errors)


class WorkspaceTestCase(TestCase):
    """Tooling for testing upload workspace examples."""

    DATA_PATH = os.path.split(os.path.abspath(__file__))[0]

    def setUp(self):
        """We have a workspace."""
        self.base_path = tempfile.mkdtemp()
        self.upload_id = 5432
        self.workspace_path = os.path.join(self.base_path, str(self.upload_id))
        os.makedirs(self.workspace_path)

        self.workspace = UploadWorkspace(
            upload_id=self.upload_id,
            submission_id=None,
            owner_user_id='98765',
            archive=None,
            created_datetime=datetime.now(),
            modified_datetime=datetime.now(),
            strategy=SynchronousCheckingStrategy(),
            storage=SimpleStorageAdapter(self.base_path),
            checkers=get_default_checkers()
        )

    def tearDown(self):
        """Remove the temporary directory for files."""
        shutil.rmtree(self.base_path)

    def write_upload(self, relpath):
        """
        Write the upload into the workspace.

        We'll use a similar pattern when doing this in Flask.
        """
        filepath = os.path.join(self.DATA_PATH, relpath)
        if '/' in relpath:
            filename = relpath.split('/')[1]
        else:
            filename = relpath
        new_file = self.workspace.create(filename)
        with self.workspace.open(new_file, 'wb') as dest:
            with open(filepath, 'rb') as source:
                dest.write(source.read())


class TestSingleFileSubmissions(WorkspaceTestCase):
    """Test some basic single-file source packages."""

    def test_single_file_pdf_submission(self):
        """Test checking a normal single-file PDF submission."""
        self.write_upload('test_files_upload/upload5.pdf')
        self.workspace.perform_checks()
        self.assertEqual(self.workspace.source_type,
                         UploadWorkspace.SourceType.PDF,
                         'Source type is PDF')
        self.assertFalse(self.workspace.has_errors)

    def test_single_file_tex_submission(self):
        """Test checking a normal single-file 'TeX' submission."""
        self.write_upload('type_test_files/minMac.tex')
        self.workspace.perform_checks()
        self.assertEqual(self.workspace.source_type,
                         UploadWorkspace.SourceType.TEX,
                         'Source type is TEX')
        self.assertFalse(self.workspace.has_errors)
        counts = self.workspace.get_file_type_counts()
        self.assertEqual(counts[FileType.LATEX2e], 1)

    def test_single_file_ps_submission(self):
        """Test checking a normal single-file 'Postscript' submission."""
        self.write_upload('type_test_files/one.ps')
        self.workspace.perform_checks()
        self.assertEqual(self.workspace.source_type,
                         UploadWorkspace.SourceType.POSTSCRIPT,
                         'Source type is POSTSCRIPT')
        self.assertFalse(self.workspace.has_errors)
        counts = self.workspace.get_file_type_counts()
        self.assertEqual(counts[FileType.POSTSCRIPT], 1)

    def test_another_single_file_ps_submission(self):
        """Test checking a normal single-file 'Postscript' submission."""
        self.write_upload('test_files_sub_type/sampleA.ps')
        self.workspace.perform_checks()
        self.assertEqual(self.workspace.source_type,
                         UploadWorkspace.SourceType.POSTSCRIPT,
                         'Source type is POSTSCRIPT')
        self.assertFalse(self.workspace.has_errors)
        counts = self.workspace.get_file_type_counts()
        self.assertEqual(counts[FileType.POSTSCRIPT], 1)

    def test_single_file_html_submission(self):
        """Test checking a normal single-file 'HTML' submission."""
        self.write_upload('test_files_sub_type/sampleA.html')
        self.workspace.perform_checks()
        self.assertEqual(self.workspace.source_type,
                         UploadWorkspace.SourceType.HTML,
                         'Source type is HTML')
        self.assertFalse(self.workspace.has_errors)
        counts = self.workspace.get_file_type_counts()
        self.assertEqual(counts[FileType.HTML], 1)

    def test_single_file_docx_submission(self):
        """Test checking invalid single-file 'DOCX' submission."""
        self.write_upload('test_files_sub_type/sampleA.docx')
        self.workspace.perform_checks()
        self.assertEqual(self.workspace.source_type,
                         UploadWorkspace.SourceType.INVALID,
                         'Source type is INVALID')
        self.assertTrue(self.workspace.has_errors,
                        'DocX submissions are not allowed')
        counts = self.workspace.get_file_type_counts()
        self.assertEqual(counts[FileType.DOCX], 1)

    def test_single_file_odt_submission(self):
        """Test checking invalid single-file 'ODT' submission."""
        self.write_upload('test_files_sub_type/Hellotest.odt')
        self.workspace.perform_checks()
        self.assertEqual(self.workspace.source_type,
                         UploadWorkspace.SourceType.INVALID,
                         'Source type is INVALID')
        self.assertTrue(self.workspace.has_errors,
                        'ODT submissions are not allowed')
        counts = self.workspace.get_file_type_counts()
        self.assertEqual(counts[FileType.ODF], 1)

    def test_single_file_eps_submission(self):
        """Test checking invalid single-file 'EPS' submission."""
        self.write_upload('type_test_files/dos_eps_1.eps')
        self.workspace.perform_checks()
        self.assertEqual(self.workspace.source_type,
                         UploadWorkspace.SourceType.INVALID,
                         'Source type is INVALID')
        self.assertTrue(self.workspace.has_errors,
                        'EPS submissions are not allowed')
        counts = self.workspace.get_file_type_counts()
        self.assertEqual(counts[FileType.DOS_EPS], 1)

    def test_single_file_texaux_submission(self):
        """Test checking invalid single-file 'texaux' submission."""
        self.write_upload('type_test_files/ol.sty')
        self.workspace.perform_checks()
        self.assertEqual(self.workspace.source_type,
                         UploadWorkspace.SourceType.INVALID,
                         'Source type is INVALID')
        self.assertTrue(self.workspace.has_errors,
                        'Texaux submissions are not allowed')
        counts = self.workspace.get_file_type_counts()
        self.assertEqual(counts[FileType.TEXAUX], 1)


class TestMultiFileSubmissions(WorkspaceTestCase):
    """Test some multi-file source packages."""

    def test_multi_file_html_submission(self):
        """Test a typical multi-file 'HTML' submission."""
        self.write_upload('test_files_sub_type/sampleB_html.tar.gz')
        self.workspace.perform_checks()
        self.assertEqual(self.workspace.source_type,
                         UploadWorkspace.SourceType.HTML,
                         'Source type is HTML')
        self.assertFalse(self.workspace.has_errors,
                         'HTML submissions are OK')
        counts = self.workspace.get_file_type_counts()
        self.assertEqual(counts[FileType.IMAGE], 6)
        self.assertEqual(counts[FileType.HTML], 1)

    def test_another_multi_file_html_submission(self):
        """Test another typical multi-file 'HTML' submission."""
        self.write_upload('test_files_sub_type/sampleF_html.tar.gz')
        self.workspace.perform_checks()
        counts = self.workspace.get_file_type_counts()
        self.assertEqual(self.workspace.source_type,
                         UploadWorkspace.SourceType.HTML,
                         'Source type is HTML')
        self.assertFalse(self.workspace.has_errors,
                         'HTML submissions are OK')

        self.assertEqual(counts[FileType.IMAGE], 20)
        self.assertEqual(counts[FileType.HTML], 1)

    def test_tex_with_postscript_submission(self):
        """Test a typical multi-file 'TeX w/Postscript' submission."""
        self.write_upload('test_files_sub_type/sampleA_ps.tar.gz')
        self.workspace.perform_checks()
        self.assertEqual(self.workspace.source_type,
                         UploadWorkspace.SourceType.TEX,
                         'Source type is TEX')
        self.assertFalse(self.workspace.has_errors,
                         'TEX submissions are OK')
        counts = self.workspace.get_file_type_counts()
        self.assertEqual(counts[FileType.LATEX2e], 1)
        self.assertEqual(counts[FileType.POSTSCRIPT], 23)

    def test_another_tex_with_postscript_submission(self):
        """Test another typical multi-file 'TeX w/Postscript' submission."""
        self.write_upload('test_files_sub_type/sampleB_ps.tar.gz')
        self.workspace.perform_checks()
        self.assertEqual(self.workspace.source_type,
                         UploadWorkspace.SourceType.TEX,
                         'Source type is TEX')
        self.assertFalse(self.workspace.has_errors,
                         'TEX submissions are OK')
        counts = self.workspace.get_file_type_counts()
        self.assertEqual(counts[FileType.LATEX2e], 1)
        self.assertEqual(counts[FileType.POSTSCRIPT], 4)

    def test_tex_with_ancillary_submission(self):
        """Test a multi-file 'TeX' submission with ancillary files."""
        self.write_upload('test_files_upload/UploadWithANCDirectory.tar.gz')
        self.workspace.perform_checks()
        self.assertEqual(self.workspace.source_type,
                         UploadWorkspace.SourceType.TEX,
                         'Source type is TEX')
        self.assertFalse(self.workspace.has_errors,
                         'TEX submissions are OK')
        counts = self.workspace.get_file_type_counts()
        self.assertEqual(counts[FileType.LATEX2e], 2)
        self.assertEqual(counts[FileType.IMAGE], 9)
        self.assertEqual(counts[FileType.TEXAUX], 5)
        self.assertEqual(counts[FileType.PDF], 4)
        self.assertEqual(counts[FileType.PDFLATEX], 1)


class TestUploadScenarios(WorkspaceTestCase):
    """Test series of uniform cases with specified outcomes."""

    DATA_PATH = os.path.join(os.path.split(os.path.abspath(__file__))[0],
                             'test_files_upload')

    def test_warning_for_empty_file(self):
        """Upload contains an empty file."""
        self.write_upload('upload1.tar.gz')
        self.workspace.perform_checks()
        self.assertTrue(self.workspace.has_warnings)
        self.assertIn("File 'espcrc2.sty' is empty (size is zero).",
                      self.workspace.warnings['espcrc2.sty'])

    def test_well_formed_submission(self):
        """Upload is a well-formed submission package."""
        self.write_upload('upload2.tar.gz')
        self.workspace.perform_checks()
        self.assertFalse(self.workspace.has_warnings)
        self.assertFalse(self.workspace.has_errors)

    def test_another_well_formed_submission(self):
        """Upload is a well-formed submission package."""
        self.write_upload('upload3.tar.gz')
        self.workspace.perform_checks()
        self.assertFalse(self.workspace.has_warnings)
        self.assertFalse(self.workspace.has_errors)

    def test_submission_with_warnings(self):
        """Upload is a well-formed submission package."""
        self.write_upload('upload4.gz')
        self.workspace.perform_checks()
        self.assertTrue(self.workspace.has_warnings)
        self.assertIn("Renaming 'upload4.gz' to 'upload4'.",
                      self.workspace.warnings['upload4'])
        self.assertTrue(self.workspace.has_errors)

    def test_yet_another_well_formed_submission(self):
        """Upload is a well-formed submission package."""
        self.write_upload('upload5.tar.gz')
        self.workspace.perform_checks()
        self.assertFalse(self.workspace.has_warnings)
        self.assertFalse(self.workspace.has_errors)

    def test_a_tgz_file(self):
        """
        Upload is a well-formed submission package.

        .tgz file because of Archive::Extrat/gzip bug
        """
        self.write_upload('upload6.tgz')
        self.workspace.perform_checks()
        self.assertFalse(self.workspace.has_warnings)
        self.assertFalse(self.workspace.has_errors)


class TestNestedArchives(WorkspaceTestCase):
    """Tests for uploads with nested archives."""

    DATA_PATH = os.path.join(os.path.split(os.path.abspath(__file__))[0],
                             'test_files_upload')

    def test_nested_zip_and_tar(self):
        """Nested archives including a corrupted zip file."""
        self.write_upload('upload-nested-zip-and-tar.zip')
        self.workspace.perform_checks()
        self.assertTrue(self.workspace.has_warnings)
        self.assertIn('There were problems unpacking \'jz2.zip\'. Please try'
                      ' again and confirm your files.',
                      self.workspace.warnings['jz2.zip'])

    def test_contains_top_level_directory(self):
        """Contains a top-level directory."""
        self.write_upload('upload7.tar.gz')
        self.workspace.perform_checks()
        self.assertTrue(self.workspace.has_warnings)
        self.assertIn('Removing top level directory',
                      self.workspace.warnings['index_files/'])
        self.workspace.exists('link.gif')
        self.workspace.exists('larrow.gif')
        self.workspace.exists('logo.gif')
        self.workspace.exists('tourbik2.gif')
        self.workspace.exists('bicycle.gif')
        self.workspace.exists('commbike.gif')
        self.workspace.exists('heartcyc.gif')
        # Etc...

    def test_another_contains_top_level_directory(self):
        """Contains a top-level directory."""
        self.write_upload('source_with_dir.tar.gz')
        self.workspace.perform_checks()
        self.assertTrue(self.workspace.has_warnings)
        self.assertIn('Removing top level directory',
                      self.workspace.warnings['source/'])
        self.workspace.exists('draft.tex')


class TestBadFilenames(WorkspaceTestCase):
    """Tests for uploads with bad filenames."""

    DATA_PATH = os.path.join(os.path.split(os.path.abspath(__file__))[0],
                             'test_files_upload')

    def test_contains_windows_filenames(self):
        """Contains windows filenames."""
        self.write_upload('UploadTestWindowCDrive.tar.gz')
        self.workspace.perform_checks()
        self.assertTrue(self.workspace.has_warnings)
        self.assertIn('Renamed c:\\data\\windows.txt to windows.txt',
                      self.workspace.warnings['windows.txt'])

    def test_contains_illegal_filenames(self):
        """Contains really bad filenames."""
        self.write_upload('Upload9BadFileNames.tar.gz')
        self.workspace.perform_checks()
        self.assertTrue(self.workspace.has_warnings)
        self.assertIn('Renamed 10-1-1(63).png to 10_1_1(63).png',
                      self.workspace.warnings['10_1_1(63).png'])


class TestMalformedFiles(WorkspaceTestCase):
    """Tests for uploads with malformed content."""

    DATA_PATH = os.path.join(os.path.split(os.path.abspath(__file__))[0],
                             'test_files_upload')

    def test_no_newline(self):
        """File does not end with newline character."""
        self.write_upload('UploadNoNewlineTerm.tar.gz')
        self.workspace.perform_checks()
        self.assertTrue(self.workspace.has_warnings)
        self.assertIn('File \'NoNewlineTermination.tex\' does not end with'
                      ' newline (\\n), TRUNCATED?',
                      self.workspace.warnings['NoNewlineTermination.tex'])


# TODO: checks for pdfpages documents do not appear to be implemented yet.
# --Erick 2019-06-11.
# class TestPDFPages(TestCase):
#     """
#     Test checking a workspace with pdfpages uploads.
#
#     These submissions are examples of submitters using pdfpagea package to
#     avoid having to include working source files.
#     """
#
#     DATA_PATH = os.path.join(parent, 'test_files_pdfpages')
#
#     examples = [
#         '2211696.tar.gz',
#         '2223445.tar.gz',
#         '2226238.tar.gz',
#         '2229143.tar.gz',
#         '2230466.tar.gz',
#         '2260340.tar.gz',
#     ]
#
#     def setUp(self):
#         """We have a workspace."""
#         self.base_path = tempfile.mkdtemp()
#
#     def new_workspace(self, upload_id):
#         """Create a new workspace."""
#         workspace_path = os.path.join(self.base_path, str(upload_id))
#         os.makedirs(workspace_path)
#
#         return UploadWorkspace(
#             upload_id=upload_id,
#             submission_id=None,
#             owner_user_id='98765',
#             archive=None,
#             created_datetime=datetime.now(),
#             modified_datetime=datetime.now(),
#             strategy=SynchronousCheckingStrategy(),
#             storage=SimpleStorageAdapter(self.base_path),
#             checkers=get_default_checkers()
#         )
#
#     def tearDown(self):
#         """Remove the temporary directory for files."""
#         shutil.rmtree(self.base_path)
#
#     def test_examples(self):
#         """Test each of the examples."""
#         for i, filename in enumerate(self.examples):
#             workspace = self.new_workspace(i)
#             filepath = os.path.join(self.DATA_PATH, filename)
#             new_file = workspace.create(filename)
#             with workspace.open(new_file, 'wb') as dest:
#                 with open(filepath, 'rb') as source:
#                     dest.write(source.read())
#
#         workspace.perform_checks()
#         self.assertTrue(workspace.has_errors)
