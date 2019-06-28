"""Provides routes for the external API."""

from typing import Optional, Union, Any, Dict
import json
from http import HTTPStatus

from flask.json import jsonify
from flask import Blueprint, render_template, redirect, request, url_for, \
    Response, make_response, send_file
from werkzeug.exceptions import NotFound, Forbidden, Unauthorized, \
    InternalServerError, HTTPException, BadRequest

from arxiv.base import routes as base_routes
from arxiv.base import logging
from arxiv.users import domain as auth_domain
from arxiv.users.auth import scopes
from arxiv.users.auth.decorators import scoped

from ..services import database
from ..controllers import upload, status, service_log, source_log, lock, \
    release, package, files


logger = logging.getLogger(__name__)
blueprint = Blueprint('upload_api', __name__, url_prefix='/filemanager/api')


def is_owner(session: auth_domain.Session, upload_id: str,
             **kwargs: Any) -> bool:
    """User must be the upload owner, or an admin."""
    upload_obj = database.retrieve(upload_id)
    if upload_obj is None:
        return True

    if session.user:
        owner_id = str(request.session.user.user_id)
    elif session.client:
        owner_id = str(request.session.client.owner_id)
    else:
        raise Unauthorized('No user or client on authenticated session')

    return owner_id == str(database.retrieve(upload_id).owner_user_id)


@blueprint.route('/status', methods=['GET'])
def service_status() -> tuple:
    """
    Readiness endpoint.

    This route quickly exercises the downstream services/systems upon which
    the filemanager service depends. If all is well, returns 200 OK. Otherwise,
    returns 503 Service Unavailable.
    """
    response_data, code, headers = status.service_status()
    return jsonify(response_data), code, headers


@blueprint.route('/', methods=['POST'])
@scoped(scopes.WRITE_UPLOAD)
def new_upload() -> tuple:
    """
    Create workspace and upload files.

    Initial upload where workspace (upload_id) does not yet exist.

    This requests creates a new workspace. Upload package is processed normally.

    Client response include upload_id which is necessary for subsequent requests.
    """
    # Optional category/archive - this is required to accurately calculate
    # whether submission is oversize.
    archive_arg = request.form.get('archive', None)

    # is this optional??
    archive_arg = request.args.get('archive')

    # Required file payload
    file = request.files.get('file', None)

    if request.session.user:
        user_or_client = request.session.user
    elif request.session.client:
        user_or_client = request.session.client
    else:
        raise Unauthorized('No user or client on authenticated session')

    # Collect arguments and call main upload controller
    data, status_code, headers = upload.upload(None, file, archive_arg,
                                               user_or_client)
    
    response: Response = make_response(jsonify(data))
    response = _update_headers(jsonify(data), headers)
    response.status_code = status_code
    return response


@blueprint.route('<int:upload_id>', methods=['POST'])
@scoped(scopes.WRITE_UPLOAD, authorizer=is_owner)
def upload_files(upload_id: int) -> tuple:
    """
    Upload files to existing workspace.

    Upload individual files or compressed archive
    and add to existing upload workspace. Multiple uploads accepted.

    Parameters
    ----------
    upload_id : int
        Workspace identifier

    """
    archive_arg = request.form.get('archive')
    ancillary = request.form.get('ancillary', None) == 'True'
    file = request.files.get('file', None)
    # Attempt to process upload
    data, status_code, headers = upload.upload(upload_id, file, archive_arg,
                                               request.session.user,
                                               ancillary=ancillary)
    response: Response = make_response(jsonify(data))
    response = _update_headers(jsonify(data), headers)
    response.status_code = status_code
    return response


# Separated this out so that we can support auth granularity. -E
@blueprint.route('<int:upload_id>', methods=['GET'])
@scoped(scopes.READ_UPLOAD, authorizer=is_owner)
def get_upload_files(upload_id: int) -> tuple:
    """Upload summary.

    Parameters
    ----------
    upload_id : int
        Workspace identifier

    """
    data, status_code, headers = upload.upload_summary(upload_id)
    return jsonify(data), status_code, headers


@blueprint.route('<int:upload_id>/<path:public_file_path>', methods=['DELETE'])
@scoped(scopes.DELETE_UPLOAD_FILE, authorizer=is_owner)
def delete_file(upload_id: int, public_file_path: str) -> tuple:
    """
    Delete individual file.

    Parameters
    ----------
    upload_id : int
        Workspace identifier
    public_file_path : str
        Relative file path that uniquely identifies file to be removed.

    """
    data, status_code, headers = files.client_delete_file(upload_id,
                                                          public_file_path)
    return jsonify(data), status_code, headers

# File and workspace deletion

@blueprint.route('<int:upload_id>/delete_all', methods=['POST'])
@scoped(scopes.WRITE_UPLOAD, authorizer=is_owner)
def delete_all_files(upload_id: int) -> tuple:
    """
    Delete all files in specified workspace.

    Parameters
    ----------
    upload_id : int
        Workspace identifier

    """
    data, status_code, headers = files.client_delete_all_files(upload_id)
    return jsonify(data), status_code, headers


@blueprint.route('<int:upload_id>', methods=['DELETE'])
@scoped(scopes.DELETE_UPLOAD_WORKSPACE)
def workspace_delete(upload_id: int) -> tuple:
    """
    Delete the specified workspace.

    Parameters
    ----------
    upload_id : int
        Workspace identifier

    """
    data, status_code, headers = upload.delete_workspace(upload_id)
    return jsonify(data), status_code, headers


# Lock and unlock upload workspace

@blueprint.route('/<int:upload_id>/lock', methods=['POST'])
@scoped(scopes.WRITE_UPLOAD, authorizer=is_owner)
def lock_workspace(upload_id: int) -> tuple:
    """
    Lock submission workspace.

    Lock submission (read-only mode) while other services are
    processing (major state transitions are occurring).

    Parameters
    ----------
    upload_id : int
        Workspace identifier

    """
    data, status_code, headers = lock.upload_lock(upload_id)
    return jsonify(data), status_code, headers


# This could be thaw or release instead of unlock
@blueprint.route('/<int:upload_id>/unlock', methods=['POST'])
@scoped(scopes.WRITE_UPLOAD, authorizer=is_owner)
def unlock_workspace(upload_id: int) -> tuple:
    """Unlock submission workspace and allow updates."""
    data, status_code, headers = lock.upload_unlock(upload_id)
    return jsonify(data), status_code, headers


# This could be remove or delete instead of release
@blueprint.route('/<int:upload_id>/release', methods=['POST'])
@scoped(scopes.WRITE_UPLOAD, authorizer=is_owner)
def release_workspace(upload_id: int) -> tuple:
    """
    Client indicates they are finished with submission.

    File management service is free to remove submissions files,
    or schedule workspace for removal.
    """
    data, status_code, headers = release.upload_release(upload_id)
    return jsonify(data), status_code, headers


# This could be remove or delete instead of release
@blueprint.route('/<int:upload_id>/unrelease', methods=['POST'])
@scoped(scopes.WRITE_UPLOAD, authorizer=is_owner)
def unrelease_workspace(upload_id: int) -> tuple:
    """
    Client indicates they are NOT finished with submission.

    Workspace was previously release by client. Client has changed their
    mind and does not want to remove workspace.
    """
    data, status_code, headers = release.upload_unrelease(upload_id)
    return jsonify(data), status_code, headers


# Get content

@blueprint.route('/<int:upload_id>/content', methods=['HEAD'])
@scoped(scopes.READ_UPLOAD)
def check_upload_content_exists(upload_id: int) -> Response:
    """
    Verify that upload content exists.

    Returns an ``ETag`` header with the current source package checksum.
    """
    data, status_code, headers = package.check_upload_content_exists(upload_id)
    response = _update_headers(jsonify(data), headers)
    response.status_code = status_code
    return response


@blueprint.route('/<int:upload_id>/content', methods=['GET'])
@scoped(scopes.READ_UPLOAD)
def get_upload_content(upload_id: int) -> Response:
    """
    Get the upload content as a compressed tarball.

    Returns a stream with mimetype ``application/tar+gzip``, and an ``ETag``
    header with the current source package checksum.
    """
    logger.debug('Request for upload content: %s (%s)',
                 upload_id, type(upload_id))
    # Note: status_code is not used
    data, _, headers = package.get_upload_content(upload_id)
    response = send_file(data, mimetype="application/tar+gzip")
    response = _update_headers(response, headers)
    return response

@blueprint.route('/<int:upload_id>/<path:public_file_path>/content',
                 methods=['HEAD'])
@scoped(scopes.READ_UPLOAD)
def check_file_exists(upload_id: int, public_file_path: str) -> Response:
    """
    Verify specified file exists.

    Returns an ``ETag`` header with the current source file checksum.
    """
    data, status_code, headers = \
        files.check_upload_file_content_exists(upload_id, public_file_path)

    response = _update_headers(jsonify(data), headers)
    response.status_code = status_code
    return response


@blueprint.route('/<int:upload_id>/<path:public_file_path>/content', methods=['GET'])
@scoped(scopes.READ_UPLOAD)
def get_file_content(upload_id: int, public_file_path: str) -> Response:
    """
    Return content of specified file.

    :param upload_id:
    :param public_file_path:
    :return: File content.
    """
    # Note: status_code not used
    data, _, headers = \
        files.get_upload_file_content(upload_id, public_file_path)
    response = send_file(data, mimetype="application/*")
    response.set_etag(headers.get('ETag'))
    return response


# Get logs

@blueprint.route('/<int:upload_id>/log', methods=['HEAD'])
@scoped(scopes.READ_UPLOAD_LOGS)
def check_upload_source_log_exists(upload_id: int) -> Response:
    """
    Check that upload source log exists.

    Parameters
    ----------
    upload_id: int

    Returns
    -------
    Returns an ``ETag`` header with the current source package checksum.

    """
    data, status_code, headers = \
        source_log.check_upload_source_log_exists(upload_id)
    response = _update_headers(jsonify(data), headers)
    response.status_code = status_code
    return response


@blueprint.route('/<int:upload_id>/log', methods=['GET'])
@scoped(scopes.READ_UPLOAD_LOGS)
def get_upload_source_log(upload_id: int) -> Response:
    """
    Get upload workspace log.

    Get the upload source log for specified upload workspace. This provides details of all
    upload/deletion/errors/warnings for specified workspace.

    Parameters
    ----------
    upload_id : int

    Returns
    -------
    The source.log for specified upload workspace.

    """
    # Note: status_code not used
    data, _, headers = source_log.get_upload_source_log(upload_id)
    response = send_file(data, mimetype="application/tar+gzip")
    response.set_etag(headers.get('ETag'))
    return response


@blueprint.route('/log', methods=['HEAD'])
@scoped(scopes.READ_UPLOAD_SERVICE_LOGS)
def check_upload_service_log_exists() -> Response:
    """
    Check that upload source log exists.

    Returns
    -------
    Returns an ``ETag`` header with the current source package checksum.

    """
    data, status_code, headers = service_log.check_upload_service_log_exists()
    response = _update_headers(jsonify(data), headers)
    response.status_code = status_code
    return response


@blueprint.route('/log', methods=['GET'])
@scoped(scopes.READ_UPLOAD_SERVICE_LOGS)
def get_upload_service_log() -> Response:
    """
    Get upload file manager service log.

    Return the top level file manager service log that records high-level
    events/requests along with important errors/warnings.

    Does not include etails for a specific upload workspace.

    Returns
    -------
    The log file for upload file manager service.

    """
    # Note: status_code not used
    data, _, headers = service_log.get_upload_service_log()
    response = send_file(data, mimetype="application/tar+gzip")
    response = _update_headers(response, headers)
    # response.set_etag(headers.get('ETag'))
    return response

# Exception handling


@blueprint.errorhandler(NotFound)
@blueprint.errorhandler(InternalServerError)
@blueprint.errorhandler(Forbidden)
@blueprint.errorhandler(Unauthorized)
@blueprint.errorhandler(BadRequest)
@blueprint.errorhandler(NotImplementedError)
def handle_exception(error: HTTPException) -> Response:
    """
    JSON-ify the error response.

    This works just like the handlers in zero.routes.ui, but instead of
    rendering a template we are JSON-ifying the response. Note that we are
    registering the same error handler for several different exceptions, since
    we aren't doing anything that is specific to a particular exception.
    """
    content = jsonify({'reason': error.description})

    # Each Werkzeug HTTP exception has a class attribute called ``code``; we
    # can use that to set the status code on the response.
    response = make_response(content, error.code)
    return response


def _update_headers(response: Response, headers: Dict[str, Any]) -> Response:
    for key, value in headers.items():
        if key in response.headers:     # Avoid duplicate headers.
            response.headers.remove(key)
        response.headers.add(key, value)
    return response
