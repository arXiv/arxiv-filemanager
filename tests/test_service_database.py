"""Tests for :mod:`filemanager.services.database`."""

from unittest import TestCase, mock
import tempfile
import shutil
from datetime import datetime
from pytz import UTC
from typing import Any
import sqlalchemy
from filemanager.services import database
from filemanager.domain import Workspace, Error, UserFile, Status
from filemanager.services.storage import SimpleStorageAdapter


class TestTranslate(TestCase):
    """Tests for :mod:`.database.translate` for fidelity."""

    def test_translate_error(self):
        """Translate an :class:`.Error` to and from a ``dict``."""
        error = Error(severity=Error.Severity.FATAL, path='foo/path.md',
                               message='This is a message',
                               is_persistant=True)
        self.assertEqual(error, Error.from_dict(error.to_dict()),
                         'Error is preserved with fidelity')
        error = Error(severity=Error.Severity.FATAL, path='foo/path.md',
                               message='This is a message',
                               is_persistant=False)
        self.assertEqual(error, Error.from_dict(error.to_dict()),
                         'Error is preserved with fidelity')

    def test_translate_file(self):
        """Translate an :class:`.UserFile` to and from a ``dict``."""
        workspace = mock.MagicMock(spec=Workspace)
        u_file = UserFile(workspace=workspace,
                              path='foo/path.md', is_ancillary=True,
                              size_bytes=54_022)
        self.assertEqual(u_file,
                         UserFile.from_dict(u_file.to_dict(), workspace),
                         'File is preserved with fidelity')

    def test_translate_file_with_errors(self):
        """Translate an :class:`.UserFile` with errors."""
        workspace = mock.MagicMock(spec=Workspace)
        u_file = UserFile(workspace=workspace,
                              path='foo/path.md', is_ancillary=True,
                              size_bytes=54_022, _errors=[
                                  Error(severity=Error.Severity.FATAL,
                                        path='foo/path.md',
                                        message='This is a fatal error',
                                        is_persistant=True),
                                  Error(severity=Error.Severity.WARNING,
                                        path='foo/path.md',
                                        message='This is a message',
                                        is_persistant=False),
                              ])
        translated_file = UserFile.from_dict(u_file.to_dict(), workspace)
        self.assertEqual(len(translated_file.errors), 1,
                         'Only one file is preserved')
        self.assertEqual(translated_file.errors[0].severity,
                         Error.Severity.FATAL,
                         'The persistant error is preserved')


class TestUploadGetter(TestCase):
    """The method :meth:`.get_an_upload` retrieves data about uploads."""

    def setUp(self) -> None:
        """Initialize an in-memory SQLite database."""

        self.database = database
        app = mock.MagicMock(
            config={
                # 'SQLALCHEMY_DATABASE_URI': 'mysql://bob:dole@localhost/ack',
                'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
                'SQLALCHEMY_TRACK_MODIFICATIONS': False
            }, extensions={}, root_path=''
        )
        database.db.init_app(app)
        database.db.app = app
        database.db.create_all()

        self.data = dict(owner_user_id='dlf2',
                         created_datetime=datetime.now(UTC),
                         modified_datetime=datetime.now(UTC),
                         status=Status.ACTIVE.value)
        self.dbupload = self.database.DBUpload(**self.data)  # type: ignore
        self.database.db.session.add(self.dbupload)  # type: ignore
        self.database.db.session.commit()  # type: ignore
        self.base_path = tempfile.mkdtemp()

    def tearDown(self) -> None:
        """Clear the database and tear down all tables."""
        database.db.session.remove()
        database.db.drop_all()
        shutil.rmtree(self.base_path)

    @mock.patch(f'{database.__name__}.current_app',
                mock.MagicMock(config={
                    'STORAGE_BACKEND': 'simple',
                    'STORAGE_BASE_PATH': tempfile.mkdtemp()
                }))
    def test_get_an_upload_that_exists(self) -> None:
        """When the uploads exists, returns a :class:`.Upload`."""
        upload = self.database.retrieve(1)  # type: ignore
        self.assertIsInstance(upload, Workspace)
        self.assertEqual(upload.upload_id, 1)
        self.assertEqual(upload.owner_user_id, self.data['owner_user_id'])
        self.assertEqual(upload.created_datetime,
                         self.data['created_datetime'])

    def test_get_an_upload_that_doesnt_exist(self) -> None:
        """When the upload doesn't exist, returns None."""
        with self.assertRaises(self.database.WorkspaceNotFound):
            database.retrieve(666)
#
    @mock.patch('filemanager.services.database.db.session.query')
    def test_get_upload_when_db_is_unavailable(self, mock_query: Any) -> None:
        """When the database squawks, raises an IOError."""

        def raise_op_error(*args: str, **kwargs: str) -> None:
            raise sqlalchemy.exc.OperationalError('statement', {}, None)

        mock_query.side_effect = raise_op_error
        with self.assertRaises(IOError):
            self.database.retrieve(1, skip_cache=True)  # type: ignore


class TestUploadCreator(TestCase):
    """:func:`.store_a_thing` creates a new record in the database."""

    def setUp(self) -> None:
        """Initialize an in-memory SQLite database."""
        self.database = database
        app = mock.MagicMock(
            config={
                # 'SQLALCHEMY_DATABASE_URI': 'mysql://bob:dole@localhost/ack',
                'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
                'SQLALCHEMY_TRACK_MODIFICATIONS': False
            }, extensions={}, root_path=''
        )
        self.database.db.init_app(app)  # type: ignore
        self.database.db.app = app  # type: ignore
        self.database.db.create_all()  # type: ignore

        self.data = {'owner_user_id': 'dlf2',
                     'created_datetime': datetime.now(UTC),
                     'modified_datetime': datetime.now(UTC),
                     'status': Status.ACTIVE.value}
        self.dbupload = self.database.DBUpload(**self.data)  # type: ignore
        self.database.db.session.add(self.dbupload)  # type: ignore
        self.database.db.session.commit()  # type: ignore
        self.base_path = tempfile.mkdtemp()

    def tearDown(self) -> None:
        """Clear the database and tear down all tables."""
        self.database.db.session.remove()  # type: ignore
        self.database.db.drop_all()  # type: ignore
        shutil.rmtree(self.base_path)

    def test_store_an_upload(self) -> None:
        """A new row is added for the upload."""
        existing_upload = Workspace(
            upload_id='98765',
            owner_user_id='dlf2',
            created_datetime=datetime.now(UTC),
            modified_datetime=datetime.now(UTC),
            _strategy=mock.MagicMock(),
            _storage=SimpleStorageAdapter(self.base_path)
        )

        self.database.store(existing_upload)  # type: ignore
        self.assertGreater(existing_upload.upload_id, 0,
                           "Upload.id is updated with pk id")

        dbupload = self.database.db.session \
            .query(self.database.DBUpload) \
            .get(existing_upload.upload_id)  # type: ignore

        self.assertEqual(dbupload.owner_user_id, existing_upload.owner_user_id)


class TestUploadUpdater(TestCase):
    """:func:`.update_an_upload` updates the db with :class:`.Upload` data."""

    def setUp(self) -> None:
        """Initialize an in-memory SQLite database."""

        self.database = database
        app = mock.MagicMock(
            config={
                # 'SQLALCHEMY_DATABASE_URI': 'mysql://bob:dole@localhost/ack',
                'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
                'SQLALCHEMY_TRACK_MODIFICATIONS': False
            }, extensions={}, root_path=''
        )
        self.database.db.init_app(app)  # type: ignore
        self.database.db.app = app  # type: ignore
        self.database.db.create_all()  # type: ignore

        self.data = dict(owner_user_id='dlf2',
                         created_datetime=datetime.now(UTC))
        self.dbupload = self.database.DBUpload(**self.data)  # type: ignore
        self.database.db.session.add(self.dbupload)  # type: ignore
        self.database.db.session.commit()  # type: ignore

        self.base_path = tempfile.mkdtemp()

    def tearDown(self) -> None:
        """Clear the database and tear down all tables."""
        self.database.db.session.remove()  # type: ignore
        self.database.db.drop_all()  # type: ignore
        shutil.rmtree(self.base_path)
    #
    def test_update_an_upload(self) -> None:
        """The db is updated with the current state of the :class:`.Upload`."""
        an_upload = Workspace(
            upload_id=self.dbupload.upload_id,
            owner_user_id='dlf2',
            created_datetime=datetime.now(UTC),
            modified_datetime=datetime.now(UTC),
            _strategy=mock.MagicMock(),
            _storage=SimpleStorageAdapter(self.base_path)
        )
        self.database.update(an_upload)  # type: ignore

        dbupload = self.database.db.session \
            .query(self.database.DBUpload) \
            .get(self.dbupload.upload_id)  # type: ignore

        # TODO: more assertions here.
        self.assertEqual(dbupload.status, an_upload.status.value)

    @mock.patch('filemanager.services.database.db.session.query')
    def test_operationalerror_is_handled(self, mock_query: Any) -> None:
        """When the db raises an OperationalError, an IOError is raised."""
        an_upload = Workspace(
            upload_id=self.dbupload.upload_id,
            owner_user_id='dlf2',
            created_datetime=datetime.now(UTC),
            modified_datetime=datetime.now(UTC),
            _strategy=mock.MagicMock(),
            _storage=SimpleStorageAdapter(self.base_path)
        )

        def raise_op_error(*args, **kwargs) -> None:  # type: ignore
            """Function designed to raise operational error."""
            raise sqlalchemy.exc.OperationalError('statement', {}, None)

        mock_query.side_effect = raise_op_error

        with self.assertRaises(IOError):
            self.database.update(an_upload)  # type: ignore

    def test_upload_really_does_not_exist(self) -> None:
        """If the :class:`.Upload` doesn't exist, a RuntimeError is raised."""
        an_update = Workspace(
            upload_id=666,
            owner_user_id='12345',
            created_datetime=datetime.now(UTC),
            modified_datetime=datetime.now(UTC),
            _strategy=mock.MagicMock(),
            _storage=SimpleStorageAdapter(self.base_path)
        )  # Unlikely to exist.
        with self.assertRaises(RuntimeError):
            self.database.update(an_update)  # type: ignore

    @mock.patch('filemanager.services.database.db.session.query')
    def test_thing_does_not_exist(self, mock_query: Any) -> None:
        """If the :class:`.Upload` doesn't exist, a RuntimeError is raised."""
        an_update = Workspace(
            upload_id=666,
            owner_user_id='dlf2',
            created_datetime=datetime.now(UTC),
            modified_datetime=datetime.now(UTC),
            _strategy=mock.MagicMock(),
            _storage=SimpleStorageAdapter(self.base_path)
        )
        mock_query.return_value = mock.MagicMock(
            get=mock.MagicMock(return_value=None)
        )
        with self.assertRaises(RuntimeError):
            self.database.update(an_update)  # type: ignore
