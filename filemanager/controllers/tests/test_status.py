"""Tests for :mod:`.controllers.status`."""

from unittest import TestCase, mock
from http import HTTPStatus

from .. import status


class TestCheckServiceStatus(TestCase):
    """Tests for :func:`.controllers.status.service_status`."""

    @mock.patch(f'{status.__name__}.database.is_available',
                mock.MagicMock(return_value=True))
    # @mock.patch(f'{status.__name__}.filesystem.is_available',
    #             mock.MagicMock(return_value=True))
    def test_all_ok(self):
        """All dependencies are available."""
        response_data, code, headers = status.service_status()
        self.assertEqual(code, HTTPStatus.OK, 'Returns 200 OK')
        self.assertTrue(response_data['database'], 'Database reports OK')
        # self.assertTrue(response_data['filesystem'], 'Filesystem reports OK')

    @mock.patch(f'{status.__name__}.database.is_available',
                mock.MagicMock(return_value=False))
    # @mock.patch(f'{status.__name__}.filesystem.is_available',
    #             mock.MagicMock(return_value=True))
    def test_database_not_available(self):
        """Database is unavailable."""
        response_data, code, headers = status.service_status()
        self.assertEqual(code, HTTPStatus.SERVICE_UNAVAILABLE,
                         'Returns 503 Service Unavailable')
        self.assertFalse(response_data['database'], 'Database reports not OK')
        # self.assertTrue(response_data['filesystem'], 'Filesystem reports OK')

    # @mock.patch(f'{status.__name__}.database.is_available',
    #             mock.MagicMock(return_value=True))
    # # @mock.patch(f'{status.__name__}.filesystem.is_available',
    # #             mock.MagicMock(return_value=False))
    # def test_filesystem_not_available(self):
    #     """Database is unavailable."""
    #     response_data, code, headers = status.service_status()
    #     self.assertEqual(code, HTTPStatus.SERVICE_UNAVAILABLE,
    #                      'Returns 503 Service Unavailable')
    #     self.assertTrue(response_data['database'], 'Database reports OK')
    #     # self.assertFalse(response_data['filesystem'], 'Filesystem not OK')
