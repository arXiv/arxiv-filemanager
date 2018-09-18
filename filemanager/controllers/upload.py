"""Handles all upload-related requests."""

from typing import Tuple, Optional
from datetime import datetime
from pytz import UTC
import json
import logging

from werkzeug.exceptions import NotFound, BadRequest, InternalServerError, \
    NotImplemented, SecurityError, Forbidden

from werkzeug.datastructures import FileStorage
from flask.json import jsonify

from arxiv import status
from arxiv.users import domain as auth_domain

import filemanager
from filemanager.shared import url_for

from filemanager.domain import Upload
from filemanager.services import uploads

from filemanager.arxiv.file import File

# Temporary logging at service level - just to get something in place to build on

logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger(__name__)

file_handler = logging.FileHandler('upload.log', 'a')
# Default arXiv log format.
# fmt = ("application %(asctime)s - %(name)s - %(requestid)s"
#          " - [arxiv:%(paperid)s] - %(levelname)s: \"%(message)s\"")
datefmt = '%d/%b/%Y:%H:%M:%S %z'  # Used to format asctime.
formatter = logging.Formatter('%(asctime)s %(message)s', '%d/%b/%Y:%H:%M:%S %z')
file_handler.setFormatter(formatter)
logger.handlers = []
logger.addHandler(file_handler)
logger.setLevel(logging.DEBUG)
logger.propagate = False

# End logging configuration

# exceptions
UPLOAD_MISSING_FILE = 'missing file/archive payload'
UPLOAD_MISSING_FILENAME = 'file argument missing filename or file not selected'
# UPLOAD_FILE_EMPTY = {'file payload is zero length'}

UPLOAD_NOT_FOUND = 'upload workspace not found'
UPLOAD_DB_ERROR = 'unable to create/insert new upload workspace into database'
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
REQUUTC_NOT_IMPLEMENTED = {'request not implemented'}

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


def delete_workspace(upload_id: int) -> Response:
    """Delete workspace.

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
        else:

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

            upload_workspace = filemanager.process.upload.Upload(upload_id)

            # Call routine that will do the actual work
            upload_workspace.remove_workspace()

            # update database
            if upload_db_data.state != Upload.RELEASED:
                logger.info("%s: Workspace currently in '%s' state.", upload_id, upload_db_data.state)

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
    status_code = status.HTTP_200_OK
    return response_data, status_code, {}


def client_delete_file(upload_id: str, public_file_path: str) -> Response:
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
    logger.info("%s: Delete file '%s'.", upload_id, public_file_path)

    try:
        # Make sure we have an upload_db_data to work with
        upload_db_data: Optional[Upload] = uploads.retrieve(upload_id)

        if upload_db_data is None:
            # Invalid workspace identifier
            raise NotFound(UPLOAD_NOT_FOUND)
        elif upload_db_data.state != Upload.ACTIVE:
            # Do we log anything for these requests
            raise Forbidden(UPLOAD_NOT_ACTIVE)
        elif upload_db_data.lock == Upload.LOCKED:
            raise Forbidden(UPLOAD_WORKSPACE_LOCKED)
        else:

            # Create Upload object
            upload_workspace = filemanager.process.upload.Upload(upload_id)

            # Call routine that will do the actual work
            upload_workspace.client_remove_file(public_file_path)


    except IOError:
        logger.error("%s: Delete file request failed ", upload_db_data.upload_id)
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
        logger.info("Unknown error in delete file. "
                    " Add except clauses for '%s'. DO IT NOW!", ue)
        raise InternalServerError(UPLOAD_UNKNOWN_ERROR)

    response_data = {'reason': UPLOAD_DELETED_FILE}  # Get rid of pylint error
    status_code = status.HTTP_204_NO_CONTENT
    return response_data, status_code, {}


def client_delete_all_files(upload_id: str) -> Response:
    """Delete all files uploaded by client from specified workspace.

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

    logger.info("%s: Deleting all uploaded files from this workspace.", upload_id)

    try:
        # Make sure we have an upload_db_data to work with
        upload_db_data: Optional[Upload] = uploads.retrieve(upload_id)

        if upload_db_data is None:
            # Invalid workspace identifier
            raise NotFound(UPLOAD_NOT_FOUND)
        elif upload_db_data.state != Upload.ACTIVE:
            # Do we log anything for these requests
            raise Forbidden(UPLOAD_NOT_ACTIVE)
        elif upload_db_data.lock == Upload.LOCKED:
            raise Forbidden(UPLOAD_WORKSPACE_LOCKED)
        else:

            # Create Upload object
            upload_workspace = filemanager.process.upload.Upload(upload_id)

            upload_workspace.client_remove_all_files()


    except IOError:
        logger.error("%s: Delete all files request failed ", upload_db_data.upload_id)
        raise InternalServerError(CANT_DELETE_ALL_FILES)
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

    response_data = {'reason': UPLOAD_DELETED_ALL_FILES}  # Get rid of pylint error
    status_code = status.HTTP_204_NO_CONTENT
    return response_data, status_code, {}


def upload(upload_id: int, file: FileStorage, archive: str,
           user: auth_domain.User, ancillary: bool = False) -> Response:
    """Upload individual files or compressed archive. Unpack and add
    files to upload_db_data workspace.

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

    # TODO: Hook up async processing (celery/redis) - doesn't work now
    # TODO: Will likely delete this code if processing time is reasonable
    # print(f'Controller: Schedule upload_db_data task for {upload_id}')
    #
    # result = sanitize_upload.delay(upload_id, file)
    #
    # headers = {'Location': url_for('upload_api.upload_status',
    #                              task_id=result.task_id)}
    # return ACCEPTED, status.HTTP_202_ACCEPTED, headers
    # End delete

    # Check arguments for basic qualities like existing and such.

    # File argument is required to exist and have a name associated with it.
    # It is standard practice that if user fails to select file the filename is null.
    if file is None:
        # Crash and burn...not quite...do we need info about client?
        logger.error(f'Upload request is missing file/archive payload.')
        raise BadRequest(UPLOAD_MISSING_FILE)

    if file.filename == '':
        # Client needs to select file, or provide name to upload payload
        logger.error(f'Upload file is missing filename. File to upload may not be selected.')
        raise BadRequest(UPLOAD_MISSING_FILENAME)

    # What about archive argument.
    if archive is None:
        # TODO: Discussion about how to treat omission of archive argument.
        # Is this an HTTP exception? Oversize limits are configured per archive.
        # Or is this a warning/error returned in upload summary?
        #
        # Most submissions can get by with default size limitations so we'll add a warning
        # message for the upload (this will appear on upload page and get logged). This
        # warning will get generated in process/upload.py and not here.
        logger.error("Upload 'archive' not specified. Oversize calculation "
                     "will use default values.")

    # If this is a new upload then we need to create a workspace and add to database.
    if upload_id is None:
        try:
            logger.info("Create new workspace: Upload request: "
                        "file='%s' archive='%s'", file.filename, archive)
            user_id = user.user_id

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
            logger.info("Unknown error in upload for new workspace. "
                        " Add except clauses for '%s'. DO IT NOW!", ue)
            raise InternalServerError(UPLOAD_UNKNOWN_ERROR)

    # At this point we expect upload to exist in system
    try:

        upload_db_data: Optional[Upload] = uploads.retrieve(upload_id)

        if upload_db_data is None:
            # Invalid workspace identifier
            raise NotFound(UPLOAD_NOT_FOUND)
        elif upload_db_data.state != Upload.ACTIVE:
            # Do we log anything for these requests
            logger.debug('Forbidden, workspace not active')
            raise Forbidden(UPLOAD_NOT_ACTIVE)
        elif upload_db_data.lock == Upload.LOCKED:
            logger.debug('Forbidden, workspace locked')
            raise Forbidden(UPLOAD_WORKSPACE_LOCKED)
        else:
            # Now handle upload package - process file or gzipped tar archive

            # NOTE: This will need to be migrated to task.py using Celery at
            #       some point in future. Depends in time it takes to process
            #       uploads.retrieve
            logger.info("%s: Upload files to existing "
                        "workspace: file='%s'", upload_db_data.upload_id, file.filename)

            # Keep track of how long processing upload_db_data takes
            start_datetime = datetime.now(UTC)

            # Create Upload object
            upload_workspace = filemanager.process.upload.Upload(upload_id)

            # Process upload_db_data
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

            logger.info("%s: Processed upload. "
                        "Saved to DB. Preparing upload summary.", upload_db_data.upload_id)

            # Do we want affirmative log messages after processing each request
            # or maybe just report errors like:
            #    logger.info(f"{upload_db_data.upload_id}: Finished processing ...")

            # Upload action itself has very simple response
            headers = {'Location': url_for('upload_api.upload_files',
                                           upload_id=upload_db_data.upload_id)}

            status_code = status.HTTP_201_CREATED

            response_data = {
                'upload_id': upload_db_data.upload_id,
                'created_datetime': upload_db_data.created_datetime,
                'modified_datetime': upload_db_data.modified_datetime,
                'start_datetime': upload_db_data.lastupload_start_datetime,
                'completion_datetime': upload_db_data.lastupload_completion_datetime,
                'files': json.loads(upload_db_data.lastupload_file_summary),
                'errors': json.loads(upload_db_data.lastupload_logs),
                'upload_status': upload_db_data.lastupload_upload_status,
                'workspace_state': upload_db_data.state,
                'lock_state': upload_db_data.lock
            }
            logger.info("%s: Generating upload summary.", upload_db_data.upload_id)
            return response_data, status_code, headers

    except IOError as e:
        logger.error("%s: File upload_db_data request failed "
                     "for file='%s'", upload_db_data.upload_id, file.filename)
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
        logger.info("Unknown error with existing workspace."
                    " Add except clauses for '%s'. DO IT NOW!", ue)
        raise InternalServerError(UPLOAD_UNKNOWN_ERROR)


def upload_summary(upload_id: int) -> Response:
    """Provide summary of important upload workspace details.

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
            status_code = status.HTTP_404_NOT_FOUND
            response_data = UPLOAD_NOT_FOUND
            raise NotFound(UPLOAD_NOT_FOUND)
        else:
            logger.info("%s: Upload summary request.", upload_db_data.upload_id)

            # Create Upload object
            upload_workspace = filemanager.process.upload.Upload(upload_id)
            file_list = upload_workspace.create_file_list()

            details_list = []
            for fileObj in file_list:
                print(type(fileObj.modified_datetime))
                file_details = {
                    'name': fileObj.name,
                    'public_filepath': fileObj.public_filepath,
                    'size': fileObj.size,
                    'type': fileObj.type_string,
                    'modified_datetime': fileObj.modified_datetime
                }
                if not fileObj.removed:
                    details_list.append(file_details)


            status_code = status.HTTP_200_OK
            response_data = {
                'upload_id': upload_db_data.upload_id,
                'created_datetime': upload_db_data.created_datetime,
                'modified_datetime': upload_db_data.modified_datetime,
                'start_datetime': upload_db_data.lastupload_start_datetime,
                'completion_datetime': upload_db_data.lastupload_completion_datetime,
                'files': details_list,
                'errors': [],
                'upload_status': upload_db_data.lastupload_upload_status,
                'workspace_state': upload_db_data.state,
                'lock_state': upload_db_data.lock
            }
            logger.info("%s: Upload summary request.", upload_db_data.upload_id)

    except IOError:
        # response_data = ERROR_RETRIEVING_UPLOAD
        # status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        raise InternalServerError(ERROR_RETRIEVING_UPLOAD)
    except (TypeError, ValueError):
        logger.info("Error updating database.")
        raise InternalServerError(UPLOAD_DB_ERROR)
    except NotFound as nf:
        logger.info("%s: UploadSummary: '%s'", upload_id, nf)
        raise
    except Exception as ue:
        logger.info("Unknown error with existing workspace."
                    " Add except clauses for '%s'. DO IT NOW!", ue)
        raise InternalServerError(UPLOAD_UNKNOWN_ERROR)

    return response_data, status_code, {}


# TODO: How do we keep submitter from updating workspace while admin
# TODO: is working on it? These locks currently mean no changes are allowed.
# TODO: Is there another flavor of lock? Administrative lock? Or do admin
# TODO: and submitter coordinate on changes to upload workspace.

def upload_lock(upload_id: int) -> Response:
    """Lock upload workspace. Prohibit all user operations on upload.

    Lock may indicate process that might produce unknown results if
    workspace is updated. Compile and publish are examples.

    Admins may unlock upload."""

    logger.info("%s: Lock upload workspace.", upload_id)

    try:
        # Make sure we have an upload_db_data to work with
        upload_db_data: Optional[Upload] = uploads.retrieve(upload_id)

        if upload_db_data is None:
            # Invalid workspace identifier
            raise NotFound(UPLOAD_NOT_FOUND)
        else:

            # Lock upload workspace
            # update database
            if upload_db_data.lock == Upload.LOCKED:
                logger.info("%s: Lock: Workspace is already locked.", upload_id)
            else:
                upload_db_data.lock = Upload.LOCKED

                # Store in DB
                uploads.update(upload_db_data)

            response_data = {'reason': UPLOAD_LOCKED_WORKSPACE}  # Get rid of pylint error
            status_code = status.HTTP_200_OK

    except IOError:
        logger.error("%s: Lock workspace request failed ", upload_db_data.upload_id)
        raise InternalServerError(CANT_DELETE_FILE)
    except NotFound as nf:
        logger.info("%s: Lock: %s", upload_id, nf)
        raise
    except Exception as ue:
        logger.info("Unknown error lock workspace. "
                    " Add except clauses for '%s'. DO IT NOW!", ue)
        raise InternalServerError(UPLOAD_UNKNOWN_ERROR)

    return response_data, status_code, {}


def upload_unlock(upload_id: int) -> Response:
    """Unlock upload workspace."""
    # response_data = ERROR_REQUUTC_NOT_IMPLEMENTED
    # status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    logger.info("%s: Unlock upload workspace.", upload_id)

    try:
        # Make sure we have an upload_db_data to work with
        upload_db_data: Optional[Upload] = uploads.retrieve(upload_id)

        if upload_db_data is None:
            # Invalid workspace identifier
            raise NotFound(UPLOAD_NOT_FOUND)
        else:

            # Lock upload workspace
            # update database
            if upload_db_data.lock == Upload.UNLOCKED:
                logger.info("%s: Unlock: Workspace is already unlocked.", upload_id)
            else:
                upload_db_data.lock = Upload.UNLOCKED

                # Store in DB
                uploads.update(upload_db_data)

            response_data = {'reason': UPLOAD_UNLOCKED_WORKSPACE}  # Get rid of pylint error
            status_code = status.HTTP_200_OK

    except IOError:
        logger.error("%s: Unlock workspace request failed ", upload_db_data.upload_id)
        raise InternalServerError(CANT_DELETE_FILE)
    except NotFound as nf:
        logger.info("%s: Unlock workspace: %s", upload_id, nf)
        raise
    except Exception as ue:
        logger.info("Unknown error in unlock workspace. "
                    " Add except clauses for '%s'. DO IT NOW!", ue)
        raise InternalServerError(UPLOAD_UNKNOWN_ERROR)

    return response_data, status_code, {}


def upload_release(upload_id: int) -> Response:
    """Release inidcates owner is done with upload workspace.

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
        # Make sure we have an upload_db_data to work with
        upload_db_data: Optional[Upload] = uploads.retrieve(upload_id)

        if upload_db_data is None:
            # Invalid workspace identifier
            raise NotFound(UPLOAD_NOT_FOUND)
        else:

            # Release upload workspace
            # update database

            if upload_db_data.state == Upload.RELEASED:
                logger.info("%s: Release: Workspace has already been released.", upload_id)
                response_data = {'reason': UPLOAD_RELEASED_WORKSPACE}  # Should this be an error?
                status_code = status.HTTP_200_OK
            elif upload_db_data.state == Upload.DELETED:
                logger.info("%s: Release failed: Workspace has been deleted.", upload_id)
                # response_data = {'reason': UPLOAD_WORKSPACE_ALREADY_DELETED}
                # status_code = status.HTTP_200_OK
                raise NotFound(UPLOAD_WORKSPACE_ALREADY_DELETED)
            elif upload_db_data.state == Upload.ACTIVE:
                logger.info("%s: Release upload workspace.", upload_id)

                upload_db_data.state = Upload.RELEASED

                # Store in DB
                uploads.update(upload_db_data)

                response_data = {'reason': UPLOAD_RELEASED_WORKSPACE}  # Get rid of pylint error
                status_code = status.HTTP_200_OK

    except IOError:
        logger.error("%s: Release workspace request failed.", upload_db_data.upload_id)
        raise InternalServerError(CANT_RELEASE_WORKSPACE)
    except NotFound as nf:
        logger.info(f"%s: Release workspace: %s", upload_id, nf)
        raise
    except Exception as ue:
        logger.info("Unknown error in release workspace. "
                    " Add except clauses for '%s'. DO IT NOW!", ue)
        raise InternalServerError(UPLOAD_UNKNOWN_ERROR)

    return response_data, status_code, {}


def upload_unrelease(upload_id: int) -> Response:
    """Unrelease returns released workspace to active state.

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
        upload_db_data: Optional[Upload] = uploads.retrieve(upload_id)

        if upload_db_data is None:
            # Invalid workspace identifier
            raise NotFound(UPLOAD_NOT_FOUND)
        else:

            # Unrelease upload workspace
            # update database
            if upload_db_data.state == Upload.DELETED:
                # logger.info(f"{upload_id}: Unrelease Failed: Workspace has been deleted.")
                # response_data = {'reason': UPLOAD_WORKSPACE_ALREADY_DELETED}
                # tatus_code = status.HTTP_200_OK
                raise NotFound(UPLOAD_WORKSPACE_ALREADY_DELETED)
            elif upload_db_data.state == Upload.ACTIVE:
                logger.info("%s: Unrelease: Workspace is already active.", upload_id)
                response_data = {'reason': UPLOAD_UNRELEASED_WORKSPACE}  # Should this be an error?
                status_code = status.HTTP_200_OK
            elif upload_db_data.state == Upload.RELEASED:
                logger.info("%s: Unrelease upload workspace.", upload_id)

                upload_db_data.state = Upload.ACTIVE

                # Store in DB
                uploads.update(upload_db_data)

                response_data = {'reason': UPLOAD_UNRELEASED_WORKSPACE}
                status_code = status.HTTP_200_OK

    except IOError:
        logger.error("%s: Unrelease workspace request failed.", upload_db_data.upload_id)
        raise InternalServerError(CANT_DELETE_FILE)
    except NotFound as nf:
        logger.info("%s: Unrelease workspace: '%s'", upload_id, nf)
        raise
    except Exception as ue:
        logger.info("Unknown error in unrelease workspace. "
                    " Add except clauses for '%s'. DO IT NOW!", ue)
        raise InternalServerError(UPLOAD_UNKNOWN_ERROR)

    return response_data, status_code, {}


def get_upload_content(upload_id: int) -> Response:
    """Package up files for downloading as a compressed gzipped tar file."""
    upload_db_data: Optional[Upload] = uploads.retrieve(upload_id)

    if upload_db_data is None:
        raise NotFound(UPLOAD_NOT_FOUND)
    upload_workspace = filemanager.process.upload.Upload(upload_id)
    checksum = upload_workspace.content_checksum()
    filepointer = upload_workspace.get_content()
    headers = {
        "Content-disposition": f"filename={filepointer.name}",
        'ETag': checksum
    }
    return filepointer, status.HTTP_200_OK, headers


def check_upload_content_exists(upload_id: int) -> Response:
    """Verify that the package content exists/is available."""
    upload_db_data: Optional[Upload] = uploads.retrieve(upload_id)

    if upload_db_data is None:
        raise NotFound(UPLOAD_NOT_FOUND)

    logger.info("%s: Upload content summary request.", upload_id)
    upload_workspace = filemanager.process.upload.Upload(upload_id)
    checksum = upload_workspace.content_checksum()
    return {}, status.HTTP_200_OK, {'ETag': checksum}


# TBI

def upload_logs(upload_id: int) -> Response:
    """Return logs. Are we talking logs in database or full
    source logs. Need to implement logs first!!! """
    # response_data = ERROR_REQUUTC_NOT_IMPLEMENTED
    # status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    if 1 + upload_id:
        print(upload_id)  # make pylint happy - increase my score!
        raise NotImplementedError(REQUUTC_NOT_IMPLEMENTED)
    response_data = ACCEPTED
    status_code = status.HTTP_202_ACCEPTED
    return response_data, status_code, {}
