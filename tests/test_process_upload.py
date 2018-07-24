"""Tests for :mod:`zero.process.upload`."""

from unittest import TestCase
from datetime import datetime
# from filemanager.domain import Upload
from filemanager.process import upload
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

import os.path
import shutil

from filemanager.process.upload import Upload

UPLOAD_BASE_DIRECTORY = '/tmp/filemanagment/submissions'

TEST_FILES_DIRECTORY = os.path.join(os.getcwd(), 'tests/test_files_upload')

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

    def XXtest_process_tgz_upload(self) -> None:

        """Try to process bzip2 archive upload"""
        # upload_id = 20180228
        upload = Upload(20180228)

        filename = os.path.join(TEST_FILES_DIRECTORY, 'upload6.tgz')

        # For testing purposes, clean out existing workspace directory
        workspace_dir = upload.create_upload_workspace()
        if os.path.exists(workspace_dir):
            shutil.rmtree(workspace_dir)

        self.assertTrue(os.path.exists(filename), 'Test zip archive is available')
        # Recreate FileStroage object that flask will be passing in
        file = None
        with open(filename, 'rb') as fp:
            file = FileStorage(fp)
            ret = upload.process_upload(file)

        print("Process tgz upload: " + ret)

    def XXtest_process_compressed_upload(self) -> None:

        """Try to process compressed archive upload"""
        # upload_id = 20180229
        upload = Upload(20180229)

        filename = os.path.join(TEST_FILES_DIRECTORY, 'BorelPaper.tex.Z')

        # For testing purposes, clean out existing workspace directory
        workspace_dir = upload.create_upload_workspace()
        if os.path.exists(workspace_dir):
            shutil.rmtree(workspace_dir)

        self.assertTrue(os.path.exists(filename), 'Test compressed archive is available')
        # Recreate FileStroage object that flask will be passing in
        file = None
        with open(filename, 'rb') as fp:
            file = FileStorage(fp)
            ret = upload.process_upload(file)

        print("Process tgz upload: " + ret)

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

            print('Run test upload checks against file: ' + test_file)

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
                        self.assertTrue(upload.search_warnings(warnings_match),
                                        f'This test is expected to generate specific warning: "{warnings_match}"')
                        # if upload.search_warnings(warnings_match):
                        # print("Found expected warning")
                        # else:
                        # print("Failed to find expected warning")
                    else:
                        print("Upload completed without warnings (not expected)")
                else:
                    self.assertFalse(upload.has_warnings(), 'Not expecting warnings!')
