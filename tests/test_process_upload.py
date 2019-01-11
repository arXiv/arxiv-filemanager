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

upload_tests.append(['upload1.tar.gz', '9902.1001', True, 'espcrc2.sty is empty \(size is zero\)',
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


# Debugging tests


class TestInternalSupportRoutines(TestCase):

    def test_get_upload_directory(self):
        upload = Upload(12345678)
        workspace_dir = upload.get_upload_directory()
        self.assertEqual(workspace_dir, os.path.join(UPLOAD_BASE_DIRECTORY, '12345678'),
                         'Generate path to workspace directory')

    def test_create_upload_directory(self):
        upload = Upload(12345679)
        workspace_dir = upload.create_upload_directory()
        dir_exists = os.path.exists(workspace_dir)
        self.assertEqual(dir_exists, True, 'Create workspace directory.')

    def test_get_source_directory(self):
        upload = Upload(12345680)
        source_dir = upload.get_source_directory()
        self.assertEqual(source_dir, os.path.join(UPLOAD_BASE_DIRECTORY, '12345680', 'src'),
                         "Check 'src' directory")

    def test_get_removed_directory(self):
        upload = Upload(12345680)
        removed_dir = upload.get_removed_directory()
        self.assertEqual(removed_dir, os.path.join(UPLOAD_BASE_DIRECTORY, '12345680', 'removed'),
                         "Check 'removed' directory")

    def test_create_upload_workspace(self):
        upload = Upload(12345681)
        workspace_dir = upload.create_upload_workspace()
        dir_exists = os.path.exists(workspace_dir)
        src_dir_exists = os.path.exists(upload.get_source_directory())
        rem_dir_exists = os.path.exists(upload.get_removed_directory())
        self.assertEqual(dir_exists, True, 'Create workspace directory.')
        self.assertEqual(src_dir_exists, True, 'Create workspace source directory.')
        self.assertEqual(rem_dir_exists, True, 'Create workspace removed directory.')

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
        is_same = filecmp.cmp(destfilename, reference)
        self.assertTrue(is_same, 'Eliminated unwanted CR characters from DOS file.')

        # UnMACify

        tfilename = os.path.join(TEST_FILES_DIRECTORY, 'BeforeUnMACify.eps')
        destfilename = os.path.join(tmp_dir, 'BeforeUnMACify.eps')
        shutil.copy(tfilename, destfilename)
        file_obj = File(destfilename, tmp_dir)

        upload.unmacify(file_obj)

        # Check that file generated is what we expected
        reference = os.path.join(TEST_FILES_DIRECTORY, 'AfterUnMACify.eps')
        is_same = filecmp.cmp(destfilename, reference)
        self.assertTrue(is_same, 'Eliminated unwanted CR characters from MAC file.')



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

    # TODO: Keep these old tests around for when I need specialized tests
    def XXtest_process_compressed_upload(self) -> None:

        """Test that we are generating warnings when zero length files are uploaded."""
        upload_id = 20180229
        upload = Upload(upload_id)

        filename = os.path.join(TEST_FILES_DIRECTORY, 'upload1.tar.gz')

        # For testing purposes, clean out existing workspace directory
        workspace_dir = upload.create_upload_workspace()
        if os.path.exists(workspace_dir):
            shutil.rmtree(workspace_dir)

        self.assertTrue(os.path.exists(filename), 'Test compressed archive is available')
        # Recreate FileStroage object that flask will be passing in
        file = None
        with open(filename, 'rb') as fp:
            file = FileStorage(fp)
            # Now create upload instance
            upload = Upload(upload_id)
            ret = upload.process_upload(file)

        if upload.has_warnings():
            print("Upload has warnings")
            for warn in upload.get_warnings():
                print(f"Warning: {warn}")

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
                    self.assertFalse(upload.has_warnings(), 'Not expecting warnings!')
