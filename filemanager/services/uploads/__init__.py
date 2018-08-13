"""Provides access to the uploads data store."""

from typing import Any, Dict, Optional
from datetime import datetime
from werkzeug.local import LocalProxy
from sqlalchemy.exc import OperationalError
from filemanager.domain import Upload
from .models import db, DBUpload

from arxiv.base.globals import get_application_global


def init_app(app: Optional[LocalProxy]) -> None:
    """Set configuration defaults and attach session to the application."""
    db.init_app(app)


def retrieve(upload_id: int, skip_cache: bool = False) -> Optional[Upload]:
    """
    Get data about a upload.

    Parameters
    ----------
    upload_id : int
        Unique identifier for the upload.
    skip_cache : bool
        If `True`, will load fresh data regardless of what might already be
        around. Otherwise, will only load the same :class:`Upload` instance
        once.

    Returns
    -------
    :class:`.Upload`
        Data about the upload.

    Raises
    ------
    IOError
        When there is a problem querying the database.

    """
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
            raise IOError('Could not query database: %s' % e.detail) from e

        if upload_data is None:
            return None

        if g:
            g.uploads[upload_id] = upload_data      # Cache for next time.

    args = {}
    args['upload_id'] = upload_data.upload_id
    args['owner_user_id'] = upload_data.owner_user_id
    args['archive'] = upload_data.archive

    args['created_datetime'] = upload_data.created_datetime
    args['modified_datetime'] = upload_data.modified_datetime
    args['state'] = upload_data.state
    args['lock'] = upload_data.lock

    if upload_data.lastupload_start_datetime is not None:
        args['lastupload_start_datetime'] = upload_data.lastupload_start_datetime

    if upload_data.lastupload_completion_datetime is not None:
        args['lastupload_completion_datetime'] = upload_data.lastupload_completion_datetime

    if upload_data.lastupload_logs is not None:
        args['lastupload_logs'] = upload_data.lastupload_logs

    if upload_data.lastupload_file_summary is not None:
        args['lastupload_file_summary'] = upload_data.lastupload_file_summary

    if upload_data.lastupload_upload_status is not None:
        args['lastupload_upload_status'] = upload_data.lastupload_upload_status

    return Upload(**args)


def store(new_upload_data: Upload) -> Upload:
    """
    Create a new record for a :class:`.Upload` in the database.

    Parameters
    ----------
    upload_data : :class:`.Upload`

    Raises
    ------
    IOError
        When there is a problem querying the database.
    RuntimeError
        When there is some other problem.
    """
    upload_data = DBUpload(owner_user_id=new_upload_data.owner_user_id,
                           archive=new_upload_data.archive,
                           created_datetime=new_upload_data.created_datetime,
                           modified_datetime=new_upload_data.modified_datetime,
                           state=new_upload_data.state)
    try:
        db.session.add(upload_data)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise RuntimeError('Ack! %s' % e) from e
    new_upload_data.upload_id = upload_data.upload_id
    return new_upload_data


def update(upload_update_data: Upload) -> None:
    """
    Update the database with the latest :class:`.Upload`.

    Parameters
    ----------
    the_thing : :class:`.Upload`

    Raises
    ------
    IOError
        When there is a problem querying the database.
    RuntimeError
        When there is some other problem.
    """
    if not upload_update_data.upload_id:
        raise RuntimeError('The upload data has no id!')
    try:
        upload_data = db.session.query(DBUpload).get(upload_update_data.upload_id)
    except OperationalError as e:
        raise IOError('Could not query database: %s' % e.detail) from e
    if upload_data is None:
        raise RuntimeError('Cannot find the thing!')

    # owner_user_id, archive
    upload_data.owner_user_id = upload_update_data.owner_user_id
    upload_data.archive = upload_update_data.archive

    # We won't let client update created_datetime

    upload_data.lastupload_start_datetime = upload_update_data.lastupload_start_datetime
    upload_data.lastupload_completion_datetime = upload_update_data.lastupload_completion_datetime
    upload_data.lastupload_logs = upload_update_data.lastupload_logs
    upload_data.lastupload_file_summary = upload_update_data.lastupload_file_summary
    upload_data.lastupload_upload_status = upload_update_data.lastupload_upload_status
    upload_data.state = upload_update_data.state
    upload_data.lock = upload_update_data.lock

    # Always set this when workspace DB entry is updated
    upload_data.modified_datetime = datetime.now()

    # TODO: Would user ever need to set the modification time manually?
    # upload_data.modified_datetime = upload_update_data.modified_datetime

    db.session.add(upload_data)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise RuntimeError('Ack! %s' % e) from e
