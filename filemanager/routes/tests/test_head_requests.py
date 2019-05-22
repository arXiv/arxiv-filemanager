"""Tests for routes that respond to HEAD requests."""

from unittest import TestCase, mock
from typing import Any

from arxiv.users.helpers import generate_token
from arxiv.users.auth import scopes
from arxiv.integration.api import status

from .. import upload_api
from ...factory import create_web_app


OS_ENVIRON = {'JWT_SECRET': 'foosecret'}


class TestContentLengthHeader(TestCase):
    """
    Verify that the Content-Length header is set correctly.

    Per RFC2616§14.13 the Content-Length header should be the size of the
    entity-body were the client to retrieve the resource with a GET request.
    """

    def setUp(self) -> None:
        self.app = create_web_app()
        self.app.config['JWT_SECRET'] = 'foosecret'
        self.client = self.app.test_client()
        with self.app.app_context():
            auth_scope = [scopes.READ_UPLOAD, scopes.READ_UPLOAD_SERVICE_LOGS,
                          scopes.READ_UPLOAD_LOGS]
            self.token = generate_token('123', 'foo@user.com', 'foouser',
                                        scope=auth_scope)

    @mock.patch('arxiv.users.auth.middleware.os.environ', OS_ENVIRON)
    @mock.patch(f'{upload_api.__name__}.upload.check_upload_content_exists')
    def test_check_upload_content_exists(self, mock_controller: Any) -> None:
        """HEAD request to content status endpoint returns correct length."""
        mock_controller.return_value = {}, 200, {'Content-Length': '392351'}
        with self.app.app_context():
            response = self.client.head('/filemanager/api/1/content',
                                        headers={'Authorization': self.token})

        content_length = response.headers.getlist('Content-Length')

        self.assertEqual(response.status_code, status.OK)
        self.assertEqual(len(content_length), 1, 'Only one value is returned')
        self.assertEqual(content_length[0], '392351',
                         'The value provided by the controller is returned')

    @mock.patch('arxiv.users.auth.middleware.os.environ', OS_ENVIRON)
    @mock.patch(f'{upload_api.__name__}.upload.check_upload_file_content_exists')
    def test_check_file_exists(self, mock_controller: Any) -> None:
        """HEAD request to file status endpoint returns correct length."""
        mock_controller.return_value = {}, 200, {'Content-Length': '392351'}
        with self.app.app_context():
            response = self.client.head(f'/filemanager/api/1/file.txt/content',
                                        headers={'Authorization': self.token})

        content_length = response.headers.getlist('Content-Length')

        self.assertEqual(response.status_code, status.OK)
        self.assertEqual(len(content_length), 1, 'Only one value is returned')
        self.assertEqual(content_length[0], '392351',
                         'The value provided by the controller is returned')

    @mock.patch('arxiv.users.auth.middleware.os.environ', OS_ENVIRON)
    @mock.patch(f'{upload_api.__name__}.upload.check_upload_source_log_exists')
    def test_check_upload_source_log_exists(self, mock_controller: Any) -> None:
        """HEAD request to source log endpoint returns correct length."""
        mock_controller.return_value = {}, 200, {'Content-Length': '392351'}
        with self.app.app_context():
            response = self.client.head(f'/filemanager/api/1/log',
                                        headers={'Authorization': self.token})

        content_length = response.headers.getlist('Content-Length')

        self.assertEqual(response.status_code, status.OK)
        self.assertEqual(len(content_length), 1, 'Only one value is returned')
        self.assertEqual(content_length[0], '392351',
                         'The value provided by the controller is returned')

    @mock.patch('arxiv.users.auth.middleware.os.environ', OS_ENVIRON)
    @mock.patch(f'{upload_api.__name__}.upload.check_upload_service_log_exists')
    def test_check_upload_service_log_exists(self, mock_controller: Any) -> None:
        """HEAD request to service log endpoint returns correct length."""
        mock_controller.return_value = {}, 200, {'Content-Length': '392351'}
        with self.app.app_context():
            response = self.client.head(f'/filemanager/api/log',
                                        headers={'Authorization': self.token})

        content_length = response.headers.getlist('Content-Length')

        self.assertEqual(response.status_code, status.OK)
        self.assertEqual(len(content_length), 1, 'Only one value is returned')
        self.assertEqual(content_length[0], '392351',
                         'The value provided by the controller is returned')
