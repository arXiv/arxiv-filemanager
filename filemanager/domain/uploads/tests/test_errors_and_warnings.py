"""Tests for :mod:`.uploads.errors_and_warnings`."""

from unittest import TestCase, mock

from ...uploads import FileIndex
from ...uploaded_file import UserFile
from ...error import Error, Code, Severity
from ..errors_and_warnings import ErrorsAndWarnings, IWorkspace


class AddErrors(TestCase):
    """Test adding errors."""

    def test_add_error_file(self):
        """Add a fatal error for a file."""
        api = mock.MagicMock(spec=IWorkspace, files=FileIndex())
        u_file = UserFile(api, 'foo/path', 42)
        api.files.set(u_file.path, u_file)
        eaw = ErrorsAndWarnings()
        eaw.__api_init__(api)
        eaw.add_error(u_file, 'foo_error', 'this is a foo error')

        self.assertTrue(eaw.has_errors)
        self.assertTrue(eaw.has_errors_fatal)
        self.assertEqual(len(eaw.errors), 1)

    def test_add_duplicate_error_file(self):
        """Add two fatal errors for a file with the same code."""
        api = mock.MagicMock(spec=IWorkspace, files=FileIndex())
        u_file = UserFile(api, 'foo/path', 42)
        api.files.set(u_file.path, u_file)
        eaw = ErrorsAndWarnings()
        eaw.__api_init__(api)
        eaw.add_error(u_file, 'foo_error', 'this is a foo error')
        eaw.add_error(u_file, 'foo_error', 'this is also a foo error')

        self.assertTrue(eaw.has_errors)
        self.assertTrue(eaw.has_errors_fatal)
        self.assertEqual(len(eaw.errors), 1, 'Only one error per code')

        eaw.add_error(u_file, 'baz_error', 'this is not a foo error')
        self.assertEqual(len(eaw.errors), 2)

    def test_remove_error_file(self):
        """Remove an error for a file."""
        api = mock.MagicMock(spec=IWorkspace, files=FileIndex())
        u_file = UserFile(api, 'foo/path', 42)
        api.files.set(u_file.path, u_file)
        eaw = ErrorsAndWarnings()
        eaw.__api_init__(api)
        eaw.add_error(u_file, 'foo_error', 'this is a foo error')
        eaw.add_error(u_file, 'foo_error', 'this is also a foo error')

        self.assertTrue(eaw.has_errors)
        self.assertTrue(eaw.has_errors_fatal)
        self.assertEqual(len(eaw.errors), 1, 'Only one error per code')

        eaw.remove_error('foo_error', u_file.path)
        self.assertEqual(len(eaw.errors), 0)
        self.assertFalse(eaw.has_errors)
        self.assertFalse(eaw.has_errors_fatal)

    def test_add_error_file_to_file(self):
        """Add an error for a file to the file itself."""
        api = mock.MagicMock(spec=IWorkspace, files=FileIndex())
        u_file = UserFile(api, 'foo/path', 42)
        api.files.set(u_file.path, u_file)
        eaw = ErrorsAndWarnings()
        eaw.__api_init__(api)
        u_file.add_error(Error(severity=Severity.FATAL,
                               code='foo_error',
                               message='this is a foo error'))

        self.assertTrue(eaw.has_errors)
        self.assertTrue(eaw.has_errors_fatal)
        self.assertEqual(len(eaw.errors), 1)

    def test_remove_error_file_from_file(self):
        """Remove an error for a file from the file itself."""
        api = mock.MagicMock(spec=IWorkspace, files=FileIndex())
        u_file = UserFile(api, 'foo/path', 42)
        api.files.set(u_file.path, u_file)
        eaw = ErrorsAndWarnings()
        eaw.__api_init__(api)
        eaw.add_error(u_file, 'foo_error', 'this is a foo error')
        eaw.add_error(u_file, 'foo_error', 'this is also a foo error')

        self.assertTrue(eaw.has_errors)
        self.assertTrue(eaw.has_errors_fatal)
        self.assertEqual(len(eaw.errors), 1, 'Only one error per code')

        # Remove an error directly from the file.
        u_file.remove_error('foo_error')
        self.assertEqual(len(eaw.errors), 0)
        self.assertFalse(eaw.has_errors)
        self.assertFalse(eaw.has_errors_fatal)




