"""Release and unrelease the workspace."""

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

from ..domain import Workspace, NoSuchFile, Status
from ..services import database, storage
from ..process import strategy, check
from .transform import transform_workspace
from .service_log import logger
from . import _messages as messages
from . import util

Response = Tuple[Optional[dict], status, dict]


@database.atomic
def upload_release(upload_id: int, user: auth_domain.User) -> Response:
    """
    Release inidcates owner is done with upload workspace.

    System will schedule to remove files.

    Parameters
    ----------
    upload_id : int
        The unique identifier for upload workspace.

    Returns
    -------
    dict
        Detailed information about the workspace.
        logs - Errors and Warnings
        files - list of file details
    int
        An HTTP status code.
    dict
        Some extra headers to add to the response.

    """
    # Again, as with delete workspace, authentication, authorization, and
    # existence of workspace is verified in route level

    # Expect workspace to be in ACTIVE state.
    user_string = util.format_user_information_for_logging(user)
    try:
        workspace: Optional[Workspace] = database.retrieve(upload_id)

        if workspace is None:
            # Invalid workspace identifier
            raise NotFound(messages.UPLOAD_NOT_FOUND)

        if workspace.is_released:
            logger.info("%s: Release: Workspace has already been released "
                        "[%s].", upload_id, user_string)
            response_data = {'reason': messages.UPLOAD_RELEASED_WORKSPACE}

            status_code = status.OK # Should this be an error?
        elif workspace.is_deleted:
            logger.info("%s: Release failed: Workspace has been deleted [%s].",
                        upload_id, user_string)
            raise NotFound(messages.UPLOAD_WORKSPACE_ALREADY_DELETED)
        elif workspace.is_active:
            logger.info("%s: Release upload workspace [%s].", upload_id,
                        user_string)
            workspace.status = Status.RELEASED
            if workspace.source_package.is_stale:
                workspace.source_package.pack()
            database.update(workspace)

            response_data = {'reason': messages.UPLOAD_RELEASED_WORKSPACE}
            status_code = status.OK

    except IOError:
        logger.error("%s: Release workspace request failed.", upload_id)
        raise InternalServerError(messages.CANT_RELEASE_WORKSPACE)
    except database.WorkspaceNotFound as nf:
        logger.info("%s: Workspace not found: '%s'", upload_id, nf)
        raise NotFound(messages.UPLOAD_NOT_FOUND)

    headers = {'ARXIV-OWNER': workspace.owner_user_id,
               'ETag': workspace.source_package.checksum,
               'Last-Modified': workspace.source_package.last_modified}

    return response_data, status_code, headers


@database.atomic
def upload_unrelease(upload_id: int, user: auth_domain.User) -> Response:
    """
    Unrelease returns released workspace to active state.

    Reverses previous request to release workspace.

    Note that unrelease request does NOT restore workspace that has
    already been removed from filesystem.

    Parameters
    ----------
    upload_id : int
        The unique identifier for upload workspace.

    Returns
    -------
    dict
        Detailed information about the workspace.
        logs - Errors and Warnings
        files - list of file details
    int
        An HTTP status code.
    dict
        Some extra headers to add to the response.

    """
    # Again, as with delete workspace, authentication, authorization, and
    # existence of workspace is verified in route level
    user_string = util.format_user_information_for_logging(user)

    # Expect workspace to be in RELEASED state.
    logger.info("%s: Unrelease upload workspace [%s].", upload_id, user_string)

    try:
        # Make sure we have an upload_db_data to work with
        workspace: Optional[Workspace] = database.retrieve(upload_id)

        if workspace is None:
            raise NotFound(messages.UPLOAD_NOT_FOUND)

        # Unrelease upload workspace
        # update database
        if workspace.is_deleted:
            raise NotFound(messages.UPLOAD_WORKSPACE_ALREADY_DELETED)

        if workspace.is_active:
            logger.info("%s: Unrelease: Workspace is already active [%s].",
                        upload_id, user_string)
            response_data = {'reason': messages.UPLOAD_UNRELEASED_WORKSPACE}
            status_code = status.OK     # Should this be an error?
        elif workspace.is_released:
            logger.info("%s: Unrelease upload workspace [%s].", upload_id,
                        user_string)

            workspace.status = Status.ACTIVE
            if workspace.source_package.is_stale:
                workspace.source_package.pack()
            database.update(workspace)

            response_data = {'reason': messages.UPLOAD_UNRELEASED_WORKSPACE}
            status_code = status.OK

    except IOError:
        logger.error("%s: Unrelease workspace request failed.", upload_id)
        raise InternalServerError(messages.CANT_DELETE_FILE)
    except database.WorkspaceNotFound as nf:
        logger.info("%s: Workspace not found: '%s'", upload_id, nf)
        raise NotFound(messages.UPLOAD_NOT_FOUND)

    headers = {'ARXIV-OWNER': workspace.owner_user_id,
               'ETag': workspace.source_package.checksum,
               'Last-Modified': workspace.source_package.last_modified}
    return response_data, status_code, headers
