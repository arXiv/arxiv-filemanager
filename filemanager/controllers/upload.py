"""Handles all upload-related requests."""

import time
import io
import json
import logging
import os.path
from typing import Tuple, Optional, Union
from datetime import datetime
from hashlib import md5
from base64 import urlsafe_b64encode
from http import HTTPStatus as status

from pytz import UTC

from flask import current_app
from flask.json import jsonify
from werkzeug.exceptions import NotFound, BadRequest, InternalServerError, \
    NotImplemented, SecurityError, Forbidden
from werkzeug.datastructures import FileStorage

from arxiv.users import domain as auth_domain
from arxiv.base.globals import get_application_config

from ..shared import url_for
from ..domain import UploadWorkspace, NoSuchFile
from ..services import database, storage
from ..process import strategy, check
from ..serialize import serialize_workspace

# Temporary logging at service level - just to get something in place to build on

logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger(__name__)


def _get_service_logs_directory() -> str:
    """
    Return path to service logs directory.

    Returns
    -------
    Directory where service logs are to be stored.

    """
    config = get_application_config()
    return config.get('UPLOAD_SERVICE_LOG_DIRECTORY', '')


service_log_path = os.path.join(_get_service_logs_directory(), 'upload.log')

file_handler = logging.FileHandler(service_log_path, 'a')

# Default arXiv log format.
# fmt = ("application %(asctime)s - %(name)s - %(requestid)s"
#          " - [arxiv:%(paperid)s] - %(levelname)s: \"%(message)s\"")
datefmt = '%d/%b/%Y:%H:%M:%S %z'  # Used to format asctime.
formatter = logging.Formatter('%(asctime)s %(message)s', '%d/%b/%Y:%H:%M:%S %z')
file_handler.setFormatter(formatter)
# logger.handlers = []
logger.addHandler(file_handler)
logger.setLevel(logging.DEBUG)
logger.propagate = True

# End logging configuration

# exceptions
UPLOAD_MISSING_FILE = 'missing file/archive payload'
UPLOAD_MISSING_FILENAME = 'file argument missing filename or file not selected'
UPLOAD_FILE_EMPTY = 'file payload is zero length'

UPLOAD_NOT_FOUND = 'upload workspace not found'
UPLOAD_DB_ERROR = 'unable to create/insert new upload workspace into database'
UPLOAD_DB_CONNECT_ERROR = "There was a problem connecting to database."
UPLOAD_IO_ERROR = 'encountered an IOError'
UPLOAD_UNKNOWN_ERROR = 'unknown error'
UPLOAD_DELETED_FILE = 'deleted file'
UPLOAD_DELETED_WORKSPACE = 'deleted workspace'
UPLOAD_FILE_NOT_FOUND = 'file not found'
UPLOAD_DELETED_ALL_FILES = 'deleted all files'
UPLOAD_WORKSPACE_NOT_FOUND = 'workspace not found'
UPLOAD_LOCKED_WORKSPACE = 'locked workspace'
UPLOAD_UNLOCKED_WORKSPACE = 'unlocked workspace'
UPLOAD_RELEASED_WORKSPACE = 'released workspace'
UPLOAD_UNRELEASED_WORKSPACE = 'unreleased workspace'

UPLOAD_NOT_ACTIVE = 'upload workspace is not active.'
UPLOAD_WORKSPACE_LOCKED = 'upload workspace is locked.'

UPLOAD_WORKSPACE_ALREADY_DELETED = 'Request failed. Workspace has been deleted.'

# upload status codes
# INVALID_UPLOAD_ID = {'reason': 'invalid upload identifier'}
# MISSING_UPLOAD_ID = {'reason': 'missing upload id'}

# Indicate requests that have not been implemented yet.
REQUEST_NOT_IMPLEMENTED = {'request not implemented'}

# upload status
NO_SUCH_THING = {'reason': 'there is no upload'}
THING_WONT_COME = {'reason': 'could not get the upload'}

ERROR_RETRIEVING_UPLOAD = 'upload not found'
# UPLOAD_DOESNT_EXIST = {'upload does not exist'}
CANT_CREATE_UPLOAD = 'could not create the upload'  #
CANT_UPLOAD_FILE = 'could not upload file'
CANT_DELETE_FILE = 'could not delete file'
CANT_DELETE_ALL_FILES = 'could not delete all files'
CANT_RELEASE_WORKSPACE = 'could not release workspace'
CANT_UNRELEASE_WORKSPACE = 'could not unrelease workspace'

ACCEPTED = {'reason': 'upload in progress'}

MISSING_NAME = {'an upload needs a name'}

SOME_ERROR = {'Need to define and assign better error'}

Response = Tuple[Optional[dict], int, dict]


@database.atomic
def delete_workspace(upload_id: int) -> Response:
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
    logger.info('%s: Deleting upload workspace.', upload_id)

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
        workspace: Optional[UploadWorkspace] = database.retrieve(upload_id)

        if workspace is None:
            # invalid workspace identifier
            # Note: DB entry will exist for workspace that has already been
            #       deleted
            raise NotFound(UPLOAD_NOT_FOUND)

        # Actually remove entire workspace directory structure. Log everything
        # to global log since source log is being removed!

        # Initiate workspace deletion

        # Update database (but keep around) for historical reference. Does not
        # consume very much space. What about source log?

        if workspace.is_deleted:
            logger.info("%s: Workspace has already been deleted:"
                        "current state is '%s'", upload_id, workspace.status)
            raise NotFound(UPLOAD_WORKSPACE_NOT_FOUND)

        # Call routine that will do the actual work
        workspace.delete_workspace()

        # update database
        if not workspace.is_released:
            logger.info("%s: Workspace currently in '%s' state.",
                        upload_id, workspace.status)

        workspace.status = UploadWorkspace.Status.DELETED

        # Store in DB
        database.update(workspace)

    except IOError:
        logger.error("%s: Delete workspace request failed ", upload_id)
        raise InternalServerError(CANT_DELETE_FILE)
    except NotFound as nf:
        logger.info("%s: Delete Workspace: '%s'", upload_id, nf)
        raise
    except Exception as ue:
        raise
        # logger.info("Unknown error in delete workspace. "
        #             " Add except clauses for '%s'. DO IT NOW!", ue)
        # raise InternalServerError(UPLOAD_UNKNOWN_ERROR)

    # API doesn't provide for returning errors resulting from delete.
    # 401-unautorized and 403-forbidden are handled at routes level.
    # Add 400 response to openapi.yaml
    return {'reason': UPLOAD_DELETED_WORKSPACE}, status.OK, {}


@database.atomic
def client_delete_file(upload_id: int, public_file_path: str) -> Response:
    """
    Delete a single file.

    This request is being received from API so we need to be extra careful.

    Parameters
    ----------
    upload_id : int
        The unique identifier for the upload_db_data in question.
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
            raise NotFound(UPLOAD_NOT_FOUND)
        if not workspace.is_active:    # Do we log anything for these requests?
            raise Forbidden(UPLOAD_NOT_ACTIVE)
        if workspace.is_locked:
            raise Forbidden(UPLOAD_WORKSPACE_LOCKED)

        # Call routine that will do the actual work.
        try:
            workspace.delete(workspace.get(public_file_path))
        except NoSuchFile:
            raise NotFound(UPLOAD_FILE_NOT_FOUND)

        workspace.strategy = strategy.create_strategy(current_app)
        workspace.checkers = check.get_default_checkers()
        workspace.perform_checks()
        database.update(workspace)

    except IOError:
        logger.error("%s: Delete file request failed ", upload_id)
        raise InternalServerError(CANT_DELETE_FILE)
    except NotFound as nf:
        logger.info("%s: DeleteFile: %s", upload_id, nf)
        raise nf
    except SecurityError as secerr:
        logger.info("%s: %s", upload_id, secerr.description)
        # TODO: Should this be BadRequest or NotFound. I'm leaning towards
        # NotFound in order to provide as little feedback as posible to client.
        raise NotFound(UPLOAD_FILE_NOT_FOUND)
    except Forbidden as forb:
        logger.info("%s: Delete file forbidden: %s.", upload_id, forb)
        raise forb
    except Exception as ue:
        raise ue
        # logger.info("Unknown error in delete file. "
        #             " Add except clauses for '%s'. DO IT NOW!", ue)
        # raise InternalServerError(UPLOAD_UNKNOWN_ERROR)

    response_data = serialize_workspace(workspace)
    response_data.update({'reason': UPLOAD_DELETED_FILE})
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
        The unique identifier for the upload_db_data in question.
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
        # Make sure we have an upload_db_data to work with
        workspace: Optional[UploadWorkspace] = database.retrieve(upload_id)

        if workspace is None:
            raise NotFound(UPLOAD_NOT_FOUND)    # Invalid workspace identifier.
        if not workspace.is_active: # Do we log anything for these requests.            
            raise Forbidden(UPLOAD_NOT_ACTIVE)
        if workspace.is_locked:
            raise Forbidden(UPLOAD_WORKSPACE_LOCKED)

        workspace.delete_all_files()
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
        raise InternalServerError(UPLOAD_UNKNOWN_ERROR)
    
    response_data = serialize_workspace(workspace)
    response_data.update({'reason': UPLOAD_DELETED_ALL_FILES})
    headers = {'ARXIV-OWNER': workspace.owner_user_id}
    return response_data, status.OK, headers


def _create_workspace(file: FileStorage, user_id: str) -> UploadWorkspace:
    try:
        logger.info("Create new workspace: Upload request: file='%s'",
                    file.filename)
        current_time = datetime.now(UTC)
        workspace = database.create(user_id)
    except IOError as e:
        logger.info("Error creating new workspace: %s", e)
        raise InternalServerError(f'{UPLOAD_IO_ERROR}: {e}')
    except (TypeError, ValueError) as dbe:
        logger.info("Error adding new workspace to database: '%s'.", dbe)
        raise InternalServerError(UPLOAD_DB_ERROR)
    except Exception as ue:
        logger.info("Unknown error in upload for new workspace. "
                    " Add except clauses for '%s'. DO IT NOW!", ue)
        raise InternalServerError(UPLOAD_UNKNOWN_ERROR)
    return workspace


@database.atomic
def upload(upload_id: Optional[int], file: Optional[FileStorage], archive: str,
           user: Union[auth_domain.User, auth_domain.Client],
           ancillary: bool = False) -> Response:
    """
    Upload individual files or compressed archive into specified workspace.

    Unpack, sanitize, and add files to upload workspace.

    Parameters
    ----------
    upload_id : int
        The unique identifier for the upload_db_data in question.
    file : :class:`FileStorage`
        File archive to be processed.
    archive : str
        Archive submission is targeting. Oversize thresholds are curently
        specified at the archive level.
    ancillary : bool
        If ``True``, the file is to be treated as an ancillary file. This means
        (presently) that the file is stored in a special subdirectory within
        the source package.

    Returns
    -------
    dict
        Complete summary of upload processing.
    int
        An HTTP status code.
    dict
        Some extra headers to add to the response.
    """
    start = time.time()
    workspace: Optional[UploadWorkspace] = None

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
        logger.error('Upload request is missing file/archive payload.')
        raise BadRequest(UPLOAD_MISSING_FILE)

    if file.filename == '':
        # Client needs to select file, or provide name to upload payload.
        logger.error('Upload file is missing filename. File to upload may not'
                     ' be selected.')
        raise BadRequest(UPLOAD_MISSING_FILENAME)

    # If this is a new upload then we need to create a workspace.
    if upload_id is None:
        logger.debug('This is a new upload workspace.')
        # Split this out for clarity. --Erick 2019-06-10
        workspace = _create_workspace(file, user_id)
        upload_id = workspace.upload_id

    print('upload workspace exists at', time.time() - start)
    # At this point we expect upload to exist in system
    try:
        if workspace is None:
            workspace = database.retrieve(upload_id)

        if workspace is None:   # Invalid workspace identifier
            raise NotFound(UPLOAD_NOT_FOUND)

        workspace.strategy = strategy.create_strategy(current_app)
        workspace.checkers = check.get_default_checkers()

        if workspace.status != UploadWorkspace.Status.ACTIVE:
            # Do we log anything for these requests
            logger.debug('Forbidden, workspace not active')
            raise Forbidden(UPLOAD_NOT_ACTIVE)

        if workspace.is_locked:
            logger.debug('Forbidden, workspace locked')
            raise Forbidden(UPLOAD_WORKSPACE_LOCKED)

        # Now handle upload package - process file or gzipped tar archive

        # NOTE: This will need to be migrated to task.py using Celery at
        #       some point in future. Depends in time it takes to process
        #       database.retrieve
        logger.info("%s: Upload files to existing workspace: file='%s'",
                    workspace.upload_id, file.filename)
        print('upload workspace retrieved at', time.time() - start)

        # Keep track of how long processing workspace takes.
        start_datetime = datetime.now(UTC)

        # Add the uploaded file to the workspace.
        u_file = workspace.create(file.filename, is_ancillary=ancillary)
        with workspace.open(u_file, 'wb') as f:
            file.save(f)

        if u_file.size_bytes == 0:      # Empty uploads are disallowed.
            raise BadRequest(UPLOAD_FILE_EMPTY)

        workspace.perform_checks()      # Runs sanitization, fixes, etc.
        print('workspace finished processing upload at', time.time() - start)

        completion_datetime = datetime.now(UTC)

        # Disabling these for now, as it doesn't look like we're using them.
        # --Erick 2019-06-20
        #
        # workspace.lastupload_logs = json.dumps(response_data['errors'])
        # workspace.lastupload_file_summary = json.dumps(response_data['files'])
        workspace.lastupload_start_datetime = start_datetime
        workspace.lastupload_completion_datetime = completion_datetime
        workspace.lastupload_readiness = workspace.readiness
        workspace.status = UploadWorkspace.Status.ACTIVE

        database.update(workspace)    # Store in DB
        print('db updated at', time.time() - start)

        logger.info("%s: Processed upload. Saved to DB. Preparing upload "
                    "summary.", workspace.upload_id)
        response_data = serialize_workspace(workspace)
        # Do we want affirmative log messages after processing each request
        # or maybe just report errors like:
        #  logger.info(f"{upload_db_data.upload_id}: Finished processing ...")

        headers = {'Location': url_for('upload_api.upload_files',
                                       upload_id=workspace.upload_id)}

        logger.info("%s: Generating upload summary.", workspace.upload_id)
        headers.update({'ARXIV-OWNER': workspace.owner_user_id})
        print('done at', time.time() - start)

        # TODO: this should only be 201 Created if it's a new workspace; 
        # otherwise just 200 OK. -- Erick
        return response_data, status.CREATED, headers

    except IOError as e:
        logger.error("%s: File upload_db_data request failed "
                     "for file='%s'", upload_id, file.filename)
        raise InternalServerError(f'{UPLOAD_IO_ERROR}: {e}') from e
    except (TypeError, ValueError) as dbe:
        logger.info("Error updating database: '%s'", dbe)
        raise InternalServerError(UPLOAD_DB_ERROR)
    except BadRequest as breq:
        logger.info("%s: '%s'.", upload_id, breq)
        raise
    except NotFound as nfdb:
        logger.info("%s: Upload: '{nfdb}'.", upload_id)
        raise nfdb
    except Forbidden as forb:
        logger.info("%s: Upload failed: '{forb}'.", upload_id)
        raise forb
    except Exception as ue:
        raise
        # logger.info("Unknown error with existing workspace."
        #             " Add except clauses for '%s'. DO IT NOW!", ue)
        # raise InternalServerError(UPLOAD_UNKNOWN_ERROR)

    return None


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
        Detailed information about the upload_db_data.

        logs - Errors and Warnings
        files - list of file details

    int
        An HTTP status code.
    dict
        Some extra headers to add to the response.

    """
    try:
        # Make sure we have an upload_db_data to work with
        workspace: Optional[UploadWorkspace] = database.retrieve(upload_id)
        if workspace is None:
            raise NotFound(UPLOAD_NOT_FOUND)

        logger.info("%s: Upload summary request.", workspace.upload_id)

        # Create Upload object
        # upload_workspace = UploadWorkspace(upload_id)
        # file_list = upload_workspace.create_file_list()

        # details_list = []
        # for fileObj in file_list:
        #     file_details = {
        #         'name': fileObj.name,
        #         'public_filepath': fileObj.public_filepath,
        #         'size': fileObj.size,
        #         'type': fileObj.type_string,
        #         'modified_datetime': fileObj.modified_datetime
        #     }
        #     if not fileObj.removed:
        #         details_list.append(file_details)

        status_code = status.OK
        # response_data = _status_data(upload_db_data, upload_workspace)
        # response_data.update({'files': details_list, 'errors': []})
        response_data = serialize_workspace(workspace)
        logger.info("%s: Upload summary request.", workspace.upload_id)

    except IOError:
        # response_data = ERROR_RETRIEVING_UPLOAD
        # status_code = status.INTERNAL_SERVER_ERROR
        raise InternalServerError(ERROR_RETRIEVING_UPLOAD)
    except (TypeError, ValueError) as e:
        logger.info("Error updating database.")
        raise InternalServerError(UPLOAD_DB_ERROR)
    except NotFound as nf:
        logger.info("%s: UploadSummary: '%s'", upload_id, nf)
        raise
    except Exception as ue:
        logger.info("Unknown error with existing workspace."
                    " Add except clauses for '%s'. DO IT NOW!", ue)
        raise InternalServerError(UPLOAD_UNKNOWN_ERROR)

    headers = {'ARXIV-OWNER': workspace.owner_user_id}
    return response_data, status_code, headers


# TODO: How do we keep submitter from updating workspace while admin
# TODO: is working on it? These locks currently mean no changes are allowed.
# TODO: Is there another flavor of lock? Administrative lock? Or do admin
# TODO: and submitter coordinate on changes to upload workspace.
@database.atomic
def upload_lock(upload_id: int) -> Response:
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
    Standard Response tuple containing response content, HTTP status, and HTTP headers.

    """
    logger.info("%s: Lock upload workspace.", upload_id)

    try:
        # Make sure we have an upload_db_data to work with
        workspace: Optional[UploadWorkspace] = database.retrieve(upload_id)

        if workspace is None:
            # Invalid workspace identifier
            raise NotFound(UPLOAD_NOT_FOUND)

        # Lock upload workspace
        # update database
        if workspace.is_locked:
            logger.info("%s: Lock: Workspace is already locked.", upload_id)
        else:
            workspace.lock_state = UploadWorkspace.LockState.LOCKED

            # Store in DB
            database.update(workspace)

        response_data = {'reason': UPLOAD_LOCKED_WORKSPACE}
        status_code = status.OK

    except IOError:
        logger.error("%s: Lock workspace request failed ", upload_id)
        raise InternalServerError(CANT_DELETE_FILE)
    except NotFound as nf:
        logger.info("%s: Lock: %s", upload_id, nf)
        raise
    except Exception as ue:
        logger.info("Unknown error lock workspace. "
                    " Add except clauses for '%s'. DO IT NOW!", ue)
        raise InternalServerError(UPLOAD_UNKNOWN_ERROR)

    headers = {'ARXIV-OWNER': workspace.owner_user_id}
    return response_data, status_code, headers


@database.atomic
def upload_unlock(upload_id: int) -> Response:
    """
    Unlock upload workspace.

    Parameters
    ----------
    upload_id : int
        The unique identifier for upload workspace.

    Returns
    -------
    Standard Response tuple containing response content, HTTP status, and HTTP headers.

    """
    # response_data = ERROR_REQUEST_NOT_IMPLEMENTED
    # status_code = status.INTERNAL_SERVER_ERROR
    logger.info("%s: Unlock upload workspace.", upload_id)

    try:
        # Make sure we have an upload_db_data to work with
        workspace: Optional[UploadWorkspace] = database.retrieve(upload_id)

        if workspace is None:
            raise NotFound(UPLOAD_NOT_FOUND)

        # Lock upload workspace
        if not workspace.is_locked:
            logger.info("%s: Unlock: Workspace is already unlocked.", 
                        upload_id)
        else:
            workspace.lock_state = UploadWorkspace.LockState.UNLOCKED
            database.update(workspace)

        response_data = {'reason': UPLOAD_UNLOCKED_WORKSPACE}  # Get rid of pylint error
        status_code = status.OK

    except IOError:
        logger.error("%s: Unlock workspace request failed ", upload_id)
        raise InternalServerError(CANT_DELETE_FILE)
    except NotFound as nf:
        logger.info("%s: Unlock workspace: %s", upload_id, nf)
        raise
    except Exception as ue:
        logger.info("Unknown error in unlock workspace. "
                    " Add except clauses for '%s'. DO IT NOW!", ue)
        raise InternalServerError(UPLOAD_UNKNOWN_ERROR)

    headers = {'ARXIV-OWNER': workspace.owner_user_id}
    return response_data, status_code, headers


@database.atomic
def upload_release(upload_id: int) -> Response:
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
        Detailed information about the upload_db_data.
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

    try:
        workspace: Optional[UploadWorkspace] = database.retrieve(upload_id)

        if workspace is None:
            # Invalid workspace identifier
            raise NotFound(UPLOAD_NOT_FOUND)

        if workspace.is_released:
            logger.info("%s: Release: Workspace has already been released.", 
                        upload_id)
            response_data = {'reason': UPLOAD_RELEASED_WORKSPACE}  
            
            status_code = status.OK # Should this be an error?
        elif workspace.is_deleted:
            logger.info("%s: Release failed: Workspace has been deleted.", 
                        upload_id)
            raise NotFound(UPLOAD_WORKSPACE_ALREADY_DELETED)
        elif workspace.is_active:
            logger.info("%s: Release upload workspace.", upload_id)
            workspace.status = UploadWorkspace.Status.RELEASED
            database.update(workspace)

            response_data = {'reason': UPLOAD_RELEASED_WORKSPACE} 
            status_code = status.OK

    except IOError:
        logger.error("%s: Release workspace request failed.", upload_id)
        raise InternalServerError(CANT_RELEASE_WORKSPACE)
    except NotFound as nf:
        logger.info("%s: Release workspace: %s", upload_id, nf)
        raise
    except Exception as ue:
        logger.info("Unknown error in release workspace. "
                    " Add except clauses for '%s'. DO IT NOW!", ue)
        raise InternalServerError(UPLOAD_UNKNOWN_ERROR)

    headers = {'ARXIV-OWNER': workspace.owner_user_id}
    return response_data, status_code, headers


@database.atomic
def upload_unrelease(upload_id: int) -> Response:
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
        Detailed information about the upload_db_data.
        logs - Errors and Warnings
        files - list of file details
    int
        An HTTP status code.
    dict
        Some extra headers to add to the response.

    """
    # Again, as with delete workspace, authentication, authorization, and
    # existence of workspace is verified in route level

    # Expect workspace to be in RELEASED state.
    logger.info("%s: Unrelease upload workspace.", upload_id)

    try:
        # Make sure we have an upload_db_data to work with
        workspace: Optional[UploadWorkspace] = database.retrieve(upload_id)

        if workspace is None:
            raise NotFound(UPLOAD_NOT_FOUND)

        # Unrelease upload workspace
        # update database
        if workspace.is_deleted:
            raise NotFound(UPLOAD_WORKSPACE_ALREADY_DELETED)

        if workspace.is_active:
            logger.info("%s: Unrelease: Workspace is already active.", upload_id)
            response_data = {'reason': UPLOAD_UNRELEASED_WORKSPACE}  
            status_code = status.OK     # Should this be an error?
        elif workspace.is_released:
            logger.info("%s: Unrelease upload workspace.", upload_id)

            workspace.status = UploadWorkspace.Status.ACTIVE
            database.update(workspace)

            response_data = {'reason': UPLOAD_UNRELEASED_WORKSPACE}
            status_code = status.OK

    except IOError:
        logger.error("%s: Unrelease workspace request failed.", upload_id)
        raise InternalServerError(CANT_DELETE_FILE)
    except NotFound as nf:
        logger.info("%s: Unrelease workspace: '%s'", upload_id, nf)
        raise
    except Exception as ue:
        logger.info("Unknown error in unrelease workspace. "
                    " Add except clauses for '%s'. DO IT NOW!", ue)
        raise InternalServerError(UPLOAD_UNKNOWN_ERROR)

    headers = {'ARXIV-OWNER': workspace.owner_user_id}
    return response_data, status_code, headers


# Content download controllers

def check_upload_content_exists(upload_id: int) -> Response:
    """
    Verify that the package content exists/is available.

    Parameters
    ----------
    upload_id : int
        The unique identifier for upload workspace.

    Returns
    -------
    Standard Response tuple containing response content, HTTP status, and HTTP headers.

    """
    try:
        workspace: Optional[UploadWorkspace] = database.retrieve(upload_id)
    except IOError:
        logger.error("%s: ContentExistsCheck: There was a problem connecting "
                     "to database.", upload_id)
        raise InternalServerError(UPLOAD_DB_CONNECT_ERROR)

    if upload_db_data is None:
        raise NotFound(UPLOAD_NOT_FOUND)

    logger.info("%s: Upload content summary request.", upload_id)
    upload_workspace = UploadWorkspace(upload_id)

    # This will potentially build content package if it does not exist
    checksum = upload_workspace.content_checksum()
    modified = ''
    size = 0

    # Double check package exists
    if upload_workspace.content_package_exists:
        modified = upload_workspace.content_package_modified
        size = upload_workspace.content_package_size
        return {}, status.OK, {'ETag': checksum,
                                        'Content-Length': size,
                                        'Last-Modified': modified}
    headers = {'ARXIV-OWNER': upload_db_data.owner_user_id, 'ETag': checksum}
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
    Standard Response tuple containing compressed content, HTTP status, and HTTP headers.

    """
    try:
        workspace: Optional[UploadWorkspace] = database.retrieve(upload_id)
    except IOError:
        logger.error("%s: ContentDownload: There was a problem connecting "
                     "to database.", upload_id)
        raise InternalServerError(UPLOAD_DB_CONNECT_ERROR)

    if upload_db_data is None:
        raise NotFound(UPLOAD_NOT_FOUND)
    upload_workspace = UploadWorkspace(upload_id)
    checksum = upload_workspace.content_checksum()
    try:
        filepointer = upload_workspace.get_content()
    except FileNotFoundError as e:
        raise NotFound("No content in workspace") from e
    headers = {
        "Content-disposition": f"filename={filepointer.name}",
        'ETag': checksum,
        'ARXIV-OWNER': upload_db_data.owner_user_id
    }
    return filepointer, status.OK, headers


def check_upload_file_content_exists(upload_id: int, public_file_path: str) -> Response:
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
    Standard Response tuple containing content, HTTP status, and HTTP headers.

    """
    try:
        workspace: Optional[UploadWorkspace] = database.retrieve(upload_id)
    except IOError:
        logger.error("%s: ContentFileExistsCheck: There was a problem "
                     "connecting to database.", upload_id)
        raise InternalServerError(UPLOAD_DB_CONNECT_ERROR)

    if workspace is None:
        raise NotFound(UPLOAD_NOT_FOUND)

    logger.info("%s: Upload content file exists request.", upload_id)

    try:


        # file exists
        if workspace.exists(public_file_path):
            u_file = workspace.get(public_file_path)
            return {}, status.OK, {'ETag': u_file.checksum,
                                   'Content-Length': u_file.size_bytes,
                                   'Last-Modified': u_file.last_modified}

        raise NotFound(f"File '{public_file_path}' not found.")

    except IOError:
        logger.error("%s: Content file exists request failed ", upload_db_data.upload_id)
        raise InternalServerError(CANT_DELETE_FILE)
    except NotFound as nf:
        logger.info("%s: File not found: %s", upload_id, nf)
        raise nf
    except SecurityError as secerr:
        logger.info("%s: %s", upload_id, secerr.description)
        # TODO: Should this be BadRequest or NotFound. I'm leaning towards
        # NotFound in order to provide as little feedback as posible to client.
        raise NotFound(UPLOAD_FILE_NOT_FOUND)
    except Forbidden as forb:
        logger.info("%s: Operation forbidden: %s.", upload_id, forb)
        raise forb
    except Exception as ue:
        logger.info("Unknown error in content file exists operation. "
                    " Add except clauses for '%s'. DO IT NOW!", ue)
        raise InternalServerError(UPLOAD_UNKNOWN_ERROR)

    headers = {'ARXIV-OWNER': upload_db_data.owner_user_id, 'ETag': checksum}
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
                     " to database.", upload_db_data.upload_id)
        raise InternalServerError(UPLOAD_DB_CONNECT_ERROR)

    if workspace is None:
        raise NotFound(UPLOAD_NOT_FOUND)

    try:
        if workspace.exists(public_file_path):
            u_file = workspace.get(public_file_path)
            headers = {'ETag': u_file.checksum,
                       'Content-Length': u_file.size_bytes,
                       'Last-Modified': u_file.last_modified,
                       'Content-disposition': f'filename={u_file.name}'}
        else:
            raise NotFound(f"File '{public_file_path}' not found.")
        
        filepointer = workspace.open_pointer(u_file)

    except IOError:
        logger.error("%s: Get file content request failed ", 
                     workspace.upload_id)
        raise InternalServerError(CANT_DELETE_FILE)
    except NotFound as nf:
        logger.info("%s: Get file content: %s", upload_id, nf)
        raise nf
    except SecurityError as secerr:
        logger.info("%s: %s", upload_id, secerr.description)
        # TODO: Should this be BadRequest or NotFound. I'm leaning towards
        # NotFound in order to provide as little feedback as posible to client.
        raise NotFound(UPLOAD_FILE_NOT_FOUND)
    except Forbidden as forb:
        logger.info("%s: Get file content forbidden: %s.", upload_id, forb)
        raise forb
    except Exception as ue:
        logger.info("Unknown error in get file content. "
                    " Add except clauses for '%s'. DO IT NOW!", ue)
        raise InternalServerError(UPLOAD_UNKNOWN_ERROR)

    headers.update({'ARXIV-OWNER': workspace.owner_user_id})
    return filepointer, status.OK, headers


# Log controllers

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
                     " to database.", upload_db_data.upload_id)
        raise InternalServerError(UPLOAD_DB_CONNECT_ERROR)

    if workspace is None:
        raise NotFound(UPLOAD_NOT_FOUND)

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
                     " database.", upload_db_data.upload_id)
        raise InternalServerError(UPLOAD_DB_CONNECT_ERROR)

    if workspace is None:
        raise NotFound(UPLOAD_NOT_FOUND)


    filepointer = workspace.log.open_pointer()
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


# Service log routine + support routine

def __checksum(filepath: str) -> str:
    """Return b64-encoded MD5 hash of file."""
    if os.path.exists(filepath):
        hash_md5 = md5()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return urlsafe_b64encode(hash_md5.digest()).decode('utf-8')
    return ""

def __last_modified(filepath: str) -> str:
    """Return last modified time of file.

    Perameters
    ----------
    filepath : str
        Absolute file path.

    Returns
    -------
    Last modified date string for specified file.
    """
    return datetime.utcfromtimestamp(os.path.getmtime(filepath))

def __content_pointer(log_path: str) -> io.BytesIO:
    """Get a file-pointer for service log.

    Parameters
    ----------
    service_log_path : str
        Absolute path of file manager service log.

    Returns
    -------
    Standard Response tuple containing service log content, HTTP status,
    and HTTP headers.

    """
    return open(log_path, 'rb')


def check_upload_service_log_exists() -> Response:
    """
    Check whether service log exists.

    Note
    ----
    Service log should exist. Response includes size of log and last
    modified date which may be useful for inquiries where client does
    not desire to download entire log file.

    Returns
    -------
    Standard Response tuple containing content, HTTP status, and HTTP headers.
    """
    # Need path to upload.log which is currently stored at top level
    # of filemanager service.

    logger.info("%s: Check whether upload service log exists.")

    # service_log_path is global set during startup log init
    checksum = __checksum(service_log_path)
    size = os.path.getsize(service_log_path)
    modified = __last_modified(service_log_path)
    return {}, status.OK, {'ETag': checksum,
                                    'Content-Length': size,
                                    'Last-Modified': modified
                                    }


def get_upload_service_log() -> Response:
    """
    Return the service-level file manager service log.

    The file manager service-wide log records high-level events and
    significant workspace events. Detailed file upload/file checks details
    will be recorded in workspace log.

    Returns
    -------
    Standard Response tuple containing content, HTTP status, and HTTP headers.
    """
    # service_log_path is global set during startup log init
    checksum = __checksum(service_log_path)
    size = os.path.getsize(service_log_path)
    modified = __last_modified(service_log_path)
    filepointer = __content_pointer(service_log_path)
    headers = {
        "Content-disposition": f"filename={filepointer.name}",
        'ETag': checksum,
        'Content-Length': size,
        'Last-Modified': modified
    }
    return filepointer, status.OK, headers
