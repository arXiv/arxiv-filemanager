"""Controllers for checkpoint-related operations."""

from typing import Tuple, Optional, Union, IO
from http import HTTPStatus as status
import traceback

from werkzeug.exceptions import NotFound, InternalServerError, SecurityError, \
    Forbidden, BadRequest, HTTPException

from arxiv.users import domain as auth_domain

from ..domain.uploads.exceptions import NoSourceFilesToCheckpoint, \
    UploadFileSecurityError
from ..services import database
from .service_log import logger
from . import _messages as messages
from . import util, transform

Response = Tuple[Optional[Union[dict, IO]], status, dict]


@database.atomic
def create_checkpoint(upload_id: int, user: auth_domain.User) -> Response:
    """
    Create checkpoint.

    Parameters
    ----------
    upload_id : int
        The unique identifier for upload workspace.
    use : str
        User making create checkpoint request.

    Returns
    -------
    tuple
        Standard Response tuple containing response content, HTTP status, and
        HTTP headers.

    """
    user_string = util.format_user_information_for_logging(user)
    logger.info("%s: Create checkpoint [%s].", upload_id, user_string)

    try:
        # Make sure we have an upload_db_data to work with
        workspace = database.retrieve(upload_id)
        checksum = workspace.create_checkpoint(user)

        ###
        # Lock upload workspace
        # update database
        # if upload_db_data.lock == Upload.LOCKED:
        #    logger.info("%s: Lock: Workspace is already locked.", upload_id)
        # else:
        #    upload_db_data.lock = Upload.LOCKED
        #
        # Store in DB
        #   uploads.update(upload_db_data)
        ###

        database.update(workspace)    # Store in DB
        response_data = {'reason': messages.UPLOAD_CREATED_CHECKPOINT}  # Get rid of pylint error
        status_code = status.OK
    except IOError as ioe:
        logger.error("%s: Create checkpoint request failed ", upload_id)
        raise InternalServerError(messages.CANT_DELETE_FILE) from ioe
    except NoSourceFilesToCheckpoint as nsf:
        logger.info("%s: No source files to checkpoint: %s", upload_id, nsf)
        raise BadRequest(messages.UPLOAD_WORKSPACE_IS_EMPTY) from nsf
    except database.WorkspaceNotFound as nf:
        logger.info("%s: Workspace not found: '%s'", upload_id, nf)
        raise NotFound(messages.UPLOAD_NOT_FOUND) from nf
    except Exception as ue:
        logger.info("%s: Unknown error create checkpoint. "
                    " Add except clauses for '%s'. DO IT NOW!", upload_id, ue)
        raise InternalServerError(messages.UPLOAD_UNKNOWN_ERROR)

    return response_data, status_code, {'ETag': checksum}


def list_checkpoints(upload_id: int, user: auth_domain.User) -> Response:
    """
    List checkpoints.

    Parameters
    ----------
    upload_id : int
        The unique identifier for upload workspace.
    user : str
        User making create checkpoint request.

    Returns
    -------
    tuple
        Standard Response tuple containing response content, HTTP status, and
        HTTP headers.
        Response content includes details for each checkpoint.

    """
    user_string = util.format_user_information_for_logging(user)
    logger.info("%s: List checkpoints [%s].", upload_id, user_string)

    try:
        workspace = database.retrieve(upload_id)
        checkpoint_list = workspace.list_checkpoints(user)
        response_data = {
            'upload_id': upload_id,
            'checkpoints': [transform.transform_checkpoint(f) for f in
                            checkpoint_list]
        }
        status_code = status.OK

    except IOError as ioe:
        logger.error("%s: List checkpoints request failed ", upload_id)
        raise InternalServerError(messages.CANT_DELETE_FILE) from ioe
    except database.WorkspaceNotFound as nf:
        logger.info("%s: Workspace not found: '%s'", upload_id, nf)
        raise NotFound(messages.UPLOAD_NOT_FOUND) from nf
    except Exception as ue:
        logger.error("%s: Unknown error while listing checkpoints. "
                    " Add except clauses for '%s'. DO IT NOW!", upload_id, ue)
        logger.error(traceback.print_exc())
        raise InternalServerError(messages.UPLOAD_UNKNOWN_ERROR) from ue

    return response_data, status_code, {}


@database.atomic
def restore_checkpoint(upload_id: int, checkpoint_checksum: str,
                       user: auth_domain.User) -> Response:
    """
    Restore checkpoint specified by checkpoint_checksum.

    Parameters
    ----------
    upload_id : int
        The unique identifier for upload workspace.
    checkpoint_checksum: str
        Unique identifier/key for checkpoint.
    user : str
        User making create checkpoint request.

    Returns
    -------
    tuple
        Standard Response tuple containing response content, HTTP status, and
        HTTP headers.
    """
    user_string = util.format_user_information_for_logging(user)
    logger.info("%s: Restore checkpoint '%s' [%s].", upload_id,
                checkpoint_checksum, user_string)

    try:
        # Make sure we have an upload_db_data to work with
        workspace = database.retrieve(upload_id)
        workspace.restore_checkpoint(checkpoint_checksum, user)
        if workspace.source_package.is_stale:
            workspace.source_package.pack()
        database.update(workspace)    # Store in DB
        response_data = {'reason': f"Restored checkpoint "
                                   f"'{checkpoint_checksum}'"}
        status_code = status.OK

    except database.WorkspaceNotFound as nf:
        logger.info("%s: Workspace not found: '%s'", upload_id, nf)
        raise NotFound(messages.UPLOAD_NOT_FOUND) from nf
    except FileNotFoundError as nf:
        logger.info("%s: Requested checkpoint '%s' not found: '%s'", upload_id,
                    checkpoint_checksum, nf)
        raise NotFound(messages.UPLOAD_CHECKPOINT_NOT_FOUND) from nf
    except IOError as ioe:
        logger.error("%s: Restore checkpoint request failed ", upload_id)
        raise InternalServerError(messages.CANT_DELETE_FILE) from ioe
    except Exception as ue:
        logger.info("%s: Unknown error while restoring checkpoint. "
                    " Add except clauses for '%s'. DO IT NOW!", upload_id, ue)
        raise InternalServerError(messages.UPLOAD_UNKNOWN_ERROR) from ue

    return response_data, status_code, {}


@database.atomic
def delete_checkpoint(upload_id: int, checkpoint_checksum: str,
                      user: auth_domain.User) -> Response:
    """
    Delete checkpoint specified by checkpoint_checksum.

    Parameters
    ----------
    upload_id : int
        The unique identifier for upload workspace.
    checkpoint_checksum: str
        Unique identifier/key for checkpoint to delete.
    user : str
        User making create checkpoint request.

    Returns
    -------
    tuple
        Standard Response tuple containing response content, HTTP status, and
        HTTP headers.

    """
    user_string = util.format_user_information_for_logging(user)
    logger.info("%s: Delete checkpoint '%s' [%s].", upload_id,
                checkpoint_checksum, user_string)

    try:
        # Make sure we have an upload_db_data to work with
        workspace = database.retrieve(upload_id)
        workspace.delete_checkpoint(checkpoint_checksum, user)
        if workspace.source_package.is_stale:
            workspace.source_package.pack()
        database.update(workspace)    # Store in DB

        response_data = {'reason': f"Deleted checkpoint "
                                   f"'{checkpoint_checksum}'"}
        status_code = status.OK

    except database.WorkspaceNotFound as nf:
        logger.info("%s: Workspace not found: '%s'", upload_id, nf)
        raise NotFound(messages.UPLOAD_NOT_FOUND) from nf
    except FileNotFoundError as nf:
        logger.info("%s: Requested checkpoint '%s' not found: '%s'", upload_id,
                    checkpoint_checksum, nf)
        raise NotFound(messages.UPLOAD_CHECKPOINT_NOT_FOUND) from nf
    except IOError as ioe:
        logger.error("%s: Deleted checkpoint request failed ", upload_id)
        raise InternalServerError(messages.CANT_DELETE_FILE) from ioe
    except Exception as ue:
        logger.error("%s: Unknown error while deleting checkpoint. "
                     " Add except clauses for '%s'. DO IT NOW!", upload_id, ue)
        logger.error(traceback.print_exc())
        raise InternalServerError(messages.UPLOAD_UNKNOWN_ERROR) from ue

    return response_data, status_code, {}


@database.atomic
def delete_all_checkpoints(upload_id: int, user: auth_domain.User) -> Response:
    """
    Delete all checkpoint files.

    Parameters
    ----------
    upload_id : int
        The unique identifier for upload workspace.
    user : str
        User making create checkpoint request.

    Returns
    -------
    tuple
        Standard Response tuple containing response content, HTTP status, and
        HTTP headers.

    """
    user_string = util.format_user_information_for_logging(user)
    logger.info("%s: Delete all checkpoints [%s].", upload_id, user_string)

    try:
        # Make sure we have an upload_db_data to work with
        workspace = database.retrieve(upload_id)
        workspace.delete_all_checkpoints(user)
        if workspace.source_package.is_stale:
            workspace.source_package.pack()
        database.update(workspace)    # Store in DB

        response_data = {'reason': f"Deleted all checkpoints."}  # Get rid of pylint error
        status_code = status.OK

    except database.WorkspaceNotFound as nf:
        logger.info("%s: Workspace not found: '%s'", upload_id, nf)
        raise NotFound(messages.UPLOAD_NOT_FOUND) from nf
    except IOError as ioe:
        logger.error("%s: Delete all checkpoints request failed: %s ",
                     upload_id, ioe)
        raise InternalServerError(messages.UPLOAD_UNKNOWN_ERROR) from ioe
    except Exception as ue:
        logger.error("%s: Unknown error while deleting all checkpoints. "
                     " Add except clauses for '%s'. DO IT NOW!", upload_id, ue)
        logger.error(traceback.print_exc())
        raise InternalServerError(messages.UPLOAD_UNKNOWN_ERROR) from ue

    return response_data, status_code, {}


def check_checkpoint_file_exists(upload_id: int, checkpoint_checksum: str) \
        -> Response:
    """
    Verify that the specified checkpoint content file exists/is available.

    Parameters
    ----------
    upload_id : int
        The unique identifier for upload workspace.
    checkpoint_checksum: str
        checksum of checkpoint ile to be checked.

    Returns
    -------
    tuple
        Standard Response tuple containing content, HTTP status, and
        HTTP headers.

    """
    try:
        workspace = database.retrieve(upload_id)
    except IOError as ioe:
        logger.error("%s: CheckpointFileExistsCheck: There was a problem "
                     "connecting to database.", upload_id)
        raise InternalServerError(messages.UPLOAD_DB_CONNECT_ERROR) from ioe
    except database.WorkspaceNotFound as nf:
        logger.info("%s: Workspace not found: '%s'", upload_id, nf)
        raise NotFound(messages.UPLOAD_NOT_FOUND) from nf

    ##logger.info("%s: Checkpoint content file exists request.", upload_id)

    try:

        checkpoint = workspace.get_checkpoint_file(checkpoint_checksum)

        headers = {'ETag': checkpoint_checksum,
                    'Content-Length': checkpoint.size_bytes,
                    'Last-Modified': checkpoint.last_modified}
        return {}, status.OK, headers

    except HTTPException as httpe:
        # Werkzeug HTTPExceptions are explicitly raised, so these should always
        # propagate.
        logger.info("%s: Operation failed: '%s'.", httpe, upload_id)
        raise httpe
    except FileNotFoundError as fne:
        raise NotFound(f"Checksum '{checkpoint_checksum}' not found.") from fne
    except IOError as ioe:
        logger.error("%s: Checkpoint file exists request failed ",
                     upload_id)
        raise InternalServerError(messages.CANT_DELETE_FILE) from ioe
    except UploadFileSecurityError as secerr:
        logger.info("%s: %s", upload_id, secerr)
        # TODO: Should this be BadRequest or NotFound. I'm leaning towards
        # NotFound in order to provide as little feedback as posible to client.
        raise NotFound("Checkpoint file not found.") from secerr
    except Exception as ue:
        logger.info("%s: Unknown error in checkpoint file exists operation. "
                    " Add except clauses for '%s'. DO IT NOW!", upload_id, ue)
        raise InternalServerError(messages.UPLOAD_UNKNOWN_ERROR) from ue

    return {}, status.OK, {'ETag': checkpoint_checksum}


def get_checkpoint_file(upload_id: int, checkpoint_checksum: str,
                        user: auth_domain.User) -> Response:
    """
    Get the checkpoint file specified by provided checksum.

    Parameters
    ----------
    upload_id : int
        The unique identifier for upload workspace.
    checkpoint_checksum: str
        checksum that uniquely identifies checkpoint.

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
    logger.info("%s: Download checkpoint: '%s' [%s].", upload_id,
                checkpoint_checksum, user_string)
    try:
        workspace = database.retrieve(upload_id)
    except IOError as ioe:
        logger.error("%s: CheckpointFileDownload: There was a problem"
                     " connecting to database.", upload_id)
        raise InternalServerError(messages.UPLOAD_DB_CONNECT_ERROR) from ioe
    except database.WorkspaceNotFound as nf:
        logger.info("%s: Workspace not found: '%s'", upload_id, nf)
        raise NotFound(messages.UPLOAD_NOT_FOUND) from nf

    try:
        checkpoint = workspace.get_checkpoint_file(checkpoint_checksum)
        pointer = workspace.get_checkpoint_file_pointer(checkpoint_checksum)

        headers = {
            "Content-disposition": f"filename={checkpoint.name}",
            'ETag': checkpoint_checksum,
            'Content-Length': checkpoint.size_bytes,
            'Last-Modified': checkpoint.last_modified
        }
    except HTTPException as httpe:
        # Werkzeug HTTPExceptions are explicitly raised, so these should always
        # propagate.
        logger.info("%s: Operation failed: '%s'.", httpe, upload_id)
        raise httpe
    except FileNotFoundError as fnf:
            raise NotFound(f"File '{checkpoint_checksum}' not found.") from fnf
    except IOError as ioe:
        logger.error("%s: Checkpoint file request failed ", upload_id)
        raise InternalServerError(messages.UPLOAD_DB_CONNECT_ERROR) from ioe
    except UploadFileSecurityError as secerr:
        logger.info("%s: %s", upload_id, secerr)
        # TODO: Should this be BadRequest or NotFound. I'm leaning towards
        # NotFound in order to provide as little feedback as posible to client.
        raise NotFound(messages.UPLOAD_FILE_NOT_FOUND) from secerr
    except Exception as ue:
        logger.info("%s: Unknown error in get checkpoint file. "
                    " Add except clauses for '%s'. DO IT NOW!", upload_id, ue)
        raise InternalServerError(messages.UPLOAD_UNKNOWN_ERROR) from ue

    return pointer, status.OK, headers
