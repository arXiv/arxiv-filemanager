"""Log controllers."""

import os
import io
import logging
from http import HTTPStatus as status
from typing import Optional, Tuple, Union, IO
from datetime import datetime

from werkzeug.exceptions import NotFound, InternalServerError

from arxiv.users import domain as auth_domain
from arxiv.base.globals import get_application_config

from ..domain import Workspace
from ..services import database
from .service_log import logger
from . import _messages as messages
from . import util

Response = Tuple[Optional[Union[dict, IO]], status, dict]


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
        workspace: Workspace = database.retrieve(upload_id)
    except IOError as ioe:
        logger.error("%s: SourceLogExistCheck: There was a problem connecting"
                     " to database: %s", upload_id, ioe)
        raise InternalServerError(messages.UPLOAD_DB_CONNECT_ERROR)
    except database.WorkspaceNotFound as nf:
        logger.info("%s: Workspace not found: '%s'", upload_id, nf)
        raise NotFound(messages.UPLOAD_NOT_FOUND) from nf

    logger.info("%s: Test for source log.", upload_id)
    headers = {
        'ETag': workspace.log.checksum,
        'Content-Length': workspace.log.size_bytes,
        'Last-Modified': workspace.log.last_modified,
        'ARXIV-OWNER': workspace.owner_user_id
    }
    return {}, status.OK, headers


def get_upload_source_log(upload_id: int, user: auth_domain.User) -> Response:
    """
    Get upload workspace log.

    This log contains details of all actions/requests/warnings/errors/etc
    related to specified upload workspace.

    Parameters
    ----------
    upload_id : int
        The unique identifier for upload workspace.

    Returns
    -------
    Standard Response tuple containing content, HTTP status, and HTTP headers.

    """
    user_string = util.format_user_information_for_logging(user)
    logger.info("%s: Download source log [%s].", upload_id, user_string)
    try:
        workspace: Workspace = database.retrieve(upload_id)
    except IOError:
        logger.error("%s: GetSourceLog: There was a problem connecting to"
                     " database.", upload_id)
        raise InternalServerError(messages.UPLOAD_DB_CONNECT_ERROR)

    except database.WorkspaceNotFound as nf:
        logger.info("%s: Workspace not found: '%s'", upload_id, nf)
        raise NotFound(messages.UPLOAD_NOT_FOUND) from nf


    filepointer = workspace.log.open_pointer('rb')
    headers = {
        "Content-disposition": f"filename={workspace.log.name}",
        'ETag': workspace.log.checksum,
        'Content-Length': workspace.log.size_bytes,
        'Last-Modified': workspace.log.last_modified,
        'ARXIV-OWNER': workspace.owner_user_id
    }
    return filepointer, status.OK, headers
