"""Tests for :mod:`zero.process.upload`."""

from unittest import TestCase
from datetime import datetime
# from filemanager.domain import Upload
from filemanager.process import upload
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename
from filemanager.arxiv.file import File as File

import os.path
import shutil
import tempfile
import filecmp

from filemanager.process.upload import Upload

UPLOAD_BASE_DIRECTORY = '/tmp/filemanagment/submissions'

TEST_FILES_DIRECTORY = os.path.join(os.getcwd(), 'tests/test_files_upload')
UNPACK_TEST_FILES_DIRECTORY = os.path.join(os.getcwd(), 'tests/test_files_unpack')
TEST_FILES_SUB_TYPE = os.path.join(os.getcwd(),'tests/test_files_sub_type')
TEST_FILES_FILE_TYPE = os.path.join(os.getcwd(), 'tests/type_test_files')

# General upload tests format:
#
#       test_filename, upload_id, warning, warnings_match, description/note/comment/details
#
# Can we use this for errors???
#
# Examples
# upload_tests.append(['1801.03879-1.tar.gz', '20180225', False, '', "Test gzipped tar unpack'"])
# upload_tests.append(['','',False,''])
# upload_tests.append(['filename','identifier',False/True,'Regex', 'Description'])

upload_tests = []

# Basic tests

upload_tests.append(['upload1.tar.gz', '9902.1001', True,
                     "File 'espcrc2.sty' is empty \(size is zero\)",
                     'Test zero file detection'])
upload_tests.append(['upload2.tar.gz', '9903.1002', False, '', 'Test well-formed submission.'])
upload_tests.append(['upload3.tar.gz', '9903.1003', False, '', 'Test well-formed submission.'])
upload_tests.append(['upload4.gz', '9903.1004', True, '', "Renaming 'upload4.gz' to 'upload4'"])
upload_tests.append(['upload5.pdf', '9903.1005', False, '', 'Test well-formed pdf submission.'])
## .tgz file because of Archive::Extrat/gzip bug
upload_tests.append(['upload6.tgz', '9903.1006', False, '', 'Test well-formed submission.'])

# Nested archives
upload_tests.append(['upload-nested-zip-and-tar.zip', '9903.1013', True,
                     'There were problems unpacking "jz2.zip" -- continuing. Please try again and confirm your files.',
                     'Test upload with corrupt zip file'])

# This really needs to be a special test since we need to inspect outcomes.
# upload_tests.append(['UnpackWithSubdirectories.tar.gz', '9903.1014', False, '', 'Test upload with multiple levels'])

#  contains top-level directory
upload_tests.append(['upload7.tar.gz', '9903.1007', True, 'Removing top level directory',
                     'Test removing top level directory.'])

upload_tests.append(['UploadTestWindowCDrive.tar.gz', '12345639', True,
                     r'Renaming c:\\data\\windows\.txt',
                     'Test renaming of Windows filename'])

upload_tests.append(['Upload9BadFileNames.tar.gz', '12345640', True,
                     'Attempting to rename 10-1-1\(63\)\.png to 10-1-1_63_\.png.',
                     'Test for bad/illegal file names.'])

upload_tests.append(['UploadNoNewlineTerm.tar.gz', '9903.10029', True,
                     "File 'NoNewlineTermination.tex' does not end with newline",
                     'File does not end with newline character.'])

upload_tests.append(['source_with_dir.tar.gz', '9903.1009', True, 'Removing top level directory',
                     'Removing top level directory'])

# These tests may eventually migrate to thier own file
unpack_tests = []

unpack_tests.append(['with__MACOSX_hidden.tar.gz', '9912.0001', True,
                     r"Removed '__MACOSX' directory.",
                     'Test detection and removal of __MACOSX directory'])

unpack_tests.append(['with__processed_directory.tar.gz', '9912.0002', True,
                     r"Detected 'processed' directory. Please check.",
                     "Test detection and warning about 'processed' directory"])

# Source Format Tests

test_submissions = []

# Single-file submission (valid) PDF, TEX, Postscript, HTML,
# (invalid) *.docx, *.odf, *.eps, texaux

# valid
test_submissions.append(['upload5.pdf', 'pdf',
                         "Normal single-file 'PDF' submission."])
test_submissions.append(['minMac.tex', 'tex',
                         "Normal single-file 'TeX' submission."])
test_submissions.append(['one.ps', 'postscript',
                         "Normal single-file 'Postscript' submission."])
test_submissions.append(['sampleA.ps', 'postscript',
                         "Normal single-file 'Postscript' submission."])
test_submissions.append(['sampleA.html', 'html',
                         "Normal single-file 'HTML' submission."])
# invalid
test_submissions.append(['sampleA.docx', 'invalid',
                         "Invalid single-file 'DOCX' submission."])
test_submissions.append(['Hellotest.odt', 'invalid',
                         "Invalid single-file 'ODF' submission."])
test_submissions.append(['dos_eps_1.eps', 'invalid',
                         "Invalid single-file 'EPS' submission."])
test_submissions.append(['ol.sty', 'invalid',
                         "Invalid single-file 'texaux' submission."])

# Multi-file submissions (valid) html, postscript, tex (default)
test_submissions.append(['sampleB_html.tar.gz', 'html',
                         "Typical multi-file 'HTML' submission."])
test_submissions.append(['sampleA_ps.tar.gz', 'tex',
                         "Typical multi-file 'TeX w/Postscript' submission."])
test_submissions.append(['sampleB_ps.tar.gz', 'tex',
                         "Typical multi-file 'TeX w/Postscript' submission."])
test_submissions.append(['UploadWithANCDirectory.tar.gz', 'tex',
                         "Typical multi-file 'TeX' submission."])
test_submissions.append(['sampleF_html.tar.gz', 'html',
                         "Typical multi-file 'HTML' submission."])


# Internal Debugging test
class TestInternalSupportRoutines(TestCase):

    def test_get_upload_directory(self):
        upload = Upload(12345678)
        workspace_dir = upload.get_upload_directory()
        self.assertEqual(workspace_dir, os.path.join(UPLOAD_BASE_DIRECTORY, '12345678'),
                         'Generate path to workspace directory')
        # cleanup workspace
        upload.remove_workspace()

    def test_create_upload_directory(self):
        upload = Upload(12345679)
        workspace_dir = upload.create_upload_directory()
        dir_exists = os.path.exists(workspace_dir)
        self.assertEqual(dir_exists, True, 'Create workspace directory.')
        # cleanup workspace
        upload.remove_workspace()

    def test_get_source_directory(self):
        upload = Upload(12345680)
        source_dir = upload.get_source_directory()
        self.assertEqual(source_dir, os.path.join(UPLOAD_BASE_DIRECTORY, '12345680', 'src'),
                         "Check 'src' directory")
        # cleanup workspace
        upload.remove_workspace()

    def test_get_removed_directory(self):
        upload = Upload(12345680)
        removed_dir = upload.get_removed_directory()
        self.assertEqual(removed_dir, os.path.join(UPLOAD_BASE_DIRECTORY, '12345680', 'removed'),
                         "Check 'removed' directory")
        # cleanup workspace
        upload.remove_workspace()

    def test_create_upload_workspace(self):
        upload = Upload(12345681)
        workspace_dir = upload.create_upload_workspace()
        dir_exists = os.path.exists(workspace_dir)
        src_dir_exists = os.path.exists(upload.get_source_directory())
        rem_dir_exists = os.path.exists(upload.get_removed_directory())
        self.assertEqual(dir_exists, True, 'Create workspace directory.')
        self.assertEqual(src_dir_exists, True, 'Create workspace source directory.')
        self.assertEqual(rem_dir_exists, True, 'Create workspace removed directory.')
        upload.remove_workspace()

    def test_deposit_upload(self):
        """Test upload file deposit into src directory."""
        tfilename = os.path.join(TEST_FILES_DIRECTORY, '1801.03879-1.tar.gz')
        self.assertTrue(os.path.exists(tfilename), 'Test archive is available')
        # Recreate FileStorage object that flask will be passing in

        upload = Upload(12345682)
        workspace_dir = upload.create_upload_workspace()
        if os.path.exists(workspace_dir):
            # Go ahead and deposit file in source directory
            basename = os.path.basename(tfilename)
            # Sanitize file name before saving it
            filename = secure_filename(basename)
            source_directory = upload.get_source_directory()
            path = os.path.join(source_directory, filename)
            # Remove existing file - should we warn?
            if os.path.exists(path):
                os.remove(path)
            self.assertFalse(os.path.exists(path), "Haven't deposited file yet.")
            # Finally save file
            file = None
            with open(tfilename, 'rb') as fp:
                # clear  print("Open File for reading\n")
                file = FileStorage(fp)
                file.save(path)
            # Make sure it exists
            self.assertTrue(os.path.exists(path), "Deposited upload file.")
        else:
            self.assertTrue(os.path.exists(workspace_dir), "Workspace directory exists.")

        # cleanup workspace
        upload.remove_workspace()

    def test_check_file_termination(self):
        """
        Test the filtering of unwanted characters from the end of file.
        :return:
        """

        # Copy the files that will be modified to temporary location
        tmp_dir = tempfile.mkdtemp()


        upload = Upload(1234566)

        #upload.set_debug(True)

        # 1
        tfilename = os.path.join(TEST_FILES_DIRECTORY, 'terminators1.txt')
        destfilename = os.path.join(tmp_dir, 'terminators1.txt')
        shutil.copy(tfilename, destfilename)
        file_obj = File(destfilename, tmp_dir)

        upload.check_file_termination(file_obj)

        # Check that file generated is what we expected
        reference = os.path.join(TEST_FILES_DIRECTORY, 'terminators1stripped.txt')
        is_same = filecmp.cmp(destfilename, reference)
        self.assertTrue(is_same, 'Eliminated unwanted CR characters from DOS file.')

        # 2
        tfilename = os.path.join(TEST_FILES_DIRECTORY, 'terminators2.txt')
        destfilename = os.path.join(tmp_dir, 'terminators2.txt')
        shutil.copy(tfilename, destfilename)
        file_obj = File(destfilename, tmp_dir)

        upload.check_file_termination(file_obj)

        # Check that file generated is what we expected
        reference = os.path.join(TEST_FILES_DIRECTORY, 'terminators2stripped.txt')
        is_same = filecmp.cmp(destfilename, reference)
        self.assertTrue(is_same, 'Eliminated unwanted CR characters from DOS file.')

        # 3
        # TODO: Having trouble creating example with \377 and non in production system.
        tfilename = os.path.join(TEST_FILES_DIRECTORY, 'terminators3.txt')
        destfilename = os.path.join(tmp_dir, 'terminators3.txt')
        shutil.copy(tfilename, destfilename)
        file_obj = File(destfilename, tmp_dir)
        upload.check_file_termination(file_obj)

        # Check that file generated is what we expected
        #reference = os.path.join(TEST_FILES_DIRECTORY, 'AfterUnPCify.eps')
        #is_same = filecmp.cmp(destfilename, reference)
        #self.assertTrue(is_same, 'Eliminated unwanted CR characters from DOS file.')

        # 4
        tfilename = os.path.join(TEST_FILES_DIRECTORY, 'BeforeUnPCify.eps')
        destfilename = os.path.join(tmp_dir, 'BeforeUnPCify.eps')
        shutil.copy(tfilename, destfilename)
        file_obj = File(destfilename, tmp_dir)

        upload.check_file_termination(file_obj)

        # Check that file generated is what we expected
        reference = os.path.join(TEST_FILES_DIRECTORY, 'AfterTermUnPCify.eps')
        is_same = filecmp.cmp(destfilename, reference)
        self.assertTrue(is_same, 'Eliminated unwanted EOT terminators.')

        # 5
        tfilename = os.path.join(TEST_FILES_DIRECTORY, 'BeforeUnPCify2.eps')
        destfilename = os.path.join(tmp_dir, 'BeforeUnPCify2.eps')
        shutil.copy(tfilename, destfilename)
        file_obj = File(destfilename, tmp_dir)

        upload.check_file_termination(file_obj)

        # Check that file generated is what we expected
        reference = os.path.join(TEST_FILES_DIRECTORY, 'AfterTermUnPCify2.eps')

        is_same = filecmp.cmp(destfilename, reference)
        self.assertTrue(is_same, 'Eliminated unwanted EOT terminators.')

    def test_check_file_unmacify(self):
        """
        Test the filtering of unwanted CR characters from specified file.
        :return:
        """

        # Copy the files that will be modified to temporary location
        tmp_dir = tempfile.mkdtemp()

        upload = Upload(1234566)

        # UnPCify

        tfilename = os.path.join(TEST_FILES_DIRECTORY, 'BeforeUnPCify.eps')
        destfilename = os.path.join(tmp_dir, 'BeforeUnPCify.eps')
        shutil.copy(tfilename, destfilename)
        file_obj = File(destfilename, tmp_dir)

        upload.unmacify(file_obj)

        # Check that file generated is what we expected
        reference = os.path.join(TEST_FILES_DIRECTORY, 'AfterUnPCify.eps')
        is_same = filecmp.cmp(destfilename, reference, shallow=False)
        self.assertTrue(is_same, 'Eliminated unwanted CR characters from DOS file.')

        # UnMACify

        tfilename = os.path.join(TEST_FILES_DIRECTORY, 'BeforeUnMACify.eps')
        destfilename = os.path.join(tmp_dir, 'BeforeUnMACify.eps')
        shutil.copy(tfilename, destfilename)
        file_obj = File(destfilename, tmp_dir)

        upload.unmacify(file_obj)

        # Check that file generated is what we expected
        reference = os.path.join(TEST_FILES_DIRECTORY, 'AfterUnMACify.eps')
        is_same = filecmp.cmp(destfilename, reference, shallow=False)
        self.assertTrue(is_same, 'Eliminated unwanted CR characters from MAC file.')

        # cleanup workspace
        upload.remove_workspace()

    def test_fix_file_extension(self) -> None:
        """
        Normalize file extension for file type.

        Some formats support multiple file nanme suffixes. We want to normalize
        all files of a particular type to have the desired extension. An
        example of this is .htm and .html extensions for files of type HTML.

        For this test we will work with specific files in temporary directory.

        Returns
        -------
            None
        """
        # Copy the files that will be modified to temporary location
        tmp_dir = tempfile.mkdtemp()

        # Create an upload to get a upload object to play with
        upload = Upload(1234555)

        # 1: Try arbitrary rename
        test_filename = 'BeforeUnPCify.eps'
        tfilename = os.path.join(TEST_FILES_DIRECTORY, test_filename)
        destfilename = os.path.join(tmp_dir, test_filename)
        shutil.copy(tfilename, destfilename)
        file_obj = File(destfilename, tmp_dir)

        new_extension = 'testext'
        new_file_obj = upload.fix_file_ext(file_obj, new_extension)

        filebase, file_extension = os.path.splitext(file_obj.name)
        new_filename = filebase + f".{new_extension}"
        #new_path = os.path.join(file_obj.base_dir, new_file)

        # Now look for renamed file
        filebase, file_extension = os.path.splitext(file_obj.name)

        # Make sure new file exists
        self.assertTrue(os.path.exists(new_file_obj.filepath),
                        f"Renamed file {new_filename} exists.")

        # Make sure file name is modified to use new extension.
        self.assertEqual(new_filename, new_file_obj.name,
                         "Renamed file has correct extension.")

        # 2: Try .HTM to .html rename
        test_filename = 'sampleA.html'
        temp_filename = 'sampleA.HTM'
        tfilename = os.path.join(TEST_FILES_SUB_TYPE, test_filename)
        destfilename = os.path.join(tmp_dir, temp_filename)
        shutil.copy(tfilename, destfilename)
        file_obj = File(destfilename, tmp_dir)

        new_extension = 'html'
        new_file_obj = upload.fix_file_ext(file_obj, new_extension)

        filebase, file_extension = os.path.splitext(file_obj.name)
        new_filename = filebase + f".{new_extension}"

        # Make sure new file exists
        self.assertTrue(os.path.exists(new_file_obj.filepath),
                        f"Renamed file {new_filename} exists.")

        # Make sure file name is modified to use new extension.
        self.assertEqual(new_filename, new_file_obj.name,
                         "Renamed file has correct extension.")

        # 3: Try to fix extension of non-existent file (Error)
        new_extension = 'fail'
        new_file_obj = upload.fix_file_ext(file_obj, new_extension)

        # Error should exist
        self.assertTrue(upload.has_errors(),
                        f"Fix non-existent file generates error.")

        # Check to make sure error is added to list of errors.
        self.assertTrue(upload.search_errors(f"File '{file_obj.name}'"
                                             " to fix extension not"),
                                             "Error message added to list.")

        # cleanup workspace
        upload.remove_workspace()


class TestUpload(TestCase):
    """:func:`.process_upload` adds ones to :prop:`.Thing.name`."""

    # Does this belong with a set of unpack tests (did not exist in legacy system but evidence
    # that someone was collecting files to use as part of unpack tests - may need to refactor in future.

    def test_process_upload_with_subdirectories(self) -> None:

        """Try to process archive with multiple gzipped archives imbedded in it"""
        upload = Upload('9903.1014')

        filename = os.path.join(TEST_FILES_DIRECTORY, 'UnpackWithSubdirectories.tar.gz')

        # For testing purposes, clean out existing workspace directory
        workspace_dir = upload.create_upload_workspace()
        if os.path.exists(workspace_dir):
            shutil.rmtree(workspace_dir)

        self.assertTrue(os.path.exists(filename), 'Test zip archive is available')
        # Recreate FileStroage object that flask will be passing in
        file = None
        with open(filename, 'rb') as fp:
            upload = Upload('9903.1014')
            file = FileStorage(fp)
            ret = upload.process_upload(file)

        source_directory = upload.get_source_directory()

        # These files were all contained in gzipped archives contained in original upload.

        # Check subdirectory exists
        directory_to_check = os.path.join(source_directory, 'b', 'c')
        self.assertTrue(os.path.exists(directory_to_check), 'Test subdirectory exists: b/c')

        # Check file in subdirectory exists
        file_to_check = os.path.join(source_directory, 'b', 'c', 'c_level_file.txt')
        self.assertTrue(os.path.exists(file_to_check), 'Test file within subdirectory exists: \'c_level_file.txt\'')

        # cleanup workspace
        upload.remove_workspace()

    def test_process_count_file_types(self) -> None:
        """Test routine that counts file type occurrences.

        Also tests get_single_file() routine.
        """
        upload = Upload(20180245)
        filename = os.path.join(TEST_FILES_DIRECTORY, 'UploadWithANCDirectory.tar.gz')

        # For testing purposes, clean out existing workspace directory
        workspace_dir = upload.get_upload_directory()
        if os.path.exists(workspace_dir):
            shutil.rmtree(workspace_dir)

        self.assertTrue(os.path.exists(filename), 'Test upload with anc files.')
        # Recreate FileStroage object that flask will be passing in
        file = None
        with open(filename, 'rb') as fp:
            # Now create upload instance
            upload = Upload(20180245)
            file = FileStorage(fp)

            # Test 1: Upload normal submission with lots of files.
            ret = upload.process_upload(file)

            file_formats = upload.count_file_types()

            # Check numbers generated by count_file_types()
            self.assertEqual(file_formats['all_files'], 21,
                             "Total number of files matches.")
            self.assertEqual(file_formats['files'], 6,
                             "Total number of files matches.")
            self.assertEqual(file_formats['ancillary'], 15,
                             "Total number of files matches.")
            self.assertEqual(file_formats['pdf'], 2,
                             "Total number of files matches.")
            self.assertEqual(file_formats['texaux'], 3,
                             "Total number of files matches.")

            # Clean out files. Try exception cases.
            upload.client_remove_all_files()

            # Test 2: Count nothingness
            file_formats = upload.count_file_types()

            # Check numbers
            self.assertEqual(file_formats['all_files'], 0,
                             "Total number of files matches is 0.")
            self.assertEqual(file_formats['files'], 0,
                             "Total number of files matches is 0.")

            # Test get_single_file()
            self.assertEqual(upload.get_single_file(), None,
                             "This is not a valid single file submission.")

            # Clean out files. Try exception cases.
            upload.client_remove_all_files()

        # Test 3: Single invalid sub file - generates warning to user
        test_filename = 'sampleA.docx'
        filename = os.path.join(TEST_FILES_SUB_TYPE, test_filename)
        with open(filename, 'rb') as fp:
            # Now create upload instance
            upload = Upload(20180245)
            file = FileStorage(fp)

            ret = upload.process_upload(file)

            # Single invalid source files uploaded
            file_formats = upload.count_file_types()

            # Check numbers - at this point you can't go further with docx
            self.assertEqual(file_formats['all_files'], 1,
                             "Total number of files matches is 1.")
            self.assertEqual(file_formats['files'], 1,
                             "Total number of files matches is 1.")
            self.assertEqual(file_formats['docx'], 1,
                             "Total number of files matches is 1.")

            # Clean out files to get ready for next test.
            upload.client_remove_all_files()

        # Test 4: Single invalid file
        test_filename = 'head.tmp'
        filename = os.path.join(TEST_FILES_SUB_TYPE, test_filename)
        with open(filename, 'rb') as fp:
            # Now create upload instance
            upload = Upload(20180245)
            file = FileStorage(fp)

            ret = upload.process_upload(file)

            # Single invalid source files uploaded
            file_formats = upload.count_file_types()

            # Check numbers - at this point you can't upload docx
            self.assertEqual(file_formats['all_files'], 1,
                             "Total number of files matches is 1.")
            self.assertEqual(file_formats['files'], 1,
                             "Total number of files matches is 1.")
            self.assertEqual(file_formats['always_ignore'], 1,
                             "Total number of files matches is 1.")

            # Test get_single_file()
            self.assertEqual(upload.get_single_file(), None,
                             "This is not a valid single file submission.")

            # Clean out files to get ready for next test.
            upload.client_remove_all_files()

        # Test 5: No source files - ancillary files.
        test_filename = 'onlyANCfiles.tar.gz'
        filename = os.path.join(TEST_FILES_SUB_TYPE, test_filename)
        with open(filename, 'rb') as fp:
            # Now create upload instance
            upload = Upload(20180245)
            file = FileStorage(fp)

            ret = upload.process_upload(file)

            # No valid source files uploaded (ancillary)
            file_formats = upload.count_file_types()

            # Check numbers generated by count_file_types()
            self.assertEqual(file_formats['all_files'], 15,
                             "Total number of files matches.")
            # There should be NO legitimate source files.
            self.assertEqual(file_formats['files'], 0,
                             "Total number of files matches.")
            self.assertEqual(file_formats['ancillary'], 15,
                             "Total number of files matches.")

            # Clean out files to get ready for next test.
            upload.client_remove_all_files()

        # Test 6: Single-file submission (good)
        test_filename = 'upload5.pdf'
        filename = os.path.join(TEST_FILES_DIRECTORY, test_filename)
        with open(filename, 'rb') as fp:
            # Now create upload instance
            upload = Upload(20180245)
            file = FileStorage(fp)

            ret = upload.process_upload(file)

            # Single valid source file uploaded.
            file_formats = upload.count_file_types()

            # Check numbers generated by count_file_types()
            self.assertEqual(file_formats['all_files'], 1,
                             "Total number of files matches.")
            self.assertEqual(file_formats['files'], 1,
                             "Total number of files matches.")
            self.assertEqual(file_formats['pdf'], 1,
                             "Total number of files matches.")

            # Test get_single_file() - This is a case where it works.
            self.assertIsInstance(upload.get_single_file(), File,
                             "This is a valid single file submission.")
            single_file = upload.get_single_file()
            self.assertEqual(test_filename, single_file.name,
                             f"Found single file submission: {test_filename}.")

            # Clean out files to get ready for next test.
            upload.client_remove_all_files()

        # Clean up the workspace we used for all of these tests
        upload = Upload(20180245)
        upload.remove_workspace()

    def test_process_determine_source_format(self) -> None:
        """Test code that determines submission format."""
        upload = Upload(2019145)

        # Clean out files to get ready for next test.
        upload.client_remove_all_files()

        # For testing purposes, clean out existing workspace directory
        workspace_dir = upload.get_upload_directory()
        if os.path.exists(workspace_dir):
            shutil.rmtree(workspace_dir)

        for test in test_submissions:

            test_filename, exp_sub_type, description = test

            #print(f"\n**Test File: {test_filename} format expected: {exp_sub_type} \n\tDetails:{description}")

            filepath = os.path.join(TEST_FILES_DIRECTORY, test_filename)
            if not os.path.exists(filepath):
                filepath = os.path.join(TEST_FILES_SUB_TYPE, test_filename)
            if not os.path.exists(filepath):
                filepath = os.path.join(TEST_FILES_FILE_TYPE, test_filename)

            self.assertTrue(os.path.exists(filepath),
                            f"Test submission file path exists: {filepath}")

            with open(filepath, 'rb') as fp:
                # Now create upload instance
                upload = Upload(20180245)
                file = FileStorage(fp)
                upload.client_remove_all_files()
                ret = upload.process_upload(file)
                sub_type = upload.source_format

                self.assertEqual(sub_type, exp_sub_type,
                                f"Correctly identified submission of type '{sub_type}'.")

                # Clean out files to get ready for next test.
                upload.client_remove_all_files()

                # cleanup workspace
                upload.remove_workspace()


    def test_process_anc_upload(self) -> None:
        """Process upload with ancillary files in anc directory"""
        upload = Upload(20180226)
        filename = os.path.join(TEST_FILES_DIRECTORY, 'UploadWithANCDirectory.tar.gz')

        # For testing purposes, clean out existing workspace directory
        workspace_dir = upload.get_upload_directory()
        if os.path.exists(workspace_dir):
            shutil.rmtree(workspace_dir)

        self.assertTrue(os.path.exists(filename), 'Test upload with anc files.')
        # Recreate FileStroage object that flask will be passing in
        file = None
        with open(filename, 'rb') as fp:
            # Now create upload instance
            upload = Upload(20180226)
            file = FileStorage(fp)
            ret = upload.process_upload(file)

            # cleanup workspace
            upload.remove_workspace()

    # Modified handling of bib/bbl to reduce published papers with 'missing refs'
    def test_process_bib_bbl_handling(self) -> None:

        """Test changes to reduce missing refs."""
        upload_id = 20189999
        upload = Upload(upload_id)

        filename = os.path.join(TEST_FILES_DIRECTORY, 'bad_bib_but_no_bbl.tar')
        self.assertTrue(os.path.exists(filename), 'Test submission with missing .bbl file.')

        # For testing purposes, clean out existing workspace directory
        workspace_dir = upload.create_upload_workspace()
        if os.path.exists(workspace_dir):
            shutil.rmtree(workspace_dir)


        # Test common behavior of submitting .bib file without .bbl file and then follow by
        # adding .bbl file to make submission whole.

        # Step 1: Load submission that includes .bib file but is missing required .bbl; file

        # Recreate FileStroage object that flask will be passing in
        file = None
        with open(filename, 'rb') as fp:
            file = FileStorage(fp)
            # Now create upload instance
            upload = Upload(upload_id)
            ret = upload.process_upload(file)

            self.assertTrue(upload.has_warnings(), "This test is expected to generate missing .bbl warning!")
            self.assertTrue(upload.has_errors(), "This test is expected to generate missing .bbl error!")

            error_match = 'Your submission contained'
            string = f'This test is expected to generate missing .bbl error: "{error_match}"'
            self.assertTrue(upload.search_errors(error_match), string)

            warn_match = r'We do not run bibtex'
            string = f'This test is expected to produce general warning: "{warn_match}"'
            self.assertTrue(upload.search_warnings(warn_match), string)

            # Step 2: Now load missing .bbl (and . bib should get removed)

            filename = os.path.join(TEST_FILES_DIRECTORY, 'final.bbl')
            self.assertTrue(os.path.exists(filename), 'Upload missing .bbl file.')

            with open(filename, 'rb') as fp:
                file = FileStorage(fp)
                ret = upload.process_upload(file)

                error_match = 'Your submission contained'
                string = f'This test is NOT expected to generate missing .bbl error: "{error_match}"'
                self.assertFalse(upload.search_errors(error_match), string)

                warn_match = 'We do not run bibtex'
                string = f'This test is expected to generate removing .bib warning: "{warn_match}"'
                self.assertTrue(upload.search_warnings(warn_match), string)

                warn_match = "Removed the file 'final.bib'."
                string = f'This test is expected to generate removing .bib warning: "{warn_match}"'
                self.assertTrue(upload.search_warnings(warn_match), string)

        # Try submission with .bbl file (Good)
        filename = os.path.join(TEST_FILES_DIRECTORY, 'upload3.tar.gz')
        self.assertTrue(os.path.exists(filename), 'Test well-formed submission with .bbl file.')

        with open(filename, 'rb') as fp:
            file = FileStorage(fp)
            # Now create upload instance
            upload = Upload(upload_id)
            ret = upload.process_upload(file)

            self.assertFalse(upload.has_warnings(), 'Test well-formed submission. No warnings.')
            self.assertFalse(upload.has_errors(), 'Test well-formed submission. No errors.')

            # cleanup workspace
            upload.remove_workspace()

    def test_process_unpack(self) -> None:
        """
        Test upload service's archive unpack routine.

        Returns
        -------

        """

        test_file_directory = UNPACK_TEST_FILES_DIRECTORY

        for unpack_test in unpack_tests:

            test_file, upload_id, warnings, warnings_match, *extras = unpack_test + [None] * 2

            self.assertIsNotNone(upload_id, "Test must have upload identifier.")

            if not upload_id:
                print("Test metadata is missing upload identifier. Skipping text.")
                continue

            # Create path to test upload archive
            new_path = os.path.join(test_file_directory, test_file)

            # Make sure test file exists
            self.assertTrue(os.path.exists(new_path), 'Test unpack ' + new_path + ' exists!')

            # Create Uplaod object - this instance gets cleaned out
            upload = Upload(upload_id)

            # For testing purposes only, clean out existing workspace directory
            workspace_dir = upload.get_upload_directory()
            if os.path.exists(workspace_dir):
                shutil.rmtree(workspace_dir)

            print(f"Run test upload checks against test file: '{test_file}'")

            # Recreate FileStroage object that flask will be passing in
            file = None
            with open(new_path, 'rb') as fp:
                file = FileStorage(fp)
                # Now create upload instance
                upload = Upload(upload_id)
                # Process upload
                upload.process_upload(file)

                # For the case where we are expecting warnings make sure upload has the right ones
                if warnings:

                    self.assertTrue(upload.has_warnings(), "This test is expected to generate warnings!")

                    # Look for specific warning we are attempting to generate
                    if upload.has_warnings():
                        # print ("Upload process had warnings as expected")
                        # print("Search for warning: '" + warnings_match + "'")
                        # Complain if we didn't find expected warning
                        string = f'This test is expected to generate specific warning: "{warnings_match}"'
                        self.assertTrue(upload.search_warnings(warnings_match), string)

                        # if upload.search_warnings(warnings_match):
                        # print("Found expected warning")
                        # else:
                    # print("Failed to find expected warning")
                    else:
                        print("Upload completed without warnings (not expected)")
                else:
                    self.assertFalse(upload.has_warnings(), 'Not expecting warnings!')

                # clean up workspace
                upload.remove_workspace()

    def test_process_general_upload(self) -> None:
        """Test series of uniform test cases with specified outcomes"""

        test_file_directory = TEST_FILES_DIRECTORY

        for upload_test in upload_tests:

            test_file, upload_id, warnings, warnings_match, *extras = upload_test + [None] * 2

            self.assertIsNotNone(upload_id, "Test must have upload identifier.")

            if not upload_id:
                print("Test metadata is missing upload identifier. Skipping text.")
                continue

            # Create path to test upload archive
            new_path = os.path.join(test_file_directory, test_file)

            # Make sure test file exists
            self.assertTrue(os.path.exists(new_path), 'Test upload ' + new_path + ' exists!')

            # Create Uplaod object - this instance gets cleaned out
            upload = Upload(upload_id)

            # For testing purposes only, clean out existing workspace directory
            workspace_dir = upload.get_upload_directory()
            if os.path.exists(workspace_dir):
                shutil.rmtree(workspace_dir)

            print(f"Run test upload checks against test file: '{test_file}'")

            # Recreate FileStroage object that flask will be passing in
            file = None
            with open(new_path, 'rb') as fp:
                file = FileStorage(fp)
                # Now create upload instance
                upload = Upload(upload_id)
                # Process upload
                upload.process_upload(file)

                # For the case where we are expecting warnings make sure upload has the right ones
                if warnings:

                    self.assertTrue(upload.has_warnings(), "This test is expected to generate warnings!")

                    # Look for specific warning we are attempting to generate
                    if upload.has_warnings():
                        # print ("Upload process had warnings as expected")
                        # print("Search for warning: '" + warnings_match + "'")
                        # Complain if we didn't find speocfied warning
                        string = f'This test is expected to generate specific warning: "{warnings_match}"'

                        self.assertTrue(upload.search_warnings(warnings_match), string)

                        # if upload.search_warnings(warnings_match):
                        # print("Found expected warning")
                        # else:
                        # print("Failed to find expected warning")
                    else:
                        print("Upload completed without warnings (not expected)")
                else:
                    self.assertFalse(upload.has_warnings(), f'{test_file}: Not expecting warnings!')

                # Clean up workspace
                upload.remove_workspace()
