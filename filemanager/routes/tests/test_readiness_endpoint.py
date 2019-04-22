from unittest import TestCase, mock

from http import HTTPStatus

from .. import upload_api
from ...factory import create_web_app


OS_ENVIRON = {'JWT_SECRET': 'foosecret'}
ALL_OK = ({'database': True, 'filesystem': True}, HTTPStatus.OK, {})
NOT_OK = ({'database': False, 'filesystem': False},
          HTTPStatus.SERVICE_UNAVAILABLE, {})


class TestReadinessEndpoint(TestCase):
    """Verify the readiness endpoint."""

    def setUp(self):
        """Create and configure an app."""
        self.app = create_web_app()
        self.app.config['JWT_SECRET'] = 'foosecret'
        self.client = self.app.test_client()

    @mock.patch('arxiv.users.auth.middleware.os.environ', OS_ENVIRON)
    @mock.patch(f'{upload_api.__name__}.status.service_status',
                mock.MagicMock(return_value=ALL_OK))
    def test_get_readiness_endpoint(self):
        """GET request to readiness endpoint."""
        with self.app.app_context():
            response = self.client.get('/filemanager/api/status')
            response_data = response.get_json()

        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertTrue(response_data['database'], 'Database is available')
        self.assertTrue(response_data['filesystem'], 'Filesystem is available')

    @mock.patch('arxiv.users.auth.middleware.os.environ', OS_ENVIRON)
    @mock.patch(f'{upload_api.__name__}.status.service_status',
                mock.MagicMock(return_value=NOT_OK))
    def test_not_ready(self):
        """GET request to readiness endpoint."""
        with self.app.app_context():
            response = self.client.get('/filemanager/api/status')
            response_data = response.get_json()

        self.assertEqual(response.status_code, HTTPStatus.SERVICE_UNAVAILABLE)
        self.assertFalse(response_data['database'], 'Database unavailable')
        self.assertFalse(response_data['filesystem'], 'Filesystem unavailable')
