"""Handle requests for the source package."""

import os
import io
import logging
from http import HTTPStatus as status
from typing import Optional, Tuple, Union, IO
from datetime import datetime

from flask import current_app
from werkzeug.exceptions import NotFound, InternalServerError, SecurityError, \
        Forbidden

from arxiv.users import domain as auth_domain
from arxiv.base.globals import get_application_config

from ..domain import Workspace, NoSuchFile
from ..services import database, storage
from ..process import strategy, check
from .transform import transform_workspace
from .service_log import logger
from . import _messages as messages
from . import util

Response = Tuple[Optional[Union[dict, IO]], status, dict]


def check_upload_content_exists(upload_id: int) -> Response:
    """
    Verify that the package content exists/is available.

    Parameters
    ----------
    upload_id : int
        The unique identifier for upload workspace.

    Returns
    -------
    dict
        Response content
    int
        HTTP status
    dict
        HTTP headers.

    """
    try:
        workspace: Workspace = database.retrieve(upload_id)
    except IOError:
        logger.error("%s: ContentExistsCheck: There was a problem connecting "
                     "to database.", upload_id)
        raise InternalServerError(messages.UPLOAD_DB_CONNECT_ERROR)
    except database.WorkspaceNotFound as nf:
        logger.info("%s: Workspace not found: '%s'", upload_id, nf)
        raise NotFound(messages.UPLOAD_NOT_FOUND)

    logger.info("%s: Upload content summary request.", upload_id)

    headers = {'ARXIV-OWNER': workspace.owner_user_id,
               'ETag': workspace.source_package.checksum,
               'Content-Length': workspace.source_package.size_bytes,
               'Last-Modified': workspace.source_package.last_modified}
    logger.debug('Respond with headers %s', headers)
    return {}, status.OK, headers


def get_upload_content(upload_id: int, user: auth_domain.User) -> Response:
    """
    Package up files for downloading as a compressed gzipped tar file.

    Parameters
    ----------
    upload_id : int
        The unique identifier for upload workspace.

    Returns
    -------
    dict
        Response content
    int
        HTTP status
    dict
        HTTP headers.

    """
    user_string = util.format_user_information_for_logging(user)
    logger.info("%s: Download workspace source content [%s].", upload_id,
                user_string)

    try:
        workspace: Workspace = database.retrieve(upload_id)
    except IOError:
        logger.error("%s: ContentDownload: There was a problem connecting "
                     "to database.", upload_id)
        raise InternalServerError(messages.UPLOAD_DB_CONNECT_ERROR)
    except database.WorkspaceNotFound as nf:
        logger.error("%s: Download workspace source content: There was a "
                     "problem connecting to database.", upload_id)
        raise NotFound(messages.UPLOAD_NOT_FOUND) from nf

    try:
        filepointer = workspace.source_package.open_pointer('rb')
    except FileNotFoundError as e:
        raise NotFound("No content in workspace") from e
    headers = {
        'ARXIV-OWNER': workspace.owner_user_id,
        'ETag': workspace.source_package.checksum,
        'Content-Length': workspace.source_package.size_bytes,
        'Last-Modified': workspace.source_package.last_modified,
        "Content-disposition": f"filename={workspace.source_package.name}"
    }
    logger.debug('Respond with headers %s', headers)
    return filepointer, status.OK, headers
