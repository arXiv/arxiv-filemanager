"""Provides access to the uploads data store."""

from typing import Any, Dict, Optional
from datetime import datetime
from werkzeug.local import LocalProxy
from sqlalchemy.exc import OperationalError
from filemanager.domain import Upload
from .models import db, DBUpload


def init_app(app: Optional[LocalProxy]) -> None:
    """Set configuration defaults and attach session to the application."""
    db.init_app(app)


def retrieve(upload_id: int) -> Optional[Upload]:
    """
    Get data about a upload.

    Parameters
    ----------
    upload_id : int
        Unique identifier for the upload.

    Returns
    -------
    :class:`.Upload`
        Data about the upload.

    Raises
    ------
    IOError
        When there is a problem querying the database.

    """
    try:
        upload_data = db.session.query(DBUpload).get(upload_id)
    except OperationalError as e:
        raise IOError('Could not query database: %s' % e.detail) from e
    if upload_data is None:
        return None

    args = {}
    args['upload_id'] = upload_data.upload_id
    args['created_datetime'] = upload_data.created_datetime
    args['modified_datetime'] = upload_data.modified_datetime
    args['state'] = upload_data.state

    if upload_data.lastupload_start_datetime is not None:
        args['lastupload_start_datetime'] = upload_data.lastupload_start_datetime

    if upload_data.lastupload_completion_datetime is not None:
        args['lastupload_completion_datetime'] = upload_data.lastupload_completion_datetime

    if upload_data.lastupload_logs is not None:
        args['lastupload_logs'] = upload_data.lastupload_logs

    if upload_data.lastupload_file_summary is not None:
        args['lastupload_file_summary'] = upload_data.lastupload_file_summary

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
    upload_data = DBUpload(name=new_upload_data.name,
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

    # Name will go away = leaving in case need new field whereby rename makes
    # easy to use name
    upload_data.name = upload_update_data.name
    # Won't let client update created_datetime
    upload_data.modified_datetime = upload_update_data.modified_datetime
    upload_data.lastupload_start_datetime = upload_update_data.lastupload_start_datetime
    upload_data.lastupload_completion_datetime = upload_update_data.lastupload_completion_datetime
    upload_data.lastupload_logs = upload_update_data.lastupload_logs
    upload_data.lastupload_file_summary = upload_update_data.lastupload_file_summary
    upload_data.state = upload_update_data.state
    upload_data.modified = datetime.now()

    db.session.add(upload_data)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise RuntimeError('Ack! %s' % e) from e
