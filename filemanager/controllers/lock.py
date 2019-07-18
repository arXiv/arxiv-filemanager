"""Lock and unlock the workspace."""

import os
import io
import logging
from http import HTTPStatus as status
from typing import Optional, Tuple
from datetime import datetime

from flask import current_app
from werkzeug.exceptions import NotFound, InternalServerError, SecurityError, \
        Forbidden

from arxiv.users import domain as auth_domain
from arxiv.base.globals import get_application_config

from ..domain import UploadWorkspace, NoSuchFile
from ..services import database, storage
from ..process import strategy, check
from .transform import transform_workspace
from .service_log import logger
from . import _messages as messages
from . import util

Response = Tuple[Optional[dict], status, dict]

# TODO: How do we keep submitter from updating workspace while admin
# TODO: is working on it? These locks currently mean no changes are allowed.
# TODO: Is there another flavor of lock? Administrative lock? Or do admin
# TODO: and submitter coordinate on changes to upload workspace.
@database.atomic
def upload_lock(upload_id: int, user: auth_domain.User) -> Response:
    """
    Lock upload workspace.

    Prohibit all client operations on upload workspace.

    Lock may indicate process is using workspace content that otherwise
    might produce unknown results if workspace is updated during this process.
    Compile and publish are examples.

    Admins will be able to unlock upload workspace.

    Parameters
    ----------
    upload_id : int
        The unique identifier for upload workspace.

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
    logger.info("%s: Lock upload workspace [%s].", upload_id, user_string)

    try:
        workspace: Optional[UploadWorkspace] = database.retrieve(upload_id)

        if workspace is None:
            # Invalid workspace identifier
            raise NotFound(messages.UPLOAD_NOT_FOUND)

        # Lock upload workspace
        # update database
        if workspace.is_locked:
            logger.info("%s: Lock: Workspace is already locked.", upload_id)
        else:
            workspace.lock_state = UploadWorkspace.LockState.LOCKED
            if workspace.source_package.is_stale:
                workspace.source_package.pack()
            database.update(workspace)

        response_data = {'reason': messages.UPLOAD_LOCKED_WORKSPACE}
        status_code = status.OK

    except IOError:
        logger.error("%s: Lock workspace request failed ", upload_id)
        raise InternalServerError(messages.CANT_DELETE_FILE)
    except database.WorkspaceNotFound as nf:
        logger.info("%s: Workspace not found: '%s'", upload_id, nf)
        raise NotFound(messages.UPLOAD_NOT_FOUND)
    except Exception as ue:
        logger.error("Unknown error lock workspace. "
                    " Add except clauses for '%s'. DO IT NOW!", ue)
        raise InternalServerError(messages.UPLOAD_UNKNOWN_ERROR)

    headers = {'ARXIV-OWNER': workspace.owner_user_id,
               'ETag': workspace.source_package.checksum,
               'Last-Modified': workspace.source_package.last_modified}
    return response_data, status_code, headers


@database.atomic
def upload_unlock(upload_id: int, user: auth_domain.User) -> Response:
    """
    Unlock upload workspace.

    Parameters
    ----------
    upload_id : int
        The unique identifier for upload workspace.

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
    logger.info("%s: Unlock upload workspace [%s].", upload_id, user_string)

    try:
        workspace: Optional[UploadWorkspace] = database.retrieve(upload_id)

        if workspace is None:
            raise NotFound(messages.UPLOAD_NOT_FOUND)

        # Lock upload workspace
        if not workspace.is_locked:
            logger.info("%s: Unlock: Workspace is already unlocked.",
                        upload_id)
        else:
            workspace.lock_state = UploadWorkspace.LockState.UNLOCKED
            if workspace.source_package.is_stale:
                workspace.source_package.pack()
            database.update(workspace)

        response_data = {'reason': messages.UPLOAD_UNLOCKED_WORKSPACE}
        status_code = status.OK

    except IOError:
        logger.error("%s: Unlock workspace request failed ", upload_id)
        raise InternalServerError(messages.CANT_DELETE_FILE)
    except database.WorkspaceNotFound as nf:
        logger.info("%s: Workspace not found: '%s'", upload_id, nf)
        raise NotFound(messages.UPLOAD_NOT_FOUND)
    except Exception as ue:
        logger.info("%s: Unknown error in unlock workspace. "
                    " Add except clauses for '%s'. DO IT NOW!", upload_id, ue)
        raise InternalServerError(messages.UPLOAD_UNKNOWN_ERROR)

    headers = {'ARXIV-OWNER': workspace.owner_user_id,
               'ETag': workspace.source_package.checksum,
               'Last-Modified': workspace.source_package.last_modified}
    return response_data, status_code, headers
