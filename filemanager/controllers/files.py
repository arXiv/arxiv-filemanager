"""Handle requests for individual files."""

import os
import io
import logging
from http import HTTPStatus as status
from typing import Optional, Tuple
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

Response = Tuple[Optional[dict], status, dict]


def check_upload_file_content_exists(upload_id: int, public_file_path: str) \
        -> Response:
    """
    Verify that the specified content file exists/is available.

    Parameters
    ----------
    upload_id : int
        The unique identifier for upload workspace.
    public_file_path: str
        relative path of file to be checked.

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
        logger.error("%s: ContentFileExistsCheck: There was a problem "
                     "connecting to database.", upload_id)
        raise InternalServerError(messages.UPLOAD_DB_CONNECT_ERROR)

    if workspace is None:
        raise NotFound(messages.UPLOAD_NOT_FOUND)

    logger.info("%s: Upload content file exists request.", upload_id)

    try:
        if not workspace.exists(public_file_path):
            raise NotFound(f"File '{public_file_path}' not found.")
        u_file = workspace.get(public_file_path)
    except IOError:
        logger.error("%s: Content file exists request failed ", 
                     workspace.upload_id)
        raise InternalServerError(messages.CANT_DELETE_FILE)
    except NotFound as nf:
        logger.info("%s: File not found: %s", upload_id, nf)
        raise nf
    except SecurityError as secerr:
        logger.info("%s: %s", upload_id, secerr.description)
        # TODO: Should this be BadRequest or NotFound. I'm leaning towards
        # NotFound in order to provide as little feedback as posible to client.
        raise NotFound(messages.UPLOAD_FILE_NOT_FOUND)
    except Forbidden as forb:
        logger.info("%s: Operation forbidden: %s.", upload_id, forb)
        raise forb
    except Exception as ue:
        logger.info("Unknown error in content file exists operation. "
                    " Add except clauses for '%s'. DO IT NOW!", ue)
        raise InternalServerError(messages.UPLOAD_UNKNOWN_ERROR)

    headers = {'ARXIV-OWNER': workspace.owner_user_id,
               'ETag': u_file.checksum,
               'Content-Length': u_file.size_bytes,
               'Last-Modified': u_file.last_modified}
    return {}, status.OK, headers


def get_upload_file_content(upload_id: int, public_file_path: str) -> Response:
    """
    Get the source log associated with upload workspace.

    Parameters
    ----------
    upload_id : int
        The unique identifier for upload workspace.
    public_file_path: str
        relative path of file to be deleted.

    Returns
    -------
    dict
        Complete summary of upload processing.
    int
        An HTTP status code.
    dict
        Some extra headers to add to the response.

    """
    try:
        workspace: Optional[UploadWorkspace] = database.retrieve(upload_id)
    except IOError:
        logger.error("%s: ContentFileDownload: There was a problem connecting"
                     " to database.", workspace.upload_id)
        raise InternalServerError(messages.UPLOAD_DB_CONNECT_ERROR)

    if workspace is None:
        raise NotFound(messages.UPLOAD_NOT_FOUND)

    try:
        if not workspace.exists(public_file_path):
            raise NotFound(f"File '{public_file_path}' not found.")
        u_file = workspace.get(public_file_path)
        filepointer = workspace.open_pointer(u_file, 'rb')
    except IOError:
        logger.error("%s: Get file content request failed ", 
                     workspace.upload_id)
        raise InternalServerError(messages.CANT_DELETE_FILE)
    except NotFound as nf:
        logger.info("%s: Get file content: %s", upload_id, nf)
        raise nf
    except SecurityError as secerr:
        logger.info("%s: %s", upload_id, secerr.description)
        # TODO: Should this be BadRequest or NotFound. I'm leaning towards
        # NotFound in order to provide as little feedback as posible to client.
        raise NotFound(messages.UPLOAD_FILE_NOT_FOUND)
    except Forbidden as forb:
        logger.info("%s: Get file content forbidden: %s.", upload_id, forb)
        raise forb
    except Exception as ue:
        logger.info("Unknown error in get file content. "
                    " Add except clauses for '%s'. DO IT NOW!", ue)
        raise InternalServerError(messages.UPLOAD_UNKNOWN_ERROR)

    headers = {'ARXIV-OWNER': workspace.owner_user_id,
               'ETag': u_file.checksum,
               'Content-Length': u_file.size_bytes,
               'Last-Modified': u_file.last_modified,
               'Content-disposition': f'filename={u_file.name}'}
    return filepointer, status.OK, headers


@database.atomic
def client_delete_file(upload_id: int, public_file_path: str) -> Response:
    """
    Delete a single file.

    This request is being received from API so we need to be extra careful.

    Parameters
    ----------
    upload_id : int
        The unique identifier for the workspace in question.
    public_file_path: str
        relative path of file to be deleted.

    Returns
    -------
    dict
        Complete summary of upload processing.
    int
        An HTTP status code.
    dict
        Some extra headers to add to the response.

    """
    logger.info("%s: Delete file '%s'.", upload_id, public_file_path)

    try:
        workspace: Optional[UploadWorkspace] = database.retrieve(upload_id)
        if workspace is None:   # Invalid workspace identifier.
            raise NotFound(messages.UPLOAD_NOT_FOUND)
        if not workspace.is_active:    # Do we log anything for these requests?
            raise Forbidden(messages.UPLOAD_NOT_ACTIVE)
        if workspace.is_locked:
            raise Forbidden(messages.UPLOAD_WORKSPACE_LOCKED)

        # Call routine that will do the actual work.
        try:
            workspace.delete(workspace.get(public_file_path))
        except NoSuchFile:
            raise NotFound(messages.UPLOAD_FILE_NOT_FOUND)

        workspace.strategy = strategy.create_strategy(current_app)
        workspace.checkers = check.get_default_checkers()
        workspace.perform_checks()
        if workspace.source_package.is_stale:
            workspace.source_package.pack()
        database.update(workspace)

    except IOError:
        logger.error("%s: Delete file request failed ", upload_id)
        raise InternalServerError(messages.CANT_DELETE_FILE)
    except NotFound as nf:
        logger.info("%s: DeleteFile: %s", upload_id, nf)
        raise nf
    except SecurityError as secerr:
        logger.info("%s: %s", upload_id, secerr.description)
        # TODO: Should this be BadRequest or NotFound. I'm leaning towards
        # NotFound in order to provide as little feedback as posible to client.
        raise NotFound(messages.UPLOAD_FILE_NOT_FOUND)
    except Forbidden as forb:
        logger.info("%s: Delete file forbidden: %s.", upload_id, forb)
        raise forb
    except Exception as ue:
        raise ue
        # logger.info("Unknown error in delete file. "
        #             " Add except clauses for '%s'. DO IT NOW!", ue)
        # raise InternalServerError(UPLOAD_UNKNOWN_ERROR)

    response_data = serialize_workspace(workspace)
    response_data.update({'reason': messages.UPLOAD_DELETED_FILE})
    headers = {'ARXIV-OWNER': workspace.owner_user_id}
    return response_data, status.OK, headers


@database.atomic
def client_delete_all_files(upload_id: int) -> Response:
    """
    Delete all files uploaded by client from specified workspace.

    This request is being received from API so we need to be extra careful.

    Parameters
    ----------
    upload_id : int
        The unique identifier for the workspace in question.
    public_file_path: str
        relative path of file to be deleted.

    Returns
    -------
    dict
        Complete summary of upload processing.
    int
        An HTTP status code.
    dict
        Some extra headers to add to the response.

    """
    logger.info("%s: Deleting all uploaded files from this workspace.", 
                upload_id)

    try:
        workspace: Optional[UploadWorkspace] = database.retrieve(upload_id)

        if workspace is None:
            raise NotFound(messages.UPLOAD_NOT_FOUND)   
        if not workspace.is_active: 
            raise Forbidden(messages.UPLOAD_NOT_ACTIVE)
        if workspace.is_locked:
            raise Forbidden(messages.UPLOAD_WORKSPACE_LOCKED)

        workspace.delete_all_files()
        if workspace.source_package.is_stale:
            workspace.source_package.pack()
        database.update(workspace)

    except IOError:
        raise
        # logger.error("%s: Delete all files request failed ", upload_id)
        # raise InternalServerError(CANT_DELETE_ALL_FILES)
    except NotFound as nf:
        logger.info("%s: DeleteAllFiles: '%s'", upload_id, nf)
        raise
    except Forbidden as forb:
        logger.info("%s: Upload failed: '%s'.", upload_id, forb)
        raise forb
    except Exception as ue:
        logger.info("Unknown error in delete all files. "
                    " Add except clauses for '%s'. DO IT NOW!", ue)
        raise InternalServerError(messages.UPLOAD_UNKNOWN_ERROR)
    
    response_data = serialize_workspace(workspace)
    response_data.update({'reason': messages.UPLOAD_DELETED_ALL_FILES})
    headers = {'ARXIV-OWNER': workspace.owner_user_id}
    return response_data, status.OK, headers
