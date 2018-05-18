from unittest import TestCase
from filemanager.arxiv.file import File

import os.path


class TestFileClass(TestCase):
    """Test File class"""

    def test_file(self):
        """Test :class:`.File` methods."""
        cwd = os.getcwd()
        testfiles_dir = os.path.join(cwd, 'tests/type_test_files')
        testfile_path = os.path.join(testfiles_dir, 'image.gif')
        file = File(testfile_path, testfiles_dir)

        self.assertIsInstance(file, File, "Instantiated 'File' class object")

        # Check arguments are stored properly
        self.assertEquals(file.base_dir, testfiles_dir, "Check base_dir() method")
        self.assertEquals(file.filepath, testfile_path, "Check filepath() method")

        self.assertEquals(file.name, 'image.gif', "Check name() method")
        self.assertEquals(file.dir, testfiles_dir, "Check dir() method")

        self.assertEquals(file.public_dir, '', "Check public_dir() method")
        self.assertEquals(file.public_filepath, "image.gif", "Check public_filepath() method")

        self.assertEquals(file.type, 'image', "Check type() method")
        self.assertEquals(file.type_string, 'Image (gif/jpg etc)', "Check type_string() method")

        # TODO implement sha256sum function
        self.assertEquals(file.sha256sum, "NOT IMPLEMENTED YET", "Check sha256sum method()")
        file.description = 'This is my favorite photo.'
        self.assertEquals(file.description, 'This is my favorite photo.', "Check description() method")
        self.assertEquals(file.is_tex_type, False, "Check is_tex_type() method")
        self.assertEquals(file.ext, '.gif', "Check ext() method is '.gif'")
        self.assertEquals(file.size, 495, "Check size of '.gif' is 495")

    def test_file_subdirectory(self):
        """Pretend the file is in a subdirectory of submission workspace."""
        cwd = os.getcwd()
        testfiles_dir = os.path.join(cwd, 'tests')
        testfile_path = os.path.join(testfiles_dir, 'type_test_files/polch.tex')
        file = File(testfile_path, testfiles_dir)

        self.assertIsInstance(file, File, "Instantiated 'File' class object")

        # Check arguments are stored properly
        self.assertEquals(file.base_dir, testfiles_dir, "Check base_dir() method")
        self.assertEquals(file.filepath, testfile_path, "Check filepath() method")

        self.assertEquals(file.name, 'polch.tex', "Check name() method")
        file_dir = os.path.join(testfiles_dir, 'type_test_files')
        self.assertEquals(file.dir, file_dir, "Check dir() method")
        self.assertEquals(file.public_dir, 'type_test_files', "Check public_dir() method")
        self.assertEquals(file.public_filepath, 'type_test_files/polch.tex', "Check public_filepath() method")

        self.assertEquals(file.type, 'latex', "Check type() method")
        self.assertEquals(file.type_string, 'LaTeX', "Check type_string() method")
        self.assertEquals(file.ext, '.tex', "Check ext() method is '.tex'")
        self.assertEquals(file.size, 358441, "Check size of 'polch.tex' is 358441,")

    def test_file_setters(self):
        """Test that we are able to set various settings."""
        cwd = os.getcwd()
        testfiles_dir = os.path.join(cwd, 'tests')
        testfile_path = os.path.join(testfiles_dir, 'type_test_files/polch.tex')
        file = File(testfile_path, testfiles_dir)

        # Check arguments are stored properly
        self.assertEquals(file.base_dir, testfiles_dir, "Check base_dir() method")
        self.assertEquals(file.filepath, testfile_path, "Check filepath() method")

        # new base dir
        new_dir = os.path.join(testfiles_dir, 'type_test_files')
        file.base_dir = new_dir
        self.assertEquals(file.base_dir, new_dir, "Check base_dir() method")

        file.description = "test setter"
        self.assertEquals(file.description, 'test setter', "Check description() method")

    def test_remove(self):
        """Test setting and getting state of removed file."""
        cwd = os.getcwd()
        testfiles_dir = os.path.join(cwd, 'tests')
        testfile_path = os.path.join(testfiles_dir, 'type_test_files/polch.tex')
        file = File(testfile_path, testfiles_dir)

        self.assertFalse(file.removed, 'File not removed yet')
        file.remove()
        self.assertTrue(file.removed, 'File has been marked as removed')

    def test_anc_detection(self):
        """Check that we are detecting 'special' ancillary directory properly."""
        cwd = os.getcwd()
        testfiles_dir = os.path.join(cwd, 'tests')
        testfile_path = os.path.join(testfiles_dir, 'anc')
        file = File(testfile_path, testfiles_dir)

        self.assertEquals(file.type, 'directory', "Check type of ancillary directory.")
        self.assertEquals(file.type_string, 'Ancillary files directory', "Check type_string for ancillary directory")

    def test_dirs(self):
        """Check operations on directories."""
        cwd = os.getcwd()
        testfiles_dir = os.path.join(cwd, 'tests')
        testfile_path = os.path.join(testfiles_dir, 'type_test_files', 'subdirectory')
        file = File(testfile_path, testfiles_dir)

        self.assertEquals(file.base_dir, testfiles_dir, "Check base_dir() method")
        self.assertEquals(file.public_dir, 'type_test_files', "Check public_dir() method")
        self.assertEquals(file.type, 'directory', "Check type of ancillary directory.")
        self.assertEquals(file.type_string, 'Directory', "Check type_string for ancillary directory")
