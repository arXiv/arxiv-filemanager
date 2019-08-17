"""Provides access to the uploads data store."""

from typing import Any, Dict, Optional, Callable, Generator
import time
from datetime import datetime
from pytz import UTC
from contextlib import contextmanager
from functools import wraps
from pprint import pprint

from flask import Flask, current_app
from werkzeug.local import LocalProxy
from sqlalchemy.exc import OperationalError
from retry import retry

from arxiv.base.globals import get_application_global
from arxiv.base import logging

from filemanager.domain import Workspace, FileIndex, UserFile, Error, \
    Readiness, LockState, SourceType, Status
from .models import db, DBUpload
from ..storage import create_adapter

logger = logging.getLogger(__name__)


class WorkspaceNotFound(RuntimeError):
    """Workspace not found in file manager database."""


def init_app(app: Flask) -> None:
    """Set configuration defaults and attach session to the application."""
    db.init_app(app)


# OperationalError is often due to a transient connection problem that can be
# resolved with a retry.
@retry(OperationalError, tries=3, backoff=2)
def is_available() -> bool:
    """Make a quick check to see whether databse is available."""
    try:
        db.session.execute('SELECT 1')
        return True
    except Exception as e:
        logger.error('Database not available: %s', e)
        return False


@contextmanager
def transaction() -> Generator:
    """Context manager for database transaction."""
    try:
        yield db.session
        # Only commit if there are un-flushed changes. The caller may commit
        # explicitly, e.g. to do exception handling.
        if db.session.dirty or db.session.deleted or db.session.new:
            db.session.commit()
    except Exception as e:
        logger.error('Command failed, rolling back: %s', str(e))
        db.session.rollback()
        raise


def atomic(func: Callable) -> Callable:
    """Decorate a function to run within a database transaction."""
    @wraps(func)
    def inner(*args: Any, **kwargs: Any) -> Any:
        with transaction():
            return func(*args, **kwargs)
    return inner


def retrieve(upload_id: int, skip_cache: bool = False) -> Workspace:
    """
    Get data about a upload.

    Parameters
    ----------
    upload_id : int
        Unique identifier for the upload.
    skip_cache : bool
        If `True`, will load fresh data regardless of what might already be
        around. Otherwise, will only load the same :class:`Workspace`
        instance once.

    Returns
    -------
    :class:`.Workspace`
        Data about the upload.

    Raises
    ------
    IOError
        When there is a problem querying the database.

    """
    logger.debug('Retrieve upload data from database for %s (skip_cache: %s)',
                 upload_id, skip_cache)
    # We use the application global object to create a simple cache for
    # loaded uploads. This allows us to avoid multiple queries on the same
    # state when different parts of the application need access to the same
    # upload.
    g = get_application_global()
    if g and 'uploads' not in g:
        g.uploads = {}

    if g and not skip_cache and upload_id in g.uploads:
        upload_data = g.uploads[upload_id]
    else:
        try:
            upload_data = db.session.query(DBUpload).get(upload_id)
        except OperationalError as e:
            logger.debug('Could not query database: %s', e.detail)
            raise IOError('Could not query database: %s' % e.detail) from e

        if upload_data is None:
            raise WorkspaceNotFound(f"Workspace '{upload_id}' "
                                    "not found in database.")

        if g:
            g.uploads[upload_id] = upload_data  # Cache for next time.

    args = {}
    args['upload_id'] = upload_data.upload_id
    args['owner_user_id'] = upload_data.owner_user_id
    args['created_datetime'] = upload_data.created_datetime.replace(tzinfo=UTC)
    args['modified_datetime'] = \
        upload_data.modified_datetime.replace(tzinfo=UTC)
    args['status'] = Status(upload_data.status)
    args['lock_state'] = LockState(upload_data.lock_state)
    args['source_type'] = SourceType(upload_data.source_type)

    if upload_data.last_upload_start_datetime is not None:
        args['last_upload_start_datetime'] = \
            upload_data.last_upload_start_datetime.replace(tzinfo=UTC)

    if upload_data.last_upload_completion_datetime is not None:
        args['last_upload_completion_datetime'] = \
            upload_data.last_upload_completion_datetime.replace(tzinfo=UTC)

    if upload_data.last_upload_logs is not None:
        args['last_upload_logs'] = upload_data.last_upload_logs

    if upload_data.last_upload_file_summary is not None:
        args['last_upload_file_summary'] = upload_data.last_upload_file_summary

    if upload_data.last_upload_readiness is not None:
        args['last_upload_readiness'] \
            = Readiness(upload_data.last_upload_readiness)
    args['_storage'] = create_adapter(current_app)
    workspace = Workspace(**args)

    if upload_data.files:
        workspace.files = FileIndex(
            source={p: UserFile.from_dict(d, workspace)
                    for p, d in upload_data.files['source'].items()},
            ancillary={p: UserFile.from_dict(d, workspace)
                    for p, d in upload_data.files['ancillary'].items()},
            removed={p: UserFile.from_dict(d, workspace)
                    for p, d in upload_data.files['removed'].items()},
            system={p: UserFile.from_dict(d, workspace)
                    for p, d in upload_data.files['system'].items()
            }
        )
    if upload_data.errors:
        for datum in upload_data.errors:
            workspace._insert_error(Error.from_dict(datum))
    workspace.initialize()
    return workspace


def store(new_upload_data: Workspace) -> Workspace:
    """
    Create a new record for a :class:`.Workspace` in the database.

    Parameters
    ----------
    upload_data : :class:`.Workspace`

    Raises
    ------
    IOError
        When there is a problem querying the database.
    RuntimeError
        When there is some other problem.
    """
    upload_data = DBUpload(owner_user_id=new_upload_data.owner_user_id,
                           created_datetime=new_upload_data.created_datetime,
                           modified_datetime=new_upload_data.modified_datetime,
                           status=new_upload_data.status.value)
    db.session.add(upload_data)
    db.session.commit()
    new_upload_data.upload_id = upload_data.upload_id
    return new_upload_data


def create(owner_user_id: str,
           status: Status = Status.ACTIVE) \
        -> Workspace:
    current_datetime = datetime.now(UTC)
    upload_data = DBUpload(owner_user_id=owner_user_id,
                           created_datetime=current_datetime,
                           modified_datetime=current_datetime,
                           status=status.value)
    db.session.add(upload_data)
    db.session.commit()
    return Workspace(upload_id=upload_data.upload_id,
                           owner_user_id=owner_user_id,
                           created_datetime=current_datetime,
                           modified_datetime=current_datetime,
                           _storage=create_adapter(current_app))


def update(workspace: Workspace) -> None:
    """
    Update the database with the latest :class:`.Workspace`.

    Parameters
    ----------
    the_thing : :class:`.Workspace`

    Raises
    ------
    IOError
        When there is a problem querying the database.
    RuntimeError
        When there is some other problem.

    """
    if not workspace.upload_id:
        raise RuntimeError('The upload data has no id!')
    try:
        upload_data = db.session.query(DBUpload) \
            .get(workspace.upload_id)
    except OperationalError as e:
        raise IOError('Could not query database: %s' % e.detail) from e
    if upload_data is None:
        raise RuntimeError('Cannot find the thing!')

    upload_data.owner_user_id = workspace.owner_user_id

    # We won't let client update created_datetime

    upload_data.last_upload_start_datetime = \
        workspace.last_upload_start_datetime
    upload_data.last_upload_completion_datetime = \
        workspace.last_upload_completion_datetime
    upload_data.last_upload_logs = workspace.last_upload_logs
    upload_data.last_upload_file_summary = workspace.last_upload_file_summary
    upload_data.last_upload_readiness = workspace.last_upload_readiness.value
    upload_data.status = workspace.status.value
    upload_data.lock_state = workspace.lock_state.value
    upload_data.source_type = workspace.source_type.value
    upload_data.modified_datetime = workspace.modified_datetime

    upload_data.files = {
        'source': {p: f.to_dict() for p, f in workspace.files.source.items()},
        'ancillary': {p: f.to_dict()
                      for p, f in workspace.files.ancillary.items()},
        'removed': {p: f.to_dict()
                    for p, f in workspace.files.removed.items()},
        'system': {p: f.to_dict() for p, f in workspace.files.system.items()},
    }
    upload_data.errors = [e.to_dict() for e in workspace._errors.values()
                          if e.is_persistant]

    # 2019-06-28: In earlier versions, the ``modified_datetime`` of the
    # workspace was set here. This would make sense when we think about the
    # upload workspace and the database entry about the upload workspace as
    # separate concepts. But in this iteration, the database entry (as data)
    # *represents* the upload workspace (concept). Attaching the notion of
    # modification directly to its representation confuses the representational
    # relationship, leading to odd behavior.
    #
    # TL;DR: the ``modified_datetime`` is managed in the domain.
    #
    # --Erick

    db.session.add(upload_data)
    db.session.commit()
