"""Handles all upload-related requests."""

import os
import io
import logging
import time
from http import HTTPStatus as status
from typing import Tuple, Optional, Union, Any, BinaryIO
from datetime import datetime

from pytz import UTC
from flask import current_app, url_for
from werkzeug.exceptions import NotFound, InternalServerError, SecurityError, \
        Forbidden, BadRequest, HTTPException
from werkzeug.datastructures import FileStorage

from arxiv.users import domain as auth_domain
from arxiv.base.globals import get_application_config

from ..domain import Workspace, NoSuchFile, Status
from ..domain.uploads.exceptions import EmptyUploadContentError, \
    UploadFileSecurityError, InvalidUploadContentError, \
        NoSourceFilesToCheckpoint
from ..services import database, storage
from ..process import strategy, check
from .transform import transform_workspace
from .service_log import logger
from . import _messages as messages
from . import util

Response = Tuple[Optional[dict], status, dict]


def _create_workspace(file: FileStorage, user_id: str, user_string: str) \
        -> Workspace:
    try:
        logger.info("Create new workspace: Upload request: "
                    "file='%s' [%s]", file.filename, user_string)
        workspace = database.create(user_id)
        workspace.initialize()
    except IOError as e:
        logger.info("Error creating new workspace: %s", e)
        raise InternalServerError(f'{messages.UPLOAD_IO_ERROR}: {e}')
    except (TypeError, ValueError) as dbe:
        logger.info("Error adding new workspace to database: '%s'.", dbe)
        raise InternalServerError(messages.UPLOAD_DB_ERROR)
    return workspace


@database.atomic
def upload(upload_id: Union[int, None], file: Union[FileStorage, Any],
           user: auth_domain.User, ancillary: bool = False,
           checkpoint: bool = False, clear_source_files: bool = False) \
        -> Response:
    """
    Upload individual files or compressed archive into specified workspace.

    Unpack, sanitize, and add files to upload workspace.

    Parameters
    ----------
    upload_id : int
        The unique identifier for the workspace in question.
    file : :class:`FileStorage`
        File archive to be processed.
    archive : str
        Archive submission is targeting. Oversize thresholds are curently
        specified at the archive level.
    ancillary : bool
        If ``True``, the file is to be treated as an ancillary file. This means
        (presently) that the file is stored in a special subdirectory within
        the source package.
    checkpoint : bool
        Create a checkpoint (backup) of source files before unpacking and
        installing file payload for this request.

    Returns
    -------
    dict
        Complete summary of upload processing.
    int
        An HTTP status code.
    dict
        Some extra headers to add to the response.
    """
    # Log username and upload_id or new.
    id_string = ""
    user_string = 'None'
    if user:
        user_string = util.format_user_information_for_logging(user)

    id_string = str(upload_id)
    if upload_id is None:
        id_string = "New"

    # start = time.time()
    workspace: Optional[Workspace] = None

    # TODO: we need better handling for client-only requests here.
    if isinstance(user, auth_domain.User):
        user_id = str(user.user_id)
    elif isinstance(user, auth_domain.Client):
        user_id = str(user.owner_id)   # User ID of the client owner.
    # Check arguments for basic qualities like existing and such.

    # File argument is required to exist and have a name associated with it. It
    # is standard practice that if user fails to select file the filename is
    # null.
    logger.debug('Handling upload request for %s', upload_id)
    if file is None:
        # Crash and burn...not quite...do we need info about client?
        logger.error('%s: Upload request is missing file/archive payload.',
                     upload_id)
        raise BadRequest(messages.UPLOAD_MISSING_FILE)

    if file.filename == '':
        # Client needs to select file, or provide name to upload payload.
        logger.error('%s: Upload file is missing filename. File to upload may '
                     'not be selected.', id_string)
        raise BadRequest(messages.UPLOAD_MISSING_FILENAME)

    # If this is a new upload then we need to create a workspace.
    if upload_id is None:
        # Split this out for clarity. --Erick 2019-06-10
        workspace = _create_workspace(file, user_id, user_string)
        upload_id = workspace.upload_id

    # print('upload workspace exists at', time.time() - start)
    # At this point we expect upload to exist in system
    try:
        if workspace is None:
            workspace = database.retrieve(upload_id)

        if workspace is None:   # Invalid workspace identifier
            raise NotFound(messages.UPLOAD_NOT_FOUND)

        if checkpoint:
            workspace.create_checkpoint(user)

        # Admin may want to clear out existing files so that existing files
        # do not cause problems or interfere with processing uploaded files.
        #
        # Steps are 1) checkpoint 2) clear source files 3) unpack upload
        #
        if clear_source_files:
            workspace.delete_all_files()

        workspace.set_strategy(strategy.create_strategy(current_app))
        workspace.checkers = check.get_default_checkers()

        if workspace.status != Status.ACTIVE:
            # Do we log anything for these requests
            logger.debug('Forbidden, workspace not active')
            raise Forbidden(messages.UPLOAD_NOT_ACTIVE)

        if workspace.is_locked:
            logger.debug('Forbidden, workspace locked')
            raise Forbidden(messages.UPLOAD_WORKSPACE_LOCKED)

        # Now handle upload package - process file or gzipped tar archive

        # NOTE: This will need to be migrated to task.py using Celery at
        #       some point in future. Depends in time it takes to process
        #       database.retrieve
        logger.info("%s: Upload files to existing workspace: file='%s'",
                    workspace.upload_id, file.filename)
        # print('upload workspace retrieved at', time.time() - start)

        # Keep track of how long processing workspace takes.
        start_datetime = datetime.now(UTC)

        # Add the uploaded file to the workspace.
        if not isinstance(file.filename, str):
            raise BadRequest('Could not determine filename')

        u_file = workspace.create(file.filename, is_ancillary=ancillary)
        with workspace.open(u_file, 'wb') as f:
            file.save(f)

        if u_file.size_bytes == 0:      # Empty uploads are disallowed.
            raise BadRequest(messages.UPLOAD_FILE_EMPTY)

        workspace.perform_checks()      # Runs sanitization, fixes, etc.
        # print('workspace finished processing upload at', time.time() - start)
        workspace.persist_all()
        # print('workspace persisted at', time.time() - start)

        completion_datetime = datetime.now(UTC)

        # Disabling these for now, as it doesn't look like we're using them.
        # --Erick 2019-06-20
        #
        # workspace.last_upload_logs = json.dumps(response_data['errors'])
        # workspace.last_upload_file_summary = json.dumps(response_data['files'])
        workspace.last_upload_start_datetime = start_datetime
        workspace.last_upload_completion_datetime = completion_datetime
        workspace.last_upload_readiness = workspace.readiness
        workspace.status = Status.ACTIVE
        if workspace.source_package.is_stale:
            workspace.source_package.pack()
        # print('source packed at', time.time() - start)
        database.update(workspace)    # Store in DB
        # print('db updated at', time.time() - start)

        logger.info("%s: Processed upload. Saved to DB. Preparing upload "
                    "summary.", workspace.upload_id)
        response_data = transform_workspace(workspace)
        # print('workspace serialized at', time.time() - start)

        # Do we want affirmative log messages after processing each request
        # or maybe just report errors like:
        #  logger.info(f"{workspace.upload_id}: Finished processing ...")

        headers = {'Location': url_for('upload_api.upload_files',
                                       upload_id=workspace.upload_id)}

        logger.info("%s: Generating upload summary.", workspace.upload_id)
        headers.update({
            'ARXIV-OWNER': workspace.owner_user_id,
            'ETag': workspace.source_package.checksum,
            'Last-Modified': workspace.source_package.last_modified
        })
        logger.debug('Response checksum: %s', response_data['checksum'])
        logger.debug('Responding with headers %s', headers)
        # print('done at', time.time() - start)

        # TODO: this should only be 201 Created if it's a new workspace;
        # otherwise just 200 OK. -- Erick
        return response_data, status.CREATED, headers

    except HTTPException as httpe:
        # Werkzeug HTTPExceptions are explicitly raised, so these should always
        # propagate.
        logger.info("%s: Upload failed: '%s'.", httpe, upload_id)
        raise httpe
    except InvalidUploadContentError as breq:
        logger.info("%s: '%s'.", upload_id, breq)
        raise BadRequest(messages.UPLOAD_MISSING_FILE) from breq
    except EmptyUploadContentError as ereq:
        logger.info("%s: '%s'.", upload_id, ereq)
        raise BadRequest(messages.UPLOAD_FILE_EMPTY) from ereq
    except NoSourceFilesToCheckpoint as nsf:
        logger.info("%s: No source files to checkpoint: %s", upload_id, nsf)
        raise BadRequest(messages.UPLOAD_WORKSPACE_IS_EMPTY) from nsf
    except database.WorkspaceNotFound as nf:
        logger.info("%s: Workspace not found: '%s'", upload_id, nf)
        raise NotFound(messages.UPLOAD_NOT_FOUND) from nf
    except (TypeError, ValueError) as dbe:
        logger.info("%s: Error updating database: '%s'", upload_id, dbe)
        raise InternalServerError(messages.UPLOAD_DB_ERROR) from dbe


@database.atomic
def upload_summary(upload_id: int) -> Response:
    """
    Provide summary of important upload workspace details.

    Parameters
    ----------
    upload_id : int
        The unique identifier for upload workspace.

    Returns
    -------
    dict
        Detailed information about the upload workspace.

        logs - Errors and Warnings
        files - list of file details

    int
        An HTTP status code.
    dict
        Some extra headers to add to the response.

    """
    try:
        workspace: Workspace = database.retrieve(upload_id)
        logger.info("%s: Upload summary request.", workspace.upload_id)

        status_code = status.OK
        response_data = transform_workspace(workspace)
        logger.info("%s: Upload summary request.", workspace.upload_id)

    except database.WorkspaceNotFound as nf:
        logger.info("%s: UploadSummary: '%s'", upload_id, nf)
        raise NotFound(messages.UPLOAD_NOT_FOUND)
    except (TypeError, ValueError) as e:
        logger.info("Error updating database.")
        raise InternalServerError(messages.UPLOAD_DB_ERROR)

    headers = {'ARXIV-OWNER': workspace.owner_user_id,
               'ETag': workspace.source_package.checksum,
               'Last-Modified': workspace.source_package.last_modified}
    return response_data, status_code, headers


@database.atomic
def delete_workspace(upload_id: int, user: auth_domain.User) -> Response:
    """
    Delete workspace.

    Parameters
    ----------
    upload_id : int
        The unique identifier for the upload workspace.

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
    logger.info('%s: Deleting upload workspace [%s].', upload_id, user_string)

    # Need to add several checks here

    # At this point I believe we know that caller is authorized to delete the
    # workspace. This is checked at the routes level.

    # Does workspace exist? Has it already been deleted? Generate 400:NotFound
    # error.
    # Do we care is workspace is ACTIVE state? And not released? NO. But log
    # it...
    # Do we want to stash source.log somewhere?
    # Do we care if workspace was modified recently...NO. Log it

    try:
        # Make sure we have an existing upload workspace to work with
        workspace: Workspace = database.retrieve(upload_id)

        if workspace is None:
            # invalid workspace identifier
            # Note: DB entry will exist for workspace that has already been
            #       deleted
            raise NotFound(messages.UPLOAD_NOT_FOUND)

        # Actually remove entire workspace directory structure. Log everything
        # to global log since source log is being removed!

        # Initiate workspace deletion

        # Update database (but keep around) for historical reference. Does not
        # consume very much space. What about source log?

        if workspace.is_deleted:
            logger.info("%s: Workspace has already been deleted:"
                        "current state is '%s'", upload_id, workspace.status)
            raise NotFound(messages.UPLOAD_WORKSPACE_NOT_FOUND)

        # Call routine that will do the actual work
        workspace.delete_workspace()

        # update database
        if not workspace.is_released:
            logger.info("%s: Workspace currently in '%s' state.",
                        upload_id, workspace.status)

        workspace.status = Status.DELETED
        database.update(workspace)

    except IOError:
        logger.error("%s: Delete workspace request failed ", upload_id)
        # raise InternalServerError(messages.CANT_DELETE_FILE)
        raise
    except (NotFound, database.WorkspaceNotFound) as nf:
        logger.info("%s: Delete Workspace: '%s'", upload_id, nf)
        raise

    # API doesn't provide for returning errors resulting from delete.
    # 401-unautorized and 403-forbidden are handled at routes level.
    # Add 400 response to openapi.yaml
    return {'reason': messages.UPLOAD_DELETED_WORKSPACE}, status.OK, {}
