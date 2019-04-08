"""Test availability check for database."""

from unittest import TestCase, mock
import io
from functools import partial

from flask import Flask
from sqlalchemy.exc import OperationalError

from .. import uploads as upload_db


def raise_operationalerror(*args, **kwargs):
    """Raise an :class:`.OperationalError`."""
    raise OperationalError('', '', '')


class TestIsAvailable(TestCase):
    """Test behavior of :func:`.upload_db.is_available`."""

    def setUp(self):
        """Create an application."""
        self.app = Flask(__name__)
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///'
        self.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        upload_db.init_app(self.app)

    def test_db_is_available(self):
        """The database is available."""
        with self.app.app_context():
            self.assertTrue(upload_db.is_available())

    @mock.patch(f'{upload_db.__name__}.db.session.execute',
                mock.MagicMock(side_effect=raise_operationalerror))
    def test_database_not_available(self):
        """The upload database is not available."""
        self.assertFalse(upload_db.is_available())
