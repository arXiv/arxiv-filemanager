import os
import shutil
import tempfile
from unittest import TestCase, mock
from datetime import datetime

from pytz import UTC
from werkzeug.datastructures import FileStorage

from filemanager.domain.uploads.exceptions import NoSourceFilesToCheckpoint
from filemanager.domain.uploads import Workspace, UserFile
from filemanager.domain.file_type import FileType
from filemanager.services import storage
from filemanager.process import strategy, check

class TestCheckpointable(TestCase):

    DATA_PATH = os.path.join(os.path.split(os.path.abspath(__file__))[0],
                             'test_files_upload')

    @mock.patch('filemanager.domain.uploads.file_mutations.logging',
                mock.MagicMock())
    def setUp(self):
        """We have a vanilla workspace."""
        self.base_path = tempfile.mkdtemp()
        self.test_id = '1234321'
        self.storage = storage.SimpleStorageAdapter(self.base_path)
        self.wks = Workspace(
            upload_id=self.test_id,
            owner_user_id='98765',
            created_datetime=datetime.now(),
            modified_datetime=datetime.now(),
            _storage=self.storage,
            _strategy = strategy.create_strategy(mock.MagicMock()),
            checkers=check.get_default_checkers()
        )
        self.wks.initialize()

    def tearDown(self):
        """Clean up."""
        shutil.rmtree(self.base_path)

    def compare_file_lists(self, list1: list, list2: list) -> bool:
        """
        Compare two lists of File objects and determine if they are equal.
        Since restore changes the modification time we will ignore this.
        Parameters
        ----------
        list1: list
            List of file objects
        list2
            List of file objects
        Returns
        -------
        True if list of File objects is idenical on name, size, checsum fields,
        otherwise False is returned.
        """
        names1 = {file.name for file in list1}
        names2 = {file.name for file in list2}

        if len(names1) != len(names2):
            return False

        # Compare the two lists
        set1 = set((x.name, x.checksum, x.size_bytes) for x in list1)
        set2 = set((x.name, x.checksum, x.size_bytes) for x in list2)
        if not set1.symmetric_difference(set2):
            return True
        return False

    def test_checkpoint(self) -> None:
        """
        Test basic checkpoint functionality.
        """
        # Upload initial set of files for first checkpoint
        fname = os.path.join(self.DATA_PATH, 'UnpackWithSubdirectories.tar.gz')
        print(fname)
        self.assertTrue(os.path.exists(fname), 'Test archive is available')

        # Recreate FileStroage object that flask will be passing in
        file = None
        with open(fname, 'rb') as fp:
            file = FileStorage(fp)
            u_file = self.wks.create(file.filename)
            with self.wks.open(u_file, 'wb') as f_out:
                file.save(f_out)

        # Save a list of files to compare againsgt restored checkpoint
        test1_filelist = list(self.wks.iter_files())

        # Create a checkpoint
        checkpoint1_sum = self.wks.create_checkpoint(None)

        # Upload different set of files.
        fname = os.path.join(self.DATA_PATH, 'upload2.tar.gz')
        self.assertTrue(os.path.exists(fname), 'Test archive is available')

        # Clear out existing files (pretend user is uploading new set of files)
        self.wks.delete_all_files()

        # Recreate FileStroage object that flask will be passing in
        file = None
        with open(fname, 'rb') as fp:
            file = FileStorage(fp)
            u_file = self.wks.create(file.filename)
            with self.wks.open(u_file, 'wb') as f_out:
                file.save(f_out)

        # Save a list of files to compare againsgt restored checkpoint
        test2_filelist = list(self.wks.iter_files())

        # Create a second checkpoint
        checkpoint2_sum = self.wks.create_checkpoint(None)

        # Upload third set of files.
        fname = os.path.join(self.DATA_PATH, 'upload3.tar.gz')
        self.assertTrue(os.path.exists(fname), 'Test archive is available')

        # Clear out existing files (pretend user is uploading new set of files)
        self.wks.delete_all_files()

        # Recreate FileStroage object that flask will be passing in
        file = None
        with open(fname, 'rb') as fp:
            file = FileStorage(fp)
            u_file = self.wks.create(file.filename)
            with self.wks.open(u_file, 'wb') as f_out:
                file.save(f_out)

        # Save a list of files to compare againsgt restored checkpoint
        test3_filelist = list(self.wks.iter_files())

        # Create third checkpoint
        checkpoint3_sum = self.wks.create_checkpoint(None)

        # Now try to list checkpoints
        checkpoint_list = self.wks.list_checkpoints(None)
        print(f"\nList Checkpoints:{len(checkpoint_list)}")
        for checkpoint in checkpoint_list:
            print(f"  Checkpoint; {checkpoint.name}: "
                  f"{checkpoint.checksum} : {checkpoint.size_bytes}")

        # Now restore checkpoints and check whether the restored and original
        # file lists are equivalent.

        # Restore first checkpoint
        #   - removes all files under src directory
        print(f"\nRestore:{checkpoint1_sum}")
        print(self.wks.storage)
        self.wks.restore_checkpoint(checkpoint1_sum, None)
        print(self.wks.storage)
        # Check whether restored file list matches original list.
        b1 = self.compare_file_lists(self.wks.iter_files(), test1_filelist)
        self.assertTrue(b1, "Restored file list equivalent to orignal file "
                            "list for first checkpoint.")

        # Restore second checkpoint
        #   - removes all files under src directory
        print(f"\nRestore:{checkpoint2_sum}")
        self.wks.restore_checkpoint(checkpoint2_sum, None)

        # Check whether restored file list matches original list.
        b2 = self.compare_file_lists(self.wks.iter_files(), test2_filelist)
        self.assertTrue(b2, "Restored file list equivalent to orignal file "
                            "list for second checkpoint.")

        # Restore third checkpoint
        #   - removes all files under src directory
        print(f"\nRestore:{checkpoint3_sum}")
        self.wks.restore_checkpoint(checkpoint3_sum, None)

        # Check whether restored file list matches original list.
        b3 = self.compare_file_lists(self.wks.iter_files(), test3_filelist)
        self.assertTrue(b3, "Restored file list equivalent to orignal file "
                            "list for third checkpoint.")

        # Intentionally mess things up and make sure we generate a failure
        self.wks.delete_all_files()
        bf = self.compare_file_lists(self.wks.iter_files(), test3_filelist)
        self.assertFalse(bf, "Restored file list is NOT equivalent to "
                             "orignal file list (after deleting files).")

        # Test methods that support checkpoint download
        exists = self.wks.checkpoint_file_exists(checkpoint3_sum)
        self.assertTrue(exists, "Test whether known checkpoint exists.")

        u_file = self.wks.get_checkpoint_file(checkpoint3_sum)
        self.assertTrue(os.path.exists(u_file.full_path),
                        "Test whether known checkpoint file exists")

        size = self.wks.get_checkpoint_file_size(checkpoint3_sum)
        self.assertTrue(9950 < size < 10400, "Test size of known checkpoint "
                                             "is roughly '10327' bytes.")

        mod_date = self.wks.get_checkpoint_file_last_modified(checkpoint3_sum)
        self.assertTrue(mod_date, "Test modify date returned "
                                  "something (for now).")

        # Remove individual checkpoint files
        print(f"\nRemove checkpoint {checkpoint_list[0].checksum}")

        self.wks.delete_checkpoint(checkpoint_list[0].checksum, None)

        # List checkpoint files
        # Now try to list checkpoints
        checkpoint_list = self.wks.list_checkpoints(None)
        print(f"\nList Checkpoints:{len(checkpoint_list)}")
        for checkpoint in checkpoint_list:
            print(f"  Checkpoint; {checkpoint.name}: "
                  f"{checkpoint.checksum} : {checkpoint.size_bytes}")

        # Remove all remaining checkpoint files (what we didn't delete above)
        self.wks.delete_all_checkpoints(None)

        # Now try to list checkpoints
        checkpoint_list = self.wks.list_checkpoints(None)
        print(f"\nList Checkpoints:{len(checkpoint_list)}")
        for checkpoint in checkpoint_list:
            print(f"Checkpoint; {checkpoint['name']}: "
                  f"{checkpoint['checksum']} : {checkpoint['size']}")

        self.assertTrue(checkpoint_list == [],
                        "All checkpoints have been removed.")

        # Try to create checkpoint when there are no source files.

        # Clean out the source files
        self.wks.delete_all_files()

        # Create a second checkpoint
        with self.assertRaises(NoSourceFilesToCheckpoint):
            self.wks.create_checkpoint(None)