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

from arxiv.base.globals import get_application_config

from ..domain import UploadWorkspace, NoSuchFile
from ..services import database, storage
from ..process import strategy, check
from ..serialize import serialize_workspace
from .service_log import logger
from . import _messages as messages

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
        workspace: Optional[UploadWorkspace] = database.retrieve(upload_id)
    except IOError:
        logger.error("%s: ContentExistsCheck: There was a problem connecting "
                     "to database.", upload_id)
        raise InternalServerError(messages.UPLOAD_DB_CONNECT_ERROR)

    if workspace is None:
        raise NotFound(messages.UPLOAD_NOT_FOUND)
    
    if workspace.source_package.is_stale:
        workspace.source_package.pack()

    logger.info("%s: Upload content summary request.", upload_id)

    headers = {'ARXIV-OWNER': workspace.owner_user_id, 
               'ETag': workspace.source_package.checksum,
               'Content-Length': workspace.source_package.size_bytes,
               'Last-Modified': workspace.source_package.last_modified}
    logger.debug('Respond with headers %s', headers)
    return {}, status.OK, headers


def get_upload_content(upload_id: int) -> Response:
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
    try:
        workspace: Optional[UploadWorkspace] = database.retrieve(upload_id)
    except IOError:
        logger.error("%s: ContentDownload: There was a problem connecting "
                     "to database.", upload_id)
        raise InternalServerError(messages.UPLOAD_DB_CONNECT_ERROR)

    if workspace is None:
        raise NotFound(messages.UPLOAD_NOT_FOUND)
    
    if workspace.source_package.is_stale:
        workspace.source_package.pack()

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