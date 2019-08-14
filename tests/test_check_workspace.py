"""Runs checks against an :class:`.UploadWorkspace`."""

import os
import re
import tempfile
import shutil
import filecmp
from datetime import datetime

from unittest import TestCase, mock

from filemanager.domain import UploadWorkspace, UploadedFile, FileType
from filemanager.process.strategy import SynchronousCheckingStrategy
from filemanager.process.check import get_default_checkers, cleanup, \
    FixFileExtensions
from filemanager.process.util import unmacify
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
            owner_user_id='98765',
            created_datetime=datetime.now(),
            modified_datetime=datetime.now(),
            strategy=SynchronousCheckingStrategy(),
            storage=SimpleStorageAdapter(self.base_path),
            checkers=get_default_checkers()
        )
        self.workspace.initialize()

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
        self.assertFalse(self.workspace.has_fatal_errors)


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
            owner_user_id='98765',
            created_datetime=datetime.now(),
            modified_datetime=datetime.now(),
            strategy=SynchronousCheckingStrategy(),
            storage=SimpleStorageAdapter(self.base_path),
            checkers=get_default_checkers()
        )
        self.workspace.initialize()

    def tearDown(self):
        """Remove the temporary directory for files."""
        shutil.rmtree(self.base_path)

    def write_upload(self, relpath, altname=None,
                     file_type=FileType.UNKNOWN):
        """
        Write the upload into the workspace.

        We'll use a similar pattern when doing this in Flask.
        """
        filepath = os.path.join(self.DATA_PATH, relpath)
        if altname is None and '/' in relpath:
            filename = relpath.split('/')[1]
        elif altname is None:
            filename = relpath
        else:
            filename = altname
        new_file = self.workspace.create(filename, file_type=file_type)
        with self.workspace.open(new_file, 'wb') as dest:
            with open(filepath, 'rb') as source:
                dest.write(source.read())
        return new_file


class TestSingleFileSubmissions(WorkspaceTestCase):
    """Test some basic single-file source packages."""

    def test_single_file_pdf_submission(self):
        """Test checking a normal single-file PDF submission."""
        self.write_upload('test_files_upload/upload5.pdf')
        self.workspace.perform_checks()
        self.assertEqual(self.workspace.source_type,
                         UploadWorkspace.SourceType.PDF,
                         'Source type is PDF')
        self.assertFalse(self.workspace.has_fatal_errors)

    def test_single_file_tex_submission(self):
        """Test checking a normal single-file 'TeX' submission."""
        self.write_upload('type_test_files/minMac.tex')
        self.workspace.perform_checks()
        self.assertEqual(self.workspace.source_type,
                         UploadWorkspace.SourceType.TEX,
                         'Source type is TEX')
        self.assertFalse(self.workspace.has_fatal_errors)
        counts = self.workspace.get_file_type_counts()
        self.assertEqual(counts[FileType.LATEX2e], 1)

    def test_single_file_ps_submission(self):
        """Test checking a normal single-file 'Postscript' submission."""
        self.write_upload('type_test_files/one.ps')
        self.workspace.perform_checks()
        self.assertEqual(self.workspace.source_type,
                         UploadWorkspace.SourceType.POSTSCRIPT,
                         'Source type is POSTSCRIPT')
        self.assertFalse(self.workspace.has_fatal_errors)
        counts = self.workspace.get_file_type_counts()
        self.assertEqual(counts[FileType.POSTSCRIPT], 1)

    def test_another_single_file_ps_submission(self):
        """Test checking a normal single-file 'Postscript' submission."""
        self.write_upload('test_files_sub_type/sampleA.ps')
        self.workspace.perform_checks()
        self.assertEqual(self.workspace.source_type,
                         UploadWorkspace.SourceType.POSTSCRIPT,
                         'Source type is POSTSCRIPT')
        self.assertFalse(self.workspace.has_fatal_errors)
        counts = self.workspace.get_file_type_counts()
        self.assertEqual(counts[FileType.POSTSCRIPT], 1)

    def test_single_file_html_submission(self):
        """Test checking a normal single-file 'HTML' submission."""
        self.write_upload('test_files_sub_type/sampleA.html')
        self.workspace.perform_checks()
        self.assertEqual(self.workspace.source_type,
                         UploadWorkspace.SourceType.HTML,
                         'Source type is HTML')
        self.assertFalse(self.workspace.has_fatal_errors)
        counts = self.workspace.get_file_type_counts()
        self.assertEqual(counts[FileType.HTML], 1)

    def test_single_file_docx_submission(self):
        """Test checking invalid single-file 'DOCX' submission."""
        self.write_upload('test_files_sub_type/sampleA.docx')
        self.workspace.perform_checks()
        self.assertEqual(self.workspace.source_type,
                         UploadWorkspace.SourceType.INVALID,
                         'Source type is INVALID')
        self.assertTrue(self.workspace.has_fatal_errors,
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
        self.assertTrue(self.workspace.has_fatal_errors,
                        'ODT submissions are not allowed')
        counts = self.workspace.get_file_type_counts()
        self.assertEqual(counts[FileType.ODF], 1)

    def test_single_file_eps_submission(self):
        """Test checking invalid single-file 'EPS' submission."""
        from pprint import pprint
        self.write_upload('type_test_files/dos_eps_1.eps')
        self.workspace.perform_checks()
        self.assertEqual(self.workspace.source_type,
                         UploadWorkspace.SourceType.INVALID,
                         'Source type is INVALID')
        self.assertTrue(self.workspace.has_fatal_errors,
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
        self.assertTrue(self.workspace.has_fatal_errors,
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
        self.assertFalse(self.workspace.has_fatal_errors,
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
        self.assertFalse(self.workspace.has_fatal_errors,
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
        self.assertFalse(self.workspace.has_fatal_errors,
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
        self.assertFalse(self.workspace.has_fatal_errors,
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
        self.assertFalse(self.workspace.has_fatal_errors,
                         'TEX submissions are OK')
        counts = self.workspace.get_file_type_counts()
        self.assertEqual(counts[FileType.TEXAUX], 3)
        self.assertEqual(counts[FileType.PDF], 2)
        self.assertEqual(counts['ancillary'], 16)


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
                      self.workspace.get_warnings_for_path('espcrc2.sty', is_removed=True))

    def test_well_formed_submission(self):
        """Upload is a well-formed submission package."""
        self.write_upload('upload2.tar.gz')
        self.workspace.perform_checks()
        self.assertFalse(self.workspace.has_fatal_errors)

    def test_another_well_formed_submission(self):
        """Upload is a well-formed submission package."""
        self.write_upload('upload3.tar.gz')
        self.workspace.perform_checks()
        self.assertFalse(self.workspace.has_fatal_errors)

    def test_submission_with_warnings(self):
        """Upload is a well-formed submission package."""
        self.write_upload('upload4.gz')
        self.workspace.perform_checks()
        self.assertTrue(self.workspace.has_warnings)
        self.assertIn("Renamed 'upload4.gz' to 'upload4'.",
                      self.workspace.get_warnings_for_path('upload4'))
        self.assertTrue(self.workspace.has_fatal_errors)

    def test_yet_another_well_formed_submission(self):
        """Upload is a well-formed submission package."""
        self.write_upload('upload5.tar.gz')
        self.workspace.perform_checks()
        self.assertFalse(self.workspace.has_fatal_errors)

    def test_a_tgz_file(self):
        """
        Upload is a well-formed submission package.

        .tgz file because of Archive::Extrat/gzip bug
        """
        self.write_upload('upload6.tgz')
        self.workspace.perform_checks()
        self.assertFalse(self.workspace.has_fatal_errors)


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
                      self.workspace.get_warnings_for_path('jz2.zip'))

    def test_contains_top_level_directory(self):
        """Contains a top-level directory."""
        self.write_upload('upload7.tar.gz')
        self.workspace.perform_checks()
        self.assertTrue(self.workspace.has_warnings)
        self.assertIn(
            'Removed top level directory',
            self.workspace.get_warnings_for_path('index_files/',
                                                 is_removed=True)
        )
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
        self.assertIn(
            'Removed top level directory',
            self.workspace.get_warnings_for_path('source/', is_removed=True)
        )
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
                      self.workspace.get_warnings_for_path('windows.txt'))

    def test_contains_illegal_filenames(self):
        """Contains really bad filenames."""
        self.write_upload('Upload9BadFileNames.tar.gz')
        self.workspace.perform_checks()
        self.assertTrue(self.workspace.has_warnings)
        self.assertIn('Renamed 10-1-1(63).png to 10-1-1_63_.png',
                      self.workspace.get_warnings_for_path('10-1-1_63_.png'))


class TestUnpack(WorkspaceTestCase):
    """Tests related to unpacking uploads."""

    def test_macosx_hidden_directory(self):
        """Test detection and removal of __MACOSX directory."""
        self.write_upload('test_files_unpack/with__MACOSX_hidden.tar.gz')
        self.workspace.perform_checks()
        self.assertTrue(self.workspace.has_warnings)
        self.assertIn(
            "Removed '__MACOSX' directory.",
            self.workspace.get_warnings_for_path('__MACOSX/', is_removed=True)
        )

    def test_processed_directory(self):
        """Test detection and warning about 'processed' directory."""
        self.write_upload('test_files_unpack/with__processed_directory.tar.gz')
        self.workspace.perform_checks()
        self.assertTrue(self.workspace.has_warnings)
        self.assertIn("Detected 'processed' directory. Please check.",
                      self.workspace.get_warnings_for_path('processed/'))


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
                      self.workspace.get_warnings_for_path('NoNewlineTermination.tex'))


class TestStrip(WorkspaceTestCase):
    """Cleanup tests."""

    DATA_PATH = os.path.join(os.path.split(os.path.abspath(__file__))[0],
                             'test_files_strip_postscript')

    def test_strip_preview(self):
        """Preview is removed from EPS file."""
        self.write_upload('PostscriptPhotoshop1.eps',)
        self.workspace.perform_checks()

        self.assertTrue(self.workspace.exists('PostscriptPhotoshop1.ps'),
                        'EPS file is renamed to have .ps extension')
        expected_warning = (
            'Unnecessary Preview removed from \'PostscriptPhotoshop1.ps\''
            ' from line 10 to line 202, reduced from 185586 bytes'
            ' to 172746 bytes (see http://arxiv.org/help/sizes)'
        )
        self.assertIn(expected_warning,
                      self.workspace.get_warnings_for_path('PostscriptPhotoshop1.ps'))

        result_path = self.workspace.get_full_path('PostscriptPhotoshop1.ps')
        expected_path = os.path.join(self.DATA_PATH,
                                     'PostscriptPhotoshop1_stripped.eps')
        self.assertTrue(filecmp.cmp(result_path, expected_path, shallow=False),
                        'Resulting content has preview stripped')

    def test_strip_photoshop(self):
        """Photoshop segment is removed from EPS file."""
        self.write_upload('PostscriptPhotoshop2.eps',)
        self.workspace.perform_checks()

        self.assertTrue(self.workspace.exists('PostscriptPhotoshop2.ps'),
                        'EPS file is renamed to have .ps extension')
        expected_warning = (
            'Unnecessary Photoshop removed from \'PostscriptPhotoshop2.ps\''
            ' from line 16 to line 205, reduced from 106009 bytes'
            ' to 93377 bytes (see http://arxiv.org/help/sizes)'
        )
        self.assertIn(expected_warning,
                      self.workspace.get_warnings_for_path('PostscriptPhotoshop2.ps'))

        result_path = self.workspace.get_full_path('PostscriptPhotoshop2.ps')
        expected_path = os.path.join(self.DATA_PATH,
                                     'PostscriptPhotoshop2_stripped.eps')
        self.assertTrue(filecmp.cmp(result_path, expected_path, shallow=False),
                        'Resulting content has preview stripped')

    def test_strip_another_photoshop(self):
        """Photoshop segment is removed from EPS file."""
        self.write_upload('PostscriptPhotoshop3.eps',)
        self.workspace.perform_checks()

        self.assertTrue(self.workspace.exists('PostscriptPhotoshop3.ps'),
                        'EPS file is renamed to have .ps extension')
        expected_warning = (
            'Unnecessary Photoshop removed from \'PostscriptPhotoshop3.ps\''
            ' from line 7 to line 12, reduced from 1273694 bytes'
            ' to 1273439 bytes (see http://arxiv.org/help/sizes)'
        )
        self.assertIn(expected_warning,
                      self.workspace.get_warnings_for_path('PostscriptPhotoshop3.ps'))

        result_path = self.workspace.get_full_path('PostscriptPhotoshop3.ps')
        expected_path = os.path.join(self.DATA_PATH,
                                     'PostscriptPhotoshop3_stripped.eps')
        self.assertTrue(filecmp.cmp(result_path, expected_path, shallow=False),
                        'Resulting content has preview stripped')

    def test_strip_another_preview(self):
        """Preview segment is removed from EPS file."""
        self.write_upload('PostscriptPreview1.eps',)
        self.workspace.perform_checks()

        self.assertTrue(self.workspace.exists('PostscriptPreview1.ps'),
                        'EPS file is renamed to have .ps extension')
        expected_warning = (
            'Unnecessary Preview removed from \'PostscriptPreview1.ps\''
            ' from line 13 to line 7131, reduced from 632668 bytes'
            ' to 81123 bytes (see http://arxiv.org/help/sizes)'
        )
        self.assertIn(expected_warning,
                      self.workspace.get_warnings_for_path('PostscriptPreview1.ps'))

        result_path = self.workspace.get_full_path('PostscriptPreview1.ps')
        expected_path = os.path.join(self.DATA_PATH,
                                     'PostscriptPreview1_stripped.eps')
        self.assertTrue(filecmp.cmp(result_path, expected_path, shallow=False),
                        'Resulting content has preview stripped')

    def test_strip_yet_another_preview(self):
        """Preview segment is removed from EPS file."""
        self.write_upload('PostscriptPreview2.eps',)
        self.workspace.perform_checks()

        self.assertTrue(self.workspace.exists('PostscriptPreview2.ps'),
                        'EPS file is renamed to have .ps extension')
        expected_warning = (
            'Unnecessary Preview removed from \'PostscriptPreview2.ps\''
            ' from line 10 to line 118, reduced from 425356 bytes'
            ' to 418144 bytes (see http://arxiv.org/help/sizes)'
        )
        self.assertIn(expected_warning,
                      self.workspace.get_warnings_for_path('PostscriptPreview2.ps'))

        result_path = self.workspace.get_full_path('PostscriptPreview2.ps')
        expected_path = os.path.join(self.DATA_PATH,
                                     'PostscriptPreview2_stripped.eps')
        self.assertTrue(filecmp.cmp(result_path, expected_path, shallow=False),
                        'Resulting content has preview stripped')

    def test_strip_thumbnail(self):
        """Thumbnail segment is removed from EPS file."""
        self.write_upload('PostscriptThumbnail1.eps',)
        self.workspace.perform_checks()

        self.assertTrue(self.workspace.exists('PostscriptThumbnail1.ps'),
                        'EPS file is renamed to have .ps extension')
        expected_warning = (
            'Unnecessary Thumbnail removed from \'PostscriptThumbnail1.ps\''
            ' from line 38 to line 189, reduced from 68932 bytes'
            ' to 59657 bytes (see http://arxiv.org/help/sizes)'
        )
        self.assertIn(expected_warning,
                      self.workspace.get_warnings_for_path('PostscriptThumbnail1.ps'))

        result_path = self.workspace.get_full_path('PostscriptThumbnail1.ps')
        expected_path = os.path.join(self.DATA_PATH,
                                     'PostscriptThumbnail1_stripped.eps')
        self.assertTrue(filecmp.cmp(result_path, expected_path, shallow=False),
                        'Resulting content has preview stripped')

    def test_strip_another_thumbnail(self):
        """Thumbnail segment is removed from EPS file."""
        self.write_upload('PostscriptThumbnail2.eps',)
        self.workspace.perform_checks()

        self.assertTrue(self.workspace.exists('PostscriptThumbnail2.ps'),
                        'EPS file is renamed to have .ps extension')
        expected_warning = (
            'Unnecessary Thumbnail removed from \'PostscriptThumbnail2.ps\''
            ' from line 40 to line 177, reduced from 79180 bytes'
            ' to 70771 bytes (see http://arxiv.org/help/sizes)'
        )
        self.assertIn(expected_warning,
                      self.workspace.get_warnings_for_path('PostscriptThumbnail2.ps'))

        result_path = self.workspace.get_full_path('PostscriptThumbnail2.ps')
        expected_path = os.path.join(self.DATA_PATH,
                                     'PostscriptThumbnail2_stripped.eps')
        self.assertTrue(filecmp.cmp(result_path, expected_path, shallow=False),
                        'Resulting content has preview stripped')

    # These tests come from legacy system and were part of test bundle with
    # other test files (like embedded font inclusion)
    # data/files_for_testing.tar.gz
    def test_strip_yyet_another_preview(self):
        """Preview segment is removed from EPS file."""
        self.write_upload('P11_cmplx_plane.eps',)
        self.workspace.perform_checks()

        self.assertTrue(self.workspace.exists('P11_cmplx_plane.ps'),
                        'EPS file is renamed to have .ps extension')
        expected_warning = (
            'Unnecessary Preview removed from \'P11_cmplx_plane.ps\''
            ' from line 9 to line 157, reduced from 59684 bytes'
            ' to 48174 bytes (see http://arxiv.org/help/sizes)'
        )
        self.assertIn(expected_warning,
                      self.workspace.get_warnings_for_path('P11_cmplx_plane.ps'))

        result_path = self.workspace.get_full_path('P11_cmplx_plane.ps')
        expected_path = os.path.join(self.DATA_PATH,
                                     'P11_cmplx_plane_stripped.eps')
        self.assertTrue(filecmp.cmp(result_path, expected_path, shallow=False),
                        'Resulting content has preview stripped')

    def test_strip_yyyet_another_preview(self):
        """Preview segment is removed from EPS file."""
        self.write_upload('cone.eps',)
        self.workspace.perform_checks()

        self.assertTrue(self.workspace.exists('cone.ps'),
                        'EPS file is renamed to have .ps extension')
        expected_warning = (
            'Unnecessary Photoshop removed from \'cone.ps\''
            ' from line 14 to line 207, reduced from 1701570 bytes'
            ' to 1688730 bytes (see http://arxiv.org/help/sizes)'
        )
        self.assertIn(expected_warning,
                      self.workspace.get_warnings_for_path('cone.ps'))

        result_path = self.workspace.get_full_path('cone.ps')
        expected_path = os.path.join(self.DATA_PATH,
                                     'cone_stripped.eps')
        self.assertTrue(filecmp.cmp(result_path, expected_path, shallow=False),
                        'Resulting content has preview stripped')


# TODO: theis should be moved to a separate test file.
class TestCheckFileTermination(WorkspaceTestCase):
    """Test the filtering of unwanted characters from the end of file."""

    DATA_PATH = os.path.join(os.path.split(os.path.abspath(__file__))[0],
                             'test_files_upload')

    def test_check_termination(self):
        """Eliminate unwanted CR characters from DOS file."""
        f = self.write_upload('terminators1.txt')
        unmacify.check_file_termination(self.workspace, f)
        expected_path = os.path.join(self.DATA_PATH,
                                     'terminators1stripped.txt')
        result_path = self.workspace.get_full_path('terminators1.txt')
        self.assertTrue(filecmp.cmp(result_path, expected_path, shallow=False),
                        'Unwanted CR characters removed from DOS file.')

    def test_check_more_termination(self):
        """Eliminate unwanted CR characters from DOS file."""
        f = self.write_upload('terminators2.txt')
        unmacify.check_file_termination(self.workspace, f)
        expected_path = os.path.join(self.DATA_PATH,
                                     'terminators2stripped.txt')
        result_path = self.workspace.get_full_path('terminators2.txt')
        self.assertTrue(filecmp.cmp(result_path, expected_path, shallow=False),
                        'Unwanted CR characters removed from DOS file.')

    def test_check_even_more_termination(self):
        """Eliminate unwanted CR characters from DOS file."""
        f = self.write_upload('terminators3.txt')
        unmacify.check_file_termination(self.workspace, f)
        # TODO: lacks an assertion.

    def test_check_PC_eps(self):
        """Eliminate unwanted EOT terminators."""
        f = self.write_upload('BeforeUnPCify.eps')
        unmacify.check_file_termination(self.workspace, f)
        expected_path = os.path.join(self.DATA_PATH,
                                     'AfterTermUnPCify.eps')
        result_path = self.workspace.get_full_path('BeforeUnPCify.eps')
        self.assertTrue(filecmp.cmp(result_path, expected_path, shallow=False),
                        'Eliminated unwanted EOT terminators.')

    def test_check_another_PC_eps(self):
        """Eliminate unwanted EOT terminators."""
        f = self.write_upload('BeforeUnPCify2.eps')
        unmacify.check_file_termination(self.workspace, f)
        expected_path = os.path.join(self.DATA_PATH,
                                     'AfterTermUnPCify2.eps')
        result_path = self.workspace.get_full_path('BeforeUnPCify2.eps')
        self.assertTrue(filecmp.cmp(result_path, expected_path, shallow=False),
                        'Eliminated unwanted EOT terminators.')


# TODO: these should be in a separate test module. --Erick 2019-06-12
class TestUnMacify(WorkspaceTestCase):
    """Test the filtering of unwanted CR characters from specified file.."""

    DATA_PATH = os.path.join(os.path.split(os.path.abspath(__file__))[0],
                             'test_files_upload')

    def has_cr(self, path: str) -> bool:
        """Check whether file has CR characters."""
        with open(path, 'rb') as f:
            for line in f:
                if re.search(b'\r\n?', line) is not None:
                    return True
        return False

    def test_unpcify_file(self):
        """Remove carriage return characters from a PC file."""
        f = self.write_upload('BeforeUnPCify.eps')
        unmacify.unmacify(self.workspace, f)

        result_path = self.workspace.get_full_path('BeforeUnPCify.eps')
        expected_path = os.path.join(self.DATA_PATH, 'AfterUnPCify.eps')
        self.assertTrue(self.has_cr(os.path.join(self.DATA_PATH,
                                                 'BeforeUnPCify.eps')))
        self.assertFalse(self.has_cr(result_path))
        self.assertFalse(self.has_cr(expected_path))
        self.assertTrue(filecmp.cmp(result_path, expected_path, shallow=False),
                        'Eliminated unwanted CR characters.')

    def test_unmacify_file(self):
        """Remove carriage return characters from a MAC file."""
        f = self.write_upload('BeforeUnMACify.eps')
        unmacify.unmacify(self.workspace, f)

        result_path = self.workspace.get_full_path('BeforeUnMACify.eps')
        expected_path = os.path.join(self.DATA_PATH, 'AfterUnMACify.eps')
        self.assertTrue(self.has_cr(os.path.join(self.DATA_PATH,
                                                 'BeforeUnMACify.eps')))
        self.assertFalse(self.has_cr(result_path))
        self.assertFalse(self.has_cr(expected_path))
        self.assertTrue(filecmp.cmp(result_path, expected_path, shallow=False),
                        'Eliminated unwanted CR characters.')


class TestFileExtensions(WorkspaceTestCase):
    """
    Test normalization of file extension for file type.

    Some formats support multiple file nanme suffixes. We want to normalize
    all files of a particular type to have the desired extension. An
    example of this is .htm and .html extensions for files of type HTML.

    For this test we will work with specific files in temporary directory.
    """

    DATA_PATH = os.path.split(os.path.abspath(__file__))[0]
    check = FixFileExtensions()

    def test_fix_postscript_file_extension(self):
        """Postscript file extensions are normalized to ``.ps``."""
        f = self.write_upload('test_files_upload/BeforeUnPCify.eps',
                              'BeforeUnPCify.testex',
                              file_type=FileType.POSTSCRIPT)
        self.assertEqual(f.ext, 'testex')
        f = self.check(self.workspace, f)
        self.assertEqual(f.ext, 'ps')

    def test_fix_html_file_extension(self):
        """HTML file extensions are normalized to ``.html``."""
        f = self.write_upload('test_files_sub_type/sampleA.html',
                              'sampleA.HTM',
                              file_type=FileType.HTML)
        self.assertEqual(f.ext, 'HTM')
        f = self.check(self.workspace, f)
        self.assertEqual(f.ext, 'html')

    def test_fix_pdf_file_extension(self):
        """HTML file extensions are normalized to ``.html``."""
        f = self.write_upload('test_files_sub_type/upload5.pdf',
                              'upload5.fdp',
                              file_type=FileType.PDF)
        self.assertEqual(f.ext, 'fdp')
        f = self.check(self.workspace, f)
        self.assertEqual(f.ext, 'pdf')


# Does this belong with a set of unpack tests (did not exist in legacy system
# but evidence that someone was collecting files to use as part of unpack tests
# - may need to refactor in future.
class TestProcessUploadWithSubdirectories(WorkspaceTestCase):
    """Try to process archive with multiple gzipped archives embedded in it."""

    DATA_PATH = os.path.join(os.path.split(os.path.abspath(__file__))[0],
                             'test_files_upload')

    def test_process_subdirectories(self):
        """Process archive with multiple gzipped archives embedded in it."""
        self.write_upload('UnpackWithSubdirectories.tar.gz')
        self.workspace.perform_checks()
        self.assertTrue(self.workspace.exists('b/c/'),
                        'Test subdirectory exists: b/c')
        self.assertTrue(self.workspace.exists('b/c/c_level_file.txt'),
                        'Test file within subdirectory exists:'
                        ' b/c/c_level_file.txt')


class TestProcessCountFileTypes(WorkspaceTestCase):
    """Test routine that counts file type occurrences."""

    def test_normal_submission_with_lots_of_files(self):
        """Upload normal submission with lots of files."""
        self.write_upload('test_files_upload/UploadWithANCDirectory.tar.gz')
        self.workspace.perform_checks()
        counts = self.workspace.get_file_type_counts()
        self.assertEqual(counts['all_files'], 22,
                         "Total number of files matches.")
        self.assertEqual(counts['files'], 6,
                         "Total number of files matches.")
        self.assertEqual(counts['ancillary'], 16,
                         "Total number of files matches.")
        self.assertEqual(counts[FileType.PDF], 2,
                         "Total number of files matches.")
        self.assertEqual(counts[FileType.TEXAUX], 3,
                         "Total number of files matches.")
        self.assertFalse(self.workspace.is_single_file_submission)
        self.assertIsNone(self.workspace.get_single_file())

    def test_single_invalid_sub_file(self):
        """Upload single invalid sub file."""
        self.write_upload('test_files_sub_type/sampleA.docx')
        self.workspace.perform_checks()
        counts = self.workspace.get_file_type_counts()
        self.assertEqual(counts['all_files'], 1,
                         "Total number of files matches.")
        self.assertEqual(counts['files'], 1,
                         "Total number of files matches.")
        self.assertEqual(counts[FileType.DOCX], 1,
                         "Number of docx files matches.")
        self.assertTrue(self.workspace.is_single_file_submission)
        self.assertIsNotNone(self.workspace.get_single_file())

    def test_single_invalid_file(self):
        """Upload single invalid file."""
        self.write_upload('test_files_sub_type/head.tmp')
        self.workspace.perform_checks()
        counts = self.workspace.get_file_type_counts()
        self.assertEqual(counts['all_files'], 1,
                         "Total number of files matches.")
        self.assertEqual(counts['files'], 1,
                         "Total number of files matches.")
        self.assertEqual(counts['ignore'], 1,
                         "Number of ignore files matches.")
        self.assertFalse(self.workspace.is_single_file_submission)
        self.assertIsNone(self.workspace.get_single_file())

    def test_only_ancillary_files(self):
        """Upload no source files - ancillary files only."""
        self.write_upload('test_files_sub_type/onlyANCfiles.tar.gz')
        self.workspace.perform_checks()
        counts = self.workspace.get_file_type_counts()
        self.assertEqual(counts['all_files'], 16,
                         "Total number of files matches.")
        self.assertEqual(counts['files'], 0,
                         "Total number of files matches.")
        self.assertEqual(counts['ancillary'], 16,
                         "Total number of ancillary files matches.")
        self.assertFalse(self.workspace.is_single_file_submission)
        self.assertIsNone(self.workspace.get_single_file())

    def test_good_single_file_submission(self):
        """Upload an acceptable single file submission."""
        self.write_upload('test_files_upload/upload5.pdf')
        self.workspace.perform_checks()
        counts = self.workspace.get_file_type_counts()
        self.assertEqual(counts['all_files'], 1,
                         "Total number of files matches.")
        self.assertEqual(counts['files'], 1,
                         "Total number of files matches.")
        self.assertEqual(counts['ancillary'], 0,
                         "Total number of ancillary files matches.")
        self.assertEqual(counts[FileType.PDF], 1,
                         "Number of PDF files matches.")
        self.assertTrue(self.workspace.is_single_file_submission)
        self.assertIsNotNone(self.workspace.get_single_file())


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
#             owner_user_id='98765',
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
#         self.assertTrue(workspace.has_fatal_errors)
