"""Test availability check for filesystem."""

from unittest import TestCase, mock
import io


from .. import upload as upload_fs


class TestIsAvailable(TestCase):
    """Test behavior of :func:`.upload_fs.is_available`."""

    @mock.patch(f'{upload_fs.__name__}.get_application_config',
                mock.MagicMock(return_value={'UPLOAD_BASE_DIRECTORY': '/tmp'}))
    def test_fs_is_available(self):
        """The filesystem is available."""
        self.assertTrue(upload_fs.is_available())

    @mock.patch(f'{upload_fs.__name__}.get_application_config',
                mock.MagicMock(return_value={'UPLOAD_BASE_DIRECTORY': '/no'}))
    def test_base_dir_does_not_exist(self):
        """The upload base directory does not exist."""
        self.assertFalse(upload_fs.is_available())

    @mock.patch(f'{upload_fs.__name__}.get_application_config',
                mock.MagicMock(return_value={'UPLOAD_BASE_DIRECTORY': '/tmp'}))
    @mock.patch(f'{upload_fs.__name__}.tempfile.TemporaryFile',
                mock.MagicMock(
                    write=mock.MagicMock(side_effect=io.UnsupportedOperation)))
    def test_base_dir_not_writeable(self):
        """The upload base directory is not writeable."""
        self.assertFalse(upload_fs.is_available())
