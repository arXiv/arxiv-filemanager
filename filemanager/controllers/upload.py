"""Handles all upload-related requests."""

from typing import Tuple, Optional
from datetime import datetime
import json
import logging
import os.path
from hashlib import md5
from base64 import urlsafe_b64encode
import io
from pytz import UTC


from werkzeug.exceptions import NotFound, BadRequest, InternalServerError, \
    NotImplemented, SecurityError, Forbidden

from werkzeug.datastructures import FileStorage
from flask.json import jsonify

from http import HTTPStatus as status
from arxiv.users import domain as auth_domain
from arxiv.base.globals import get_application_config

import filemanager
from filemanager.shared import url_for

from filemanager.domain import Upload
from filemanager.services import uploads
from filemanager.process.upload import Upload as UploadWorkspace
from filemanager.arxiv.file import File

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

def _format_user_information_for_logging(user) -> str:
    """
    Format user information for logging purposes.

    user_id is immutable but difficult to interpret.
    username is a little easier to understand.

    Centralize formatting to make it easier to adjust in the future.

    Parameters
    ----------
    user :
        Contains user information from auth session.

    Returns
    -------
    str
        String formatted with desired user information.

    """
    return f"user:{user.user_id}:{user.username}"


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

DEBUG_UPLOAD = False

# End logging configuration

# exceptions
UPLOAD_MISSING_FILE = 'missing file/archive payload'
UPLOAD_MISSING_FILENAME = 'file argument missing filename or file not selected'
# UPLOAD_FILE_EMPTY = {'file payload is zero length'}

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
UPLOAD_CREATED_CHECKPOINT = 'created checkpoint'
UPLOAD_RESTOREDED_CHECKPOINT = 'restored checkpoint'
UPLOAD_DELETED_CHECKPOINT = 'deleted checkpoint'
UPLOAD_DELETED_ALL_CHECKPOINTS = 'deleted all checkpoint'

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


def delete_workspace(upload_id: int, user) -> Response:
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
    user_string = _format_user_information_for_logging(user)
    logger.info('%s: Deleting upload workspace [%s].', upload_id, user_string)

    # Need to add several checks here

    # At this point I believe we know that caller is authorized to delete the
    # workspace. This is checked at the routes level.

    # Does workspace exist? Has it already been deleted? Generate 400:NotFound error.
    # Do we care is workspace is ACTIVE state? And not released? NO. But log it...
    # Do we want to stash source.log somewhere?
    # Do we care if workspace was modified recently...NO. Log it

    try:
        # Make sure we have an existing upload workspace to work with
        upload_db_data: Optional[Upload] = uploads.retrieve(upload_id)

        if upload_db_data is None:
            # invalid workspace identifier
            # Note: DB entry will exist for workspace that has already been
            #       deleted
            raise NotFound(UPLOAD_NOT_FOUND)


        # Actually remove entire workspace directory structure. Log
        # everything to global log since source log is being removed!

        # Initiate workspace deletion

        # Update database (but keep around) for historical reference. Does not
        # consume very much space. What about source log?
        # Create Upload object
        if upload_db_data.state == Upload.DELETED:
            logger.info("%s: Workspace has already been deleted:"
                        "current state is '%s'", upload_id, upload_db_data.state)
            raise NotFound(UPLOAD_WORKSPACE_NOT_FOUND)

        upload_workspace = UploadWorkspace(upload_id)

        # Call routine that will do the actual work
        upload_workspace.remove_workspace()

        # update database
        if upload_db_data.state != Upload.RELEASED:
            logger.info("%s: Workspace currently in '%s' state.",
                        upload_id, upload_db_data.state)

        upload_db_data.state = Upload.DELETED

        # Store in DB
        uploads.update(upload_db_data)

    except IOError:
        logger.error("%s: Delete workspace request failed ", upload_id)
        raise InternalServerError(CANT_DELETE_FILE)
    except NotFound as nf:
        logger.info("%s: Delete Workspace: '%s'", upload_id, nf)
        raise
    except Exception as ue:
        logger.info("Unknown error in delete workspace. "
                    " Add except clauses for '%s'. DO IT NOW!", ue)
        raise InternalServerError(UPLOAD_UNKNOWN_ERROR)

    # API doesn't provide for returning errors resulting from delete.
    # 401-unautorized and 403-forbidden are handled at routes level.
    # Add 400 response to openapi.yaml

    response_data = {'reason': UPLOAD_DELETED_WORKSPACE}  # Get rid of pylint error
    status_code = status.OK
    return response_data, status_code, {}


def client_delete_file(upload_id: int, public_file_path: str, user) -> Response:
    """Delete a single file.

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
    user_string = _format_user_information_for_logging(user)
    logger.info("%s: Delete file '%s' [%s].", upload_id, public_file_path,
                user_string)

    try:
        # Make sure we have an upload_db_data to work with
        upload_db_data: Optional[Upload] = uploads.retrieve(upload_id)

        if upload_db_data is None:
            # Invalid workspace identifier
            raise NotFound(UPLOAD_NOT_FOUND)
        if upload_db_data.state != Upload.ACTIVE:
            # Do we log anything for these requests
            raise Forbidden(UPLOAD_NOT_ACTIVE)
        if upload_db_data.lock == Upload.LOCKED:
            raise Forbidden(UPLOAD_WORKSPACE_LOCKED)


        # Create Upload object
        upload_workspace = UploadWorkspace(upload_id)

        # Call routine that will do the actual work
        upload_workspace.client_remove_file(public_file_path)

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
        logger.info("%s: Unknown error in delete file. "
                    " Add except clauses for '%s'. DO IT NOW!", upload_id, ue)
        raise InternalServerError(UPLOAD_UNKNOWN_ERROR)

    response_data = _status_data(upload_db_data, upload_workspace)
    response_data.update({
        'reason': UPLOAD_DELETED_FILE,
        'checksum': upload_workspace.get_content_checksum()
    })  # Get rid of pylint errorT
    return response_data, status.OK, {}


def client_delete_all_files(upload_id: int, user) -> Response:
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
    user_string = _format_user_information_for_logging(user)
    logger.info("%s: Deleting all uploaded files from this workspace [%s].",
                upload_id, user_string)

    try:
        # Make sure we have an upload_db_data to work with
        upload_db_data: Optional[Upload] = uploads.retrieve(upload_id)

        if upload_db_data is None:
            # Invalid workspace identifier
            raise NotFound(UPLOAD_NOT_FOUND)
        if upload_db_data.state != Upload.ACTIVE:
            # Do we log anything for these requests
            raise Forbidden(UPLOAD_NOT_ACTIVE)
        if upload_db_data.lock == Upload.LOCKED:
            raise Forbidden(UPLOAD_WORKSPACE_LOCKED)

        # Create Upload object
        upload_workspace = UploadWorkspace(upload_id)

        upload_workspace.client_remove_all_files()


    except IOError:
        logger.error("%s: Delete all files request failed ", upload_id)
        raise InternalServerError(CANT_DELETE_ALL_FILES)
    except NotFound as nf:
        logger.info("%s: DeleteAllFiles: '%s'", upload_id, nf)
        raise
    except Forbidden as forb:
        logger.info("%s: Upload failed: '%s'.", upload_id, forb)
        raise forb
    except Exception as ue:
        logger.info("%s: Unknown error in delete all files. "
                    " Add except clauses for '%s'. DO IT NOW!", upload_id, ue)
        raise InternalServerError(UPLOAD_UNKNOWN_ERROR)

    response_data = _status_data(upload_db_data, upload_workspace)
    response_data.update({
        'reason': UPLOAD_DELETED_ALL_FILES,
        'checksum': upload_workspace.get_content_checksum()
    })  # Get rid of pylint error
    return response_data, status.OK, {}


def upload(upload_id: Optional[int], file: FileStorage, archive: str,
           user: auth_domain.User, ancillary: bool = False,
           checkpoint: bool = False, clear_source_files: bool = False) \
        -> Response:
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
    # TODO: Hook up async processing (celery/redis) - doesn't work now
    # TODO: Will likely delete this code if processing time is reasonable
    # print(f'Controller: Schedule upload_db_data task for {upload_id}')
    #
    # result = sanitize_upload.delay(upload_id, file)
    #
    # headers = {'Location': url_for('upload_api.upload_status',
    #                              task_id=result.task_id)}
    # return ACCEPTED, status.ACCEPTED, headers
    # End delete

    # Log username and upload_id or new
    username = None
    if user:
        user_string = _format_user_information_for_logging(user);

    id_string = upload_id
    if upload_id == None:
        id_string = "New"

    # Check arguments for basic qualities like existing and such.

    # File argument is required to exist and have a name associated with it.
    # It is standard practice that if user fails to select file the filename is null.
    ##logger.debug('%s: Upload request for [%s]', id_string, user_string)
    if file is None:
        # Crash and burn...not quite...do we need info about client?
        logger.error('%s: Upload request is missing file/archive payload.',
                     upload_id)
        raise BadRequest(UPLOAD_MISSING_FILE)

    if file.filename == '':
        # Client needs to select file, or provide name to upload payload
        logger.error('%s: Upload file is missing filename. File to upload may '
                     'not be selected.', id_string)
        raise BadRequest(UPLOAD_MISSING_FILENAME)

    # What about archive argument.
    if archive is None:
        # No longer need archive for stamp
        pass

    # If this is a new upload then we need to create a workspace and add to database.
    if upload_id is None:
        ##logger.debug('This is a new upload workspace.')
        try:
            logger.info("Create new workspace: Upload request: "
                        "file='%s' archive='%s' [%s]", file.filename,
                        archive, user_string)
            user_id = str(user.user_id)

            if archive is None:
                arch = ''
            else:
                arch = archive

            current_time = datetime.now(UTC)
            new_upload = Upload(owner_user_id=user_id, archive=arch,
                                created_datetime=current_time,
                                modified_datetime=current_time,
                                state=Upload.ACTIVE)
            # Store in DB
            uploads.store(new_upload)

            upload_id = new_upload.upload_id

        except IOError as e:
            logger.info("Error creating new workspace: %s", e)
            raise InternalServerError(f'{UPLOAD_IO_ERROR}: {e}')
        except (TypeError, ValueError) as dbe:
            logger.info("Error adding new workspace to database: '%s'.", dbe)
            raise InternalServerError(UPLOAD_DB_ERROR)
        except Exception as ue:
            logger.info("Unknown error creating new workspace. "
                        " Add except clauses for '%s'. DO IT NOW!", ue)
            raise InternalServerError(UPLOAD_UNKNOWN_ERROR)

    # At this point we expect upload to exist in system
    try:

        upload_db_data: Optional[Upload] = uploads.retrieve(upload_id)

        if upload_db_data is None:
            # Invalid workspace identifier
            raise NotFound(UPLOAD_NOT_FOUND)
        if upload_db_data.state != Upload.ACTIVE:
            # Do we log anything for these requests
            logger.debug('Forbidden, workspace not active')
            raise Forbidden(UPLOAD_NOT_ACTIVE)
        if upload_db_data.lock == Upload.LOCKED:
            logger.debug('Forbidden, workspace locked')
            raise Forbidden(UPLOAD_WORKSPACE_LOCKED)

        # Now handle upload package - process file or gzipped tar archive

        # NOTE: This will need to be migrated to task.py using Celery at
        #       some point in future. Depends in time it takes to process
        #       uploads.retrieve
        logger.info("%s: Upload files to existing "
                    "workspace: file='%s' [%s].", upload_db_data.upload_id,
                    file.filename, user_string)

        # Keep track of how long processing upload_db_data takes
        start_datetime = datetime.now(UTC)

        # Create Upload object
        upload_workspace = UploadWorkspace(upload_id)

        # checkpoint - create backup of user uploaded files
        if checkpoint:
            checksum = upload_workspace.create_checkpoint(user)

        # Admin may want to clear out existing files so that existing files
        # do not cause problems or interfere with processing uploaded files.
        #
        # Steps are 1) checkpoint 2) clear source files 3) unpack upload
        #
        if clear_source_files:
            upload_workspace.client_remove_all_files()

        # Process uploaded file(s)
        upload_workspace.process_upload(file, ancillary=ancillary)

        completion_datetime = datetime.now(UTC)

        # Keep track of files processed (this included deleted files)
        file_list = upload_workspace.create_file_upload_summary()

        # Determine readiness state of upload content
        upload_status = Upload.READY

        if upload_workspace.has_errors():
            upload_status = Upload.ERRORS
        elif upload_workspace.has_warnings():
            upload_status = Upload.READY_WITH_WARNINGS

        # Create combine list of errors and warnings
        # TODO: Should I do this in Upload package?? Likely...
        all_errors_and_warnings = []

        for warn in upload_workspace.get_warnings():
            public_filepath, warning_message = warn
            all_errors_and_warnings.append(['warn', public_filepath, warning_message])

        for error in upload_workspace.get_errors():
            public_filepath, warning_message = error
            # TODO: errors renamed fatal. Need to review 'errors' as to whether they are 'fatal'
            all_errors_and_warnings.append(['fatal', public_filepath, warning_message])

        # Prepare upload_db_data details (DB). I'm assuming that in memory Redis
        # is not sufficient for results that may be needed in the distant future.
        # errors_and_warnings = upload_workspace.get_errors() + upload_workspace.get_warnings()
        errors_and_warnings = all_errors_and_warnings
        upload_db_data.lastupload_logs = json.dumps(errors_and_warnings)
        upload_db_data.lastupload_start_datetime = start_datetime
        upload_db_data.lastupload_completion_datetime = completion_datetime
        upload_db_data.lastupload_file_summary = json.dumps(file_list)
        upload_db_data.lastupload_upload_status = upload_status
        upload_db_data.state = Upload.ACTIVE

        # Store in DB
        uploads.update(upload_db_data)

        if DEBUG_UPLOAD:
            logger.info("%s: Processed upload. "
                        "Saved to DB. Preparing upload summary.",
                        upload_db_data.upload_id)

        # Do we want affirmative log messages after processing each request
        # or maybe just report errors like:
        #    logger.info(f"{upload_db_data.upload_id}: Finished processing ...")

        # Upload action itself has very simple response
        headers = {'Location': url_for('upload_api.upload_files',
                                       upload_id=upload_db_data.upload_id)}

        status_code = status.CREATED

        response_data = _status_data(upload_db_data, upload_workspace)

        if DEBUG_UPLOAD:
            logger.debug('%s: Upload response data: %s',
                         upload_db_data.upload_id, response_data)
        return response_data, status_code, headers

    except IOError as e:
        logger.error("%s: File upload_db_data request failed "
                     "for file='%s'", upload_id, file.filename)
        raise InternalServerError(f'{UPLOAD_IO_ERROR}: {e}') from e
    except (TypeError, ValueError) as dbe:
        logger.info("%s: Error updating database: '%s'", upload_id, dbe)
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
        logger.info("%s: Unknown error with existing workspace."
                    " Add except clauses for '%s'. DO IT NOW!", upload_id, ue)
        raise InternalServerError(UPLOAD_UNKNOWN_ERROR)

    return None


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
        upload_db_data: Optional[Upload] = uploads.retrieve(upload_id)

        if upload_db_data is None:
            status_code = status.NOT_FOUND
            response_data = UPLOAD_NOT_FOUND
            raise NotFound(UPLOAD_NOT_FOUND)

        # Create Upload object
        upload_workspace = UploadWorkspace(upload_id)
        file_list = upload_workspace.create_file_list()

        details_list = []
        for fileObj in file_list:
            file_details = {
                'name': fileObj.name,
                'public_filepath': fileObj.public_filepath,
                'size': fileObj.size,
                'type': fileObj.type_string,
                'modified_datetime': fileObj.modified_datetime
            }
            if not fileObj.removed:
                details_list.append(file_details)

        status_code = status.OK
        response_data = _status_data(upload_db_data, upload_workspace)
        response_data.update({'files': details_list, 'errors': []})

        if DEBUG_UPLOAD:
            logger.info("%s: Upload summary request.",
                        upload_db_data.upload_id)

    except IOError:
        # response_data = ERROR_RETRIEVING_UPLOAD
        # status_code = status.INTERNAL_SERVER_ERROR
        raise InternalServerError(ERROR_RETRIEVING_UPLOAD)
    except (TypeError, ValueError):
        logger.info("%s: Error updating database.", upload_id)
        raise InternalServerError(UPLOAD_DB_ERROR)
    except NotFound as nf:
        logger.info("%s: UploadSummary: '%s'", upload_id, nf)
        raise
    except Exception as ue:
        logger.info("%s: Unknown error with existing workspace."
                    " Add except clauses for '%s'. DO IT NOW!", upload_id, ue)
        raise InternalServerError(UPLOAD_UNKNOWN_ERROR)

    return response_data, status_code, {}


# TODO: How do we keep submitter from updating workspace while admin
# TODO: is working on it? These locks currently mean no changes are allowed.
# TODO: Is there another flavor of lock? Administrative lock? Or do admin
# TODO: and submitter coordinate on changes to upload workspace.

def upload_lock(upload_id: int, user) -> Response:
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
    tuple
        Standard Response tuple containing response content, HTTP status, and
        HTTP headers.

    """
    user_string = _format_user_information_for_logging(user);
    logger.info("%s: Lock upload workspace [%s].", upload_id, user_string)

    try:
        # Make sure we have an upload_db_data to work with
        upload_db_data: Optional[Upload] = uploads.retrieve(upload_id)

        if upload_db_data is None:
            # Invalid workspace identifier
            raise NotFound(UPLOAD_NOT_FOUND)

        # Lock upload workspace
        # update database
        if upload_db_data.lock == Upload.LOCKED:
            logger.info("%s: Lock: Workspace is already locked.", upload_id)
        else:
            upload_db_data.lock = Upload.LOCKED

            # Store in DB
            uploads.update(upload_db_data)

        response_data = {'reason': UPLOAD_LOCKED_WORKSPACE}  # Get rid of pylint error
        status_code = status.OK

    except IOError:
        logger.error("%s: Lock workspace request failed ", upload_id)
        raise InternalServerError(CANT_DELETE_FILE)
    except NotFound as nf:
        logger.info("%s: Lock: %s", upload_id, nf)
        raise
    except Exception as ue:
        logger.info("%s: Unknown error lock workspace. "
                    " Add except clauses for '%s'. DO IT NOW!", upload_id, ue)
        raise InternalServerError(UPLOAD_UNKNOWN_ERROR)

    return response_data, status_code, {}


def upload_unlock(upload_id: int, user) -> Response:
    """
    Unlock upload workspace.

    Parameters
    ----------
    upload_id : int
        The unique identifier for upload workspace.

    Returns
    -------
    tuple
        Standard Response tuple containing response content, HTTP status, and
        HTTP headers.

    """
    # response_data = ERROR_REQUEST_NOT_IMPLEMENTED
    # status_code = status.INTERNAL_SERVER_ERROR
    user_string = _format_user_information_for_logging(user);
    logger.info("%s: Unlock upload workspace [%s].", upload_id, user_string)

    try:
        # Make sure we have an upload_db_data to work with
        upload_db_data: Optional[Upload] = uploads.retrieve(upload_id)

        if upload_db_data is None:
            # Invalid workspace identifier
            raise NotFound(UPLOAD_NOT_FOUND)

        # Lock upload workspace
        # update database
        if upload_db_data.lock == Upload.UNLOCKED:
            logger.info("%s: Unlock: Workspace is already unlocked.", upload_id)
        else:
            upload_db_data.lock = Upload.UNLOCKED

            # Store in DB
            uploads.update(upload_db_data)

        response_data = {'reason': UPLOAD_UNLOCKED_WORKSPACE}  # Get rid of pylint error
        status_code = status.OK

    except IOError:
        logger.error("%s: Unlock workspace request failed ", upload_id)
        raise InternalServerError(CANT_DELETE_FILE)
    except NotFound as nf:
        logger.info("%s: Unlock workspace: %s", upload_id, nf)
        raise
    except Exception as ue:
        logger.info("%s: Unknown error in unlock workspace. "
                    " Add except clauses for '%s'. DO IT NOW!", upload_id, ue)
        raise InternalServerError(UPLOAD_UNKNOWN_ERROR)

    return response_data, status_code, {}


def upload_release(upload_id: int, user) -> Response:
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

    user_string = _format_user_information_for_logging(user);

    # Expect workspace to be in ACTIVE state.

    try:
        # Make sure we have an upload_db_data to work with
        upload_db_data: Optional[Upload] = uploads.retrieve(upload_id)

        if upload_db_data is None:
            # Invalid workspace identifier
            raise NotFound(UPLOAD_NOT_FOUND)

        # Release upload workspace
        # update database

        if upload_db_data.state == Upload.RELEASED:
            logger.info("%s: Release: Workspace has already been released "
                        "[%s].", upload_id, user_string)
            response_data = {'reason': UPLOAD_RELEASED_WORKSPACE}  # Should this be an error?
            status_code = status.OK
        elif upload_db_data.state == Upload.DELETED:
            logger.info("%s: Release failed: Workspace has been deleted [%s].",
                        upload_id, user_string)
            # response_data = {'reason': UPLOAD_WORKSPACE_ALREADY_DELETED}
            # status_code = status.OK
            raise NotFound(UPLOAD_WORKSPACE_ALREADY_DELETED)
        elif upload_db_data.state == Upload.ACTIVE:
            logger.info("%s: Release upload workspace [%s].", upload_id,
                        user_string)

            upload_db_data.state = Upload.RELEASED

            # Store in DB
            uploads.update(upload_db_data)

            response_data = {'reason': UPLOAD_RELEASED_WORKSPACE}  # Get rid of pylint error
            status_code = status.OK

    except IOError:
        logger.error("%s: Release workspace request failed.", upload_id)
        raise InternalServerError(CANT_RELEASE_WORKSPACE)
    except NotFound as nf:
        logger.info("%s: Release workspace: %s", upload_id, nf)
        raise
    except Exception as ue:
        logger.info("%s: Unknown error in release workspace. "
                    " Add except clauses for '%s'. DO IT NOW!", upload_id, ue)
        raise InternalServerError(UPLOAD_UNKNOWN_ERROR)

    return response_data, status_code, {}


def upload_unrelease(upload_id: int, user) -> Response:
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

    user_string = _format_user_information_for_logging(user);

    # Expect workspace to be in RELEASED state.

    logger.info("%s: Unrelease upload workspace [%s].", upload_id, user_string)

    try:
        # Make sure we have an upload_db_data to work with
        upload_db_data: Optional[Upload] = uploads.retrieve(upload_id)

        if upload_db_data is None:
            # Invalid workspace identifier
            raise NotFound(UPLOAD_NOT_FOUND)

        # Unrelease upload workspace
        # update database
        if upload_db_data.state == Upload.DELETED:
            # logger.info(f"{upload_id}: Unrelease Failed: Workspace has been deleted.")
            # response_data = {'reason': UPLOAD_WORKSPACE_ALREADY_DELETED}
            # tatus_code = status.OK
            raise NotFound(UPLOAD_WORKSPACE_ALREADY_DELETED)

        if upload_db_data.state == Upload.ACTIVE:
            logger.info("%s: Unrelease: Workspace is already active [%s].",
                        upload_id, user_string)
            response_data = {'reason': UPLOAD_UNRELEASED_WORKSPACE}  # Should this be an error?
            status_code = status.OK
        elif upload_db_data.state == Upload.RELEASED:
            logger.info("%s: Unrelease upload workspace [%s].", upload_id,
                        user_string)

            upload_db_data.state = Upload.ACTIVE

            # Store in DB
            uploads.update(upload_db_data)

            response_data = {'reason': UPLOAD_UNRELEASED_WORKSPACE}
            status_code = status.OK

    except IOError:
        logger.error("%s: Unrelease workspace request failed.", upload_id)
        raise InternalServerError(CANT_DELETE_FILE)
    except NotFound as nf:
        logger.info("%s: Unrelease workspace: '%s'", upload_id, nf)
        raise
    except Exception as ue:
        logger.info("%s: Unknown error in unrelease workspace. "
                    " Add except clauses for '%s'. DO IT NOW!", upload_id, ue)
        raise InternalServerError(UPLOAD_UNKNOWN_ERROR)

    return response_data, status_code, {}


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
    tuple
        Standard Response tuple containing response content, HTTP status, and
        HTTP headers.

    """
    try:
        upload_db_data: Optional[Upload] = uploads.retrieve(upload_id)
    except IOError:
        logger.error("%s: ContentExistsCheck: There was a problem connecting "
                     "to database.", upload_id)
        raise InternalServerError(UPLOAD_DB_CONNECT_ERROR)

    if upload_db_data is None:
        raise NotFound(UPLOAD_NOT_FOUND)

    upload_workspace = UploadWorkspace(upload_id)

    # This will potentially build content package if it does not exist
    checksum = upload_workspace.get_content_checksum()
    modified = ''
    size = 0

    # Double check package exists
    if upload_workspace.content_package_exists:
        modified = upload_workspace.content_package_modified
        size = upload_workspace.content_package_size
        return {}, status.OK, {'ETag': checksum,
                                        'Content-Length': size,
                                        'Last-Modified': modified}

    return {}, status.OK, {'ETag': checksum}


def get_upload_content(upload_id: int, user) -> Response:
    """
    Package up files for downloading as a compressed gzipped tar file.

    Parameters
    ----------
    upload_id : int
        The unique identifier for upload workspace.

    Returns
    -------
    tuple
        Standard Response tuple containing compressed content, HTTP status, and
        HTTP headers.

    """
    user_string = _format_user_information_for_logging(user);
    logger.info("%s: Download workspace source content [%s].", upload_id,
                user_string)

    try:
        upload_db_data: Optional[Upload] = uploads.retrieve(upload_id)
    except IOError:
        logger.error("%s: Download workspace source content: There was a "
                     "problem connecting to database.", upload_id)
        raise InternalServerError(UPLOAD_DB_CONNECT_ERROR)

    if upload_db_data is None:
        raise NotFound(UPLOAD_NOT_FOUND)
    upload_workspace = UploadWorkspace(upload_id)
    checksum = upload_workspace.get_content_checksum()
    try:
        filepointer = upload_workspace.get_content()
    except FileNotFoundError as e:
        raise NotFound("No content in workspace") from e
    headers = {
        "Content-disposition": f"filename={filepointer.name}",
        'ETag': checksum
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
    tuple
        Standard Response tuple containing content, HTTP status, and
        HTTP headers.

    """
    try:
        upload_db_data: Optional[Upload] = uploads.retrieve(upload_id)
    except IOError:
        logger.error("%s: ContentFileExistsCheck: There was a problem "
                     "connecting to database.", upload_id)
        raise InternalServerError(UPLOAD_DB_CONNECT_ERROR)

    if upload_db_data is None:
        raise NotFound(UPLOAD_NOT_FOUND)

    try:

        upload_workspace = UploadWorkspace(upload_id)

        # file exists
        if upload_workspace.content_file_exists(public_file_path):
            size = upload_workspace.get_content_file_size(public_file_path)
            modified = upload_workspace.get_content_file_last_modified(public_file_path)
            checksum = upload_workspace.get_content_file_checksum(public_file_path)
            return {}, status.OK, {'ETag': checksum,
                                            'Content-Length': size,
                                            'Last-Modified': modified
                                            }

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
        logger.info("%s: Unknown error in content file exists operation. "
                    " Add except clauses for '%s'. DO IT NOW!", upload_id, ue)
        raise InternalServerError(UPLOAD_UNKNOWN_ERROR)

    return {}, status.OK, {'ETag': checksum}


def get_upload_file_content(upload_id: int, public_file_path: str, user) -> Response:
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
        upload_db_data: Optional[Upload] = uploads.retrieve(upload_id)
    except IOError:
        logger.error("%s: Download file: There was a problem connecting to database.",
                     upload_db_data.upload_id)
        raise InternalServerError(UPLOAD_DB_CONNECT_ERROR)

    if upload_db_data is None:
        raise NotFound(UPLOAD_NOT_FOUND)

    try:

        user_string = _format_user_information_for_logging(user);
        logger.info("%s: Download file '%s' [%s].", upload_id,
                    public_file_path, user_string)


        upload_workspace = UploadWorkspace(upload_id)

        # Returns path if file exists
        if upload_workspace.content_file_exists(public_file_path):
            size = upload_workspace.get_content_file_size(public_file_path)
            modified = upload_workspace.get_content_file_last_modified(public_file_path)
            checksum = upload_workspace.get_content_file_checksum(public_file_path)
            filepointer = upload_workspace.get_content_file_pointer(public_file_path)
            headers = {
                "Content-disposition": f"filename={filepointer.name}",
                'ETag': checksum,
                'Content-Length': size,
                'Last-Modified': modified
            }
        else:
            raise NotFound(f"File '{public_file_path}' not found.")

    except IOError:
        logger.error("%s: Get uploaded file request failed ", upload_db_data.upload_id)
        raise InternalServerError(CANT_DELETE_FILE)
    except NotFound as nf:
        logger.info("%s: GetUploadFile: %s", upload_id, nf)
        raise nf
    except SecurityError as secerr:
        logger.info("%s: %s", upload_id, secerr.description)
        # TODO: Should this be BadRequest or NotFound. I'm leaning towards
        # NotFound in order to provide as little feedback as posible to client.
        raise NotFound(UPLOAD_FILE_NOT_FOUND)
    except Forbidden as forb:
        logger.info("%s: Get uploaded file forbidden: %s.", upload_id, forb)
        raise forb
    except Exception as ue:
        logger.info("%s: Unknown error in get uploaded file. "
                    " Add except clauses for '%s'. DO IT NOW!", upload_id, ue)
        raise InternalServerError(UPLOAD_UNKNOWN_ERROR)

    return filepointer, status.OK, headers


# Log controllers

def check_upload_source_log_exists(upload_id: int) -> Response:
    """
    Determine if source log associated with upload workspace exists.

    Parameters
    ----------
    upload_id : int
        The unique identifier for upload workspace.

    Returns
    -------
    Note: This routine currently retrieves the source log for active upload
    workspaces. Technically, the upload source log is available for a 'deleted'
    workspace, since we stash this away before we actually delete the workspace.
    The justification to save is because the upload source log contains useful
    information that the admins sometime desire after a submission has been
    published and the associated workspace deleted.
    """
    try:
        upload_db_data: Optional[Upload] = uploads.retrieve(upload_id)
    except IOError:
        logger.error("%s: SourceLogExistCheck: There was a problem connecting to database.",
                     upload_db_data.upload_id)
        raise InternalServerError(UPLOAD_DB_CONNECT_ERROR)

    if upload_db_data is None:
        raise NotFound(UPLOAD_NOT_FOUND)

    upload_workspace = UploadWorkspace(upload_id)

    checksum = upload_workspace.source_log_checksum
    size = upload_workspace.source_log_size
    modified = upload_workspace.source_log_last_modified

    return {}, status.OK, {'ETag': checksum,
                           'Content-Length': size,
                           'Last-Modified': modified}


def get_upload_source_log(upload_id: int, user) -> Response:
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
    tuple
        Standard Response tuple containing content, HTTP status, and
        HTTP headers.

    """
    try:

        user_string = _format_user_information_for_logging(user);
        logger.info("%s: Download source log [%s].", upload_id, user_string)

        upload_db_data: Optional[Upload] = uploads.retrieve(upload_id)
    except IOError:
        logger.error("%s: GetSourceLog: There was a problem connecting to database.",
                     upload_db_data.upload_id)
        raise InternalServerError(UPLOAD_DB_CONNECT_ERROR)

    if upload_db_data is None:
        raise NotFound(UPLOAD_NOT_FOUND)

    upload_workspace = UploadWorkspace(upload_id)

    checksum = upload_workspace.source_log_checksum
    size = upload_workspace.source_log_size
    modified = upload_workspace.source_log_last_modified

    filepointer = upload_workspace.get_source_log_file_pointer()
    if filepointer:
        name = filepointer.name
    else:
        name = ""

    headers = {
        "Content-disposition": f"filename={name}",
        'ETag': checksum,
        'Content-Length': size,
        'Last-Modified': modified
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
    io.BytesIO
        Open file pointer for service log content.

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
    tuple
        Standard Response tuple containing content, HTTP status, and
        HTTP headers.

    """
    # Need path to upload.log which is currently stored at top level
    # of filemanager service.

    # service_log_path is global set during startup log init
    checksum = __checksum(service_log_path)
    size = os.path.getsize(service_log_path)
    modified = __last_modified(service_log_path)
    return {}, status.OK, {'ETag': checksum,
                                    'Content-Length': size,
                                    'Last-Modified': modified
                                    }


def get_upload_service_log(user) -> Response:
    """
    Return the service-level file manager service log.

    The file manager service-wide log records high-level events and
    significant workspace events. Detailed file upload/file checks details
    will be recorded in workspace log.

    Returns
    -------
    tuple
        Standard Response tuple containing content, HTTP status, and
        HTTP headers.

    """
    user_string = _format_user_information_for_logging(user);
    logger.info("sys: Download file manager service log [%s].",
                user_string)

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


# Checkpoint support routines

def create_checkpoint(upload_id: int, user) -> Response:
    """
    Create checkpoint.

    Admins will be able to manage checkpoints.

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
    user_string = _format_user_information_for_logging(user)
    logger.info("%s: Create checkpoint [%s].", upload_id, user_string)

    try:
        # Make sure we have an upload_db_data to work with
        upload_db_data: Optional[Upload] = uploads.retrieve(upload_id)

        if upload_db_data is None:
            # Invalid workspace identifier
            raise NotFound(UPLOAD_NOT_FOUND)

        upload_workspace = UploadWorkspace(upload_id)
        checksum = upload_workspace.create_checkpoint(user)

        ###
        # Lock upload workspace
        # update database
        #if upload_db_data.lock == Upload.LOCKED:
        #    logger.info("%s: Lock: Workspace is already locked.", upload_id)
        #else:
        #    upload_db_data.lock = Upload.LOCKED
        #
        # Store in DB
        #   uploads.update(upload_db_data)
        ###

        response_data = {'reason': UPLOAD_CREATED_CHECKPOINT}  # Get rid of pylint error
        status_code = status.OK

    except IOError:
        logger.error("%s: Create checkpoint request failed ", upload_id)
        raise InternalServerError(CANT_DELETE_FILE)
    except NotFound as nf:
        logger.info("%s: Create checkpoint: %s", upload_id, nf)
        raise
    except Exception as ue:
        logger.info("%s: Unknown error create checkpoint. "
                    " Add except clauses for '%s'. DO IT NOW!", upload_id, ue)
        raise InternalServerError(UPLOAD_UNKNOWN_ERROR)

    return response_data, status_code, {'ETag': checksum}


def list_checkpoints(upload_id: int, user) -> Response:
    """
    List checkpoints.

    Admins will be able to manage checkpoints.

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
    user_string = _format_user_information_for_logging(user)
    logger.info("%s: List checkpoints [%s].", upload_id, user_string)

    try:
        # Make sure we have an upload_db_data to work with
        upload_db_data: Optional[Upload] = uploads.retrieve(upload_id)

        if upload_db_data is None:
            # Invalid workspace identifier
            raise NotFound(UPLOAD_NOT_FOUND)

        upload_workspace = UploadWorkspace(upload_id)
        checkpoint_list = upload_workspace.list_checkpoints(user)


        response_data = {'upload_id': upload_id,
                         'checkpoints': json.loads(json.dumps(checkpoint_list))
                         }  # Get rid of pylint error
        status_code = status.OK

    except IOError:
        logger.error("%s: List checkpoints request failed ", upload_id)
        raise InternalServerError(CANT_DELETE_FILE)
    except NotFound as nf:
        logger.info("%s: List checkpoints: %s", upload_id, nf)
        raise
    except Exception as ue:
        logger.info("%s: Unknown error while listing checkpoints. "
                    " Add except clauses for '%s'. DO IT NOW!", upload_id, ue)
        raise InternalServerError(UPLOAD_UNKNOWN_ERROR)

    return response_data, status_code, {}


def restore_checkpoint(upload_id: int, checkpoint_checksum: str,
                        user) -> Response:
    """
    Restore checkpoint specified by checkpoint_checksum.

    Admins will be able to manage checkpoints.

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
    user_string = _format_user_information_for_logging(user)
    logger.info("%s: Restore checkpoints [%s].", upload_id, user_string)

    try:
        # Make sure we have an upload_db_data to work with
        upload_db_data: Optional[Upload] = uploads.retrieve(upload_id)

        if upload_db_data is None:
            # Invalid workspace identifier
            raise NotFound(UPLOAD_NOT_FOUND)

        upload_workspace = UploadWorkspace(upload_id)
        result = upload_workspace.restore_checkpoint(checkpoint_checksum, user)


        response_data = {'reason': f"Restored checkpoint '{checkpoint_checksum}'"}  # Get rid of pylint error
        status_code = status.OK

    except IOError:
        logger.error("%s: Restore checkpoint request failed ", upload_id)
        raise InternalServerError(CANT_DELETE_FILE)
    except NotFound as nf:
        logger.info("%s: Restore checkpoint: %s", upload_id, nf)
        raise
    except Exception as ue:
        logger.info("%s: Unknown error while restoring checkpoint. "
                    " Add except clauses for '%s'. DO IT NOW!", upload_id, ue)
        raise InternalServerError(UPLOAD_UNKNOWN_ERROR)

    return response_data, status_code, {}



def delete_checkpoint(upload_id: int, checkpoint_checksum: str,
                        user) -> Response:
    """
    Delete checkpoint specified by checkpoint_checksum.

    Admins will be able to manage checkpoints.

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
    user_string = _format_user_information_for_logging(user)
    logger.info("%s: Delete checkpoint '%s' [%s].", upload_id,
                checkpoint_checksum, user_string)

    try:
        # Make sure we have an upload_db_data to work with
        upload_db_data: Optional[Upload] = uploads.retrieve(upload_id)

        if upload_db_data is None:
            # Invalid workspace identifier
            raise NotFound(UPLOAD_NOT_FOUND)

        upload_workspace = UploadWorkspace(upload_id)
        result = upload_workspace.delete_checkpoint(checkpoint_checksum, user)


        response_data = {'reason': f"Deleted checkpoint '{checkpoint_checksum}'"}  # Get rid of pylint error
        status_code = status.OK

    except IOError:
        logger.error("%s: Deleted checkpoint request failed ", upload_id)
        raise InternalServerError(CANT_DELETE_FILE)
    except NotFound as nf:
        logger.info("%s: Checkpoint '%s'not found: %s", upload_id,
                    checkpoint_checksum, nf)
        raise
    except Exception as ue:
        logger.info("%s: Unknown error while deleting checkpoint. "
                    " Add except clauses for '%s'. DO IT NOW!", upload_id, ue)
        raise InternalServerError(UPLOAD_UNKNOWN_ERROR)

    return response_data, status_code, {}


def delete_all_checkpoints(upload_id: int, user) -> Response:
    """
    Delete all checkpoint files.

    Admins will be able to manage checkpoints.

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
    user_string = _format_user_information_for_logging(user)
    logger.info("%s: Delete all checkpoints [%s].", upload_id, user_string)

    try:
        # Make sure we have an upload_db_data to work with
        upload_db_data: Optional[Upload] = uploads.retrieve(upload_id)

        if upload_db_data is None:
            # Invalid workspace identifier
            raise NotFound(UPLOAD_NOT_FOUND)

        upload_workspace = UploadWorkspace(upload_id)
        checkpoint_list = upload_workspace.delete_all_checkpoints(user)


        response_data = {'reason': f"Deleted all checkpoints."}  # Get rid of pylint error
        status_code = status.OK

    except IOError:
        logger.error("%s: Delete all checkpoints request failed ", upload_id)
        raise InternalServerError(CANT_DELETE_FILE)
    except NotFound as nf:
        logger.info("%s: Delete all checkpoints: %s", upload_id, nf)
        raise
    except Exception as ue:
        logger.info("%s: Unknown error while deleting all checkpoints. "
                    " Add except clauses for '%s'. DO IT NOW!", upload_id, ue)
        raise InternalServerError(UPLOAD_UNKNOWN_ERROR)

    return response_data, status_code, {}


def check_checkpoint_file_exists(upload_id: int, checkpoint_checksum: str) -> Response:
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
        upload_db_data: Optional[Upload] = uploads.retrieve(upload_id)
    except IOError:
        logger.error("%s: CheckpointFileExistsCheck: There was a problem "
                     "connecting to database.", upload_id)
        raise InternalServerError(UPLOAD_DB_CONNECT_ERROR)

    if upload_db_data is None:
        raise NotFound(UPLOAD_NOT_FOUND)

    ##logger.info("%s: Checkpoint content file exists request.", upload_id)

    try:

        upload_workspace = UploadWorkspace(upload_id)

        # file exists
        if upload_workspace.checkpoint_file_exists(checkpoint_checksum):
            size = upload_workspace.get_checkpoint_file_size(checkpoint_checksum)
            modified = upload_workspace.get_checkpoint_file_last_modified(checkpoint_checksum)
            #checksum = upload_workspace.content_file_checksum(public_file_path)
            return {}, status.OK, {'ETag': checkpoint_checksum,
                                   'Content-Length': size,
                                   'Last-Modified': modified
                                   }

        raise NotFound(f"Checksum '{checkpoint_checksum}' not found.")

    except IOError:
        logger.error("%s: Checkpoint file exists request failed ", upload_db_data.upload_id)
        raise InternalServerError(CANT_DELETE_FILE)
    except NotFound as nf:
        logger.info("%s: Checkpoint file not found: %s", upload_id, nf)
        raise nf
    except SecurityError as secerr:
        logger.info("%s: %s", upload_id, secerr.description)
        # TODO: Should this be BadRequest or NotFound. I'm leaning towards
        # NotFound in order to provide as little feedback as posible to client.
        raise NotFound("Checkpoint file not found.")
    except Forbidden as forb:
        logger.info("%s: Operation forbidden: %s.", upload_id, forb)
        raise forb
    except Exception as ue:
        logger.info("%s: Unknown error in checkpoint file exists operation. "
                    " Add except clauses for '%s'. DO IT NOW!", upload_id, ue)
        raise InternalServerError(UPLOAD_UNKNOWN_ERROR)

    return {}, status.OK, {'ETag': checkpoint_checksum}


def get_checkpoint_file(upload_id: int, checkpoint_checksum: str, user) -> Response:
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
    try:

        user_string = _format_user_information_for_logging(user)
        logger.info("%s: Download checkpoint: '%s' [%s].", upload_id,
                    checkpoint_checksum, user_string)

        upload_db_data: Optional[Upload] = uploads.retrieve(upload_id)
    except IOError:
        logger.error("%s: CheckpointFileDownload: There was a problem connecting to database.",
                     upload_db_data.upload_id)
        raise InternalServerError(UPLOAD_DB_CONNECT_ERROR)

    try:

        upload_workspace = UploadWorkspace(upload_id)

        # Returns path if file exists
        if upload_workspace.checkpoint_file_exists(checkpoint_checksum):
            size = upload_workspace.get_checkpoint_file_size(checkpoint_checksum)
            modified = upload_workspace.get_checkpoint_file_last_modified(checkpoint_checksum)
            #checksum = upload_workspace.content_file_checksum(public_file_path)
            filepointer = upload_workspace.get_checkpoint_file_pointer(checkpoint_checksum)
            headers = {
                "Content-disposition": f"filename={filepointer.name}",
                'ETag': checkpoint_checksum,
                'Content-Length': size,
                'Last-Modified': modified
            }
        else:
            raise NotFound(f"File '{checkpoint_checksum}' not found.")

    except IOError:
        logger.error("%s: Checkpoint file request failed ", upload_db_data.upload_id)
        raise InternalServerError(UPLOAD_DB_CONNECT_ERROR)
    except NotFound as nf:
        logger.info("%s: CheckpointFileDownload: %s", upload_id, nf)
        raise nf
    except SecurityError as secerr:
        logger.info("%s: %s", upload_id, secerr.description)
        # TODO: Should this be BadRequest or NotFound. I'm leaning towards
        # NotFound in order to provide as little feedback as posible to client.
        raise NotFound(UPLOAD_FILE_NOT_FOUND)
    except Forbidden as forb:
        logger.info("%s: Checkpoint file forbidden: %s.", upload_id, forb)
        raise forb
    except Exception as ue:
        logger.info("%s: Unknown error in get checkpoint file. "
                    " Add except clauses for '%s'. DO IT NOW!", upload_id, ue)
        raise InternalServerError(UPLOAD_UNKNOWN_ERROR)

    return filepointer, status.OK, headers


def _status_data(upload_db_data: Upload,
                 upload_workspace: UploadWorkspace) -> dict:
    return {
        'upload_id': upload_db_data.upload_id,
        'upload_total_size': upload_workspace.total_upload_size,
        'upload_compressed_size': upload_workspace.content_package_size,
        'created_datetime': upload_db_data.created_datetime,
        'modified_datetime': upload_db_data.modified_datetime,
        'start_datetime': upload_db_data.lastupload_start_datetime,
        'completion_datetime': upload_db_data.lastupload_completion_datetime,
        'files': json.loads(upload_db_data.lastupload_file_summary),
        'errors': json.loads(upload_db_data.lastupload_logs),
        'upload_status': upload_db_data.lastupload_upload_status,
        'workspace_state': upload_db_data.state,
        'lock_state': upload_db_data.lock,
        'source_format': upload_workspace.source_format,
        'checksum': upload_workspace.get_content_checksum()
    }
