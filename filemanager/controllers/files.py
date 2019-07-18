"""Handle requests for individual files."""

import os
import io
import logging
from http import HTTPStatus as status
from typing import Optional, Tuple, Union, IO
from datetime import datetime

from flask import current_app
from werkzeug.exceptions import NotFound, InternalServerError, SecurityError, \
        Forbidden, HTTPException

from arxiv.users import domain as auth_domain
from arxiv.base.globals import get_application_config

from ..domain import UploadWorkspace, NoSuchFile
from ..domain.uploads.exceptions import UploadFileSecurityError
from ..services import database, storage
from ..process import strategy, check
from .transform import transform_workspace
from .service_log import logger
from . import _messages as messages
from . import util

Response = Tuple[Optional[Union[dict, IO]], status, dict]


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
        workspace: UploadWorkspace = database.retrieve(upload_id)
    except IOError:
        logger.error("%s: ContentFileExistsCheck: There was a problem "
                     "connecting to database.", upload_id)
        raise InternalServerError(messages.UPLOAD_DB_CONNECT_ERROR)
    except database.WorkspaceNotFound as nf:
        logger.info("%s: Workspace not found: '%s'", upload_id, nf)
        raise NotFound(messages.UPLOAD_NOT_FOUND)

    logger.info("%s: Upload content file exists request.", upload_id)

    try:
        if not workspace.exists(public_file_path):
            raise NotFound(f"File '{public_file_path}' not found.")
        u_file = workspace.get(public_file_path)
    except HTTPException as httpe:
        # Werkzeug HTTPExceptions are explicitly raised, so these should always
        # propagate.
        logger.info("%s: Operation failed: '%s'.", httpe, upload_id)
        raise httpe
    except IOError:
        logger.error("%s: Content file exists request failed ",
                     workspace.upload_id)
        raise InternalServerError(messages.CANT_DELETE_FILE)
    except SecurityError as secerr:
        logger.info("%s: %s", upload_id, secerr.description)
        # TODO: Should this be BadRequest or NotFound. I'm leaning towards
        # NotFound in order to provide as little feedback as posible to client.
        raise NotFound(messages.UPLOAD_FILE_NOT_FOUND)
    except Exception as ue:
        logger.error("Unknown error in content file exists operation. "
                    " Add except clauses for '%s'. DO IT NOW!", ue)
        raise InternalServerError(messages.UPLOAD_UNKNOWN_ERROR)

    headers = {'ARXIV-OWNER': workspace.owner_user_id,
               'ETag': u_file.checksum,
               'Content-Length': u_file.size_bytes,
               'Last-Modified': u_file.last_modified}
    return {}, status.OK, headers


def get_upload_file_content(upload_id: int, public_file_path: str,
                            user: auth_domain.User) -> Response:
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
    user_string = util.format_user_information_for_logging(user)
    logger.info("%s: Download workspace source content [%s].", upload_id,
                user_string)
    try:
        workspace: UploadWorkspace = database.retrieve(upload_id)
    except IOError:
        logger.error("%s: ContentFileDownload: There was a problem connecting"
                     " to database.", upload_id)
        raise InternalServerError(messages.UPLOAD_DB_CONNECT_ERROR)
    except database.WorkspaceNotFound as nf:
        logger.info("%s: Workspace not found: '%s'", upload_id, nf)
        raise NotFound(messages.UPLOAD_NOT_FOUND)

    try:
        if not workspace.exists(public_file_path):
            raise NotFound(f"File '{public_file_path}' not found.")
        u_file = workspace.get(public_file_path)
        filepointer = workspace.open_pointer(u_file, 'rb')
    except HTTPException as httpe:
        # Werkzeug HTTPExceptions are explicitly raised, so these should always
        # propagate.
        logger.info("%s: Operation failed: '%s'.", httpe, upload_id)
        raise httpe
    except IOError:
        logger.error("%s: Get file content request failed ",
                     workspace.upload_id)
        raise InternalServerError(messages.CANT_DELETE_FILE)
    except SecurityError as secerr:
        logger.info("%s: %s", upload_id, secerr.description)
        # TODO: Should this be BadRequest or NotFound. I'm leaning towards
        # NotFound in order to provide as little feedback as posible to client.
        raise NotFound(messages.UPLOAD_FILE_NOT_FOUND)
    except Exception as ue:
        logger.error("Unknown error in get file content. "
                    " Add except clauses for '%s'. DO IT NOW!", ue)
        raise InternalServerError(messages.UPLOAD_UNKNOWN_ERROR)

    headers = {'ARXIV-OWNER': workspace.owner_user_id,
               'ETag': u_file.checksum,
               'Content-Length': u_file.size_bytes,
               'Last-Modified': u_file.last_modified,
               'Content-disposition': f'filename={u_file.name}'}
    return filepointer, status.OK, headers


@database.atomic
def client_delete_file(upload_id: int, public_file_path: str,
                       user: auth_domain.User) -> Response:
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
    user_string = util.format_user_information_for_logging(user)
    logger.info("%s: Delete file '%s' [%s].", upload_id, public_file_path,
                user_string)

    try:
        workspace: UploadWorkspace = database.retrieve(upload_id)
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

    except HTTPException as httpe:
        # Werkzeug HTTPExceptions are explicitly raised, so these should always
        # propagate.
        logger.info("%s: Operation failed: '%s'.", httpe, upload_id)
        raise httpe
    except database.WorkspaceNotFound as nf:
        logger.info("%s: Workspace not found: '%s'", upload_id, nf)
        raise NotFound(messages.UPLOAD_NOT_FOUND) from nf
    except FileNotFoundError as nf:
        logger.info("%s: DeleteFile: %s", upload_id, nf)
        raise NotFound(messages.UPLOAD_FILE_NOT_FOUND) from nf
    except UploadFileSecurityError as secerr:
        logger.info("%s: %s", upload_id, secerr.description)
        # TODO: Should this be BadRequest or NotFound. I'm leaning towards
        # NotFound in order to provide as little feedback as posible to client.
        raise NotFound(messages.UPLOAD_FILE_NOT_FOUND) from secerr
    except IOError as ioe:
        logger.error("%s: Delete file request failed: %s ", upload_id, ioe)
        raise InternalServerError(messages.CANT_DELETE_FILE) from ioe
    except Exception as ue:
        logger.info("%s: Unknown error in delete file. "
                    " Add except clauses for '%s'. DO IT NOW!", upload_id, ue)
        raise InternalServerError(messages.UPLOAD_UNKNOWN_ERROR)

    response_data = transform_workspace(workspace)
    response_data.update({'reason': messages.UPLOAD_DELETED_FILE})
    headers = {'ARXIV-OWNER': workspace.owner_user_id,
               'ETag': workspace.source_package.checksum,
               'Last-Modified': workspace.source_package.last_modified}
    return response_data, status.OK, headers


@database.atomic
def client_delete_all_files(upload_id: int, user: auth_domain.User) \
        -> Response:
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
    user_string = util.format_user_information_for_logging(user)
    logger.info("%s: Deleting all uploaded files from this workspace [%s].",
                upload_id, user_string)

    try:
        workspace: UploadWorkspace = database.retrieve(upload_id)
        if not workspace.is_active:
            raise Forbidden(messages.UPLOAD_NOT_ACTIVE)
        if workspace.is_locked:
            raise Forbidden(messages.UPLOAD_WORKSPACE_LOCKED)

        workspace.delete_all_files()
        if workspace.source_package.is_stale:
            workspace.source_package.pack()
        database.update(workspace)
    except HTTPException as httpe:
        # Werkzeug HTTPExceptions are explicitly raised, so these should always
        # propagate.
        logger.info("%s: Operation failed: '%s'.", httpe, upload_id)
        raise httpe
    except database.WorkspaceNotFound as nf:
        logger.info("%s: Workspace not found: '%s'", upload_id, nf)
        raise NotFound(messages.UPLOAD_NOT_FOUND)

    except IOError:
        raise
        # logger.error("%s: Delete all files request failed ", upload_id)
        # raise InternalServerError(CANT_DELETE_ALL_FILES)
    except NotFound as nf:
        logger.info("%s: DeleteAllFiles: '%s'", upload_id, nf)
        raise
    except database.WorkspaceNotFound as nf:
        logger.info("%s: Workspace not found: '%s'", upload_id, nf)
        raise NotFound(messages.UPLOAD_NOT_FOUND) from nf
    except Exception as ue:
        logger.info("%s: Unknown error in delete all files. "
                    " Add except clauses for '%s'. DO IT NOW!", upload_id, ue)
        raise InternalServerError(messages.UPLOAD_UNKNOWN_ERROR) from ue

    response_data = transform_workspace(workspace)
    response_data.update({'reason': messages.UPLOAD_DELETED_ALL_FILES})
    headers = {'ARXIV-OWNER': workspace.owner_user_id,
               'ETag': workspace.source_package.checksum,
               'Last-Modified': workspace.source_package.last_modified}
    return response_data, status.OK, headers
