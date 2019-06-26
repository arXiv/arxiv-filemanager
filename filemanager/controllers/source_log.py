"""Log controllers."""

import os
import io
import logging
from http import HTTPStatus as status
from typing import Optional, Tuple
from datetime import datetime

from werkzeug.exceptions import NotFound, InternalServerError

from arxiv.base.globals import get_application_config

from ..domain import UploadWorkspace
from ..services import database
from .service_log import logger
from . import _messages as messages

Response = Tuple[Optional[dict], status, dict]


def check_upload_source_log_exists(upload_id: int) -> Response:
    """
    Determine if source log associated with upload workspace exists.

    Note: This routine currently retrieves the source log for active upload
    workspaces. Technically, the upload source log is available for a 'deleted'
    workspace, since we stash this away before we actually delete the
    workspace. The justification to save is because the upload source log
    contains useful information that the admins sometime desire after a
    submission has been published and the associated workspace deleted.

    Parameters
    ----------
    upload_id : int
        The unique identifier for upload workspace.

    Returns
    -------

    """
    try:
        workspace: Optional[UploadWorkspace] = database.retrieve(upload_id)
    except IOError:
        logger.error("%s: SourceLogExistCheck: There was a problem connecting"
                     " to database.", workspace.upload_id)
        raise InternalServerError(messages.UPLOAD_DB_CONNECT_ERROR)

    if workspace is None:
        raise NotFound(messages.UPLOAD_NOT_FOUND)

    logger.info("%s: Test for source log.", upload_id)
    headers = {
        'ETag': workspace.log.checksum,
        'Content-Length': workspace.log.size_bytes,
        'Last-Modified': workspace.log.last_modified,
        'ARXIV-OWNER': workspace.owner_user_id
    }
    return {}, status.OK, headers


def get_upload_source_log(upload_id: int) -> Response:
    """
    Get upload workspace log.

    This log contains details of all actions/requests/warnings/errors/etc related
    to specified upload workspace.

    Parameters
    ----------
    upload_id : int
        The unique identifier for upload workspace.

    Returns
    -------
    Standard Response tuple containing content, HTTP status, and HTTP headers.
    """
    try:
        workspace: Optional[UploadWorkspace] = database.retrieve(upload_id)
    except IOError:
        logger.error("%s: GetSourceLog: There was a problem connecting to"
                     " database.", workspace.upload_id)
        raise InternalServerError(messages.UPLOAD_DB_CONNECT_ERROR)

    if workspace is None:
        raise NotFound(messages.UPLOAD_NOT_FOUND)


    filepointer = workspace.log.open_pointer('rb')
    if filepointer:
        name = filepointer.name
    else:
        name = ""

    headers = {
        "Content-disposition": f"filename={name}",
        'ETag': workspace.log.checksum,
        'Content-Length': workspace.log.size_bytes,
        'Last-Modified': workspace.log.last_modified,
        'ARXIV-OWNER': workspace.owner_user_id
    }
    return filepointer, status.OK, headers