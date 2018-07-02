"""Provides routes for the external API."""

import json

from flask.json import jsonify
from flask import Blueprint, render_template, redirect, request, url_for
from arxiv.base import routes as base_routes
from filemanager import status, authorization

from filemanager.controllers import upload

blueprint = Blueprint('upload_api', __name__, url_prefix='/filemanager/api')


@blueprint.route('/status', methods=['GET'])
def service_status() -> tuple:
    """Health check endpoint."""
    return jsonify({'status': 'OK', 'total_uploads': 1}), status.HTTP_200_OK


@blueprint.route('/create', methods=['GET'])
# @authorization.scoped('read:upload')
def create_one() -> tuple:
    """Create upload workspace. Create and return unique upload identifier."""
    data, status_code, headers = upload.create_upload()
    return jsonify(data), status_code, headers


@blueprint.route('/upload/<int:upload_id>', methods=['GET', 'POST'])
@authorization.scoped('write:upload')
def upload_files(upload_id: int) -> tuple:
    """Upload individual files or compressed archive
    and add to upload package. Multiple uploads accepted."""

    if request.method == 'POST':
        if 'file' not in request.files:
            # TODO figure out error message
            return jsonify({'status': "FAILED"})
        file = request.files['file']

        if file.filename == '':
            # TODO figure out error message
            return jsonify({'status': "FAILED"})

        # Attempt to process upload
        data, status_code, headers = upload.upload(upload_id, file)

    if request.method == 'GET':
        data, status_code, headers = upload.upload_summary(upload_id)

    return jsonify(data), status_code, headers


@blueprint.route('/upload_status/<int:upload_id>', methods=['GET'])
@authorization.scoped('read:upload')
def upload_status(upload_id: int) -> tuple:
    """Retrieve status of upload processing task."""

    data, status_code, headers = upload.upload_status(upload_id)
    return jsonify(data), status_code, headers


# TODO: The requests below need to be evaluated and/or implemented

# Was debating about 'manifest' request but upload GET request
# seems to do same thing (though that one returns file information
# generated during file processing.
#
# Will upload GET always return list of files?
#
#@blueprint.route('/manifest/<int:upload_id>', methods=['GET'])
#@authorization.scoped('read:upload')
#def manifest(upload_id: int) -> tuple:
#    """Manifest of files contained in upload package."""
#    #data, status_code, headers = upload.generate_manifest(upload_id)
#    return jsonify(data), status_code, headers


# Or would 'download' be a better request? 'disseminate'?
@blueprint.route('/content/<int:upload_id>', methods=['GET'])
@authorization.scoped('read:upload')
def get_files(upload_id: int) -> tuple:
    """Return compressed archive containing files."""
    data, status_code, headers = upload.package_content(upload_id)
    return jsonify(data), status_code, headers


# This could be freeze instead of lock
@blueprint.route('/lock/<int:upload_id>', methods=['GET'])
@authorization.scoped('write:upload')
def lock(upload_id: int) -> tuple:
    """Lock submission (read-only mode) while other services are
    processing (major state transitions are occurring)."""
    data, status_code, headers = upload.upload_lock(upload_id)
    return jsonify(data), status_code, headers


# This could be thaw or release instead of unlock
@blueprint.route('/unlock/<int:upload_id>', methods=['GET'])
@authorization.scoped('write:upload')
def unlock(upload_id: int) -> tuple:
    """Unlock submission and enable write mode."""
    data, status_code, headers = upload.upload_unlock(upload_id)
    return jsonify(data), status_code, headers


# This could be remove or delete instead of release
@blueprint.route('/release/<int:upload_id>', methods=['GET'])
@authorization.scoped('write:upload')
def release(upload_id: int) -> tuple:
    """Client indicates they are finished with submission.
    File management service is free to remove submissions files,
    or schedule files for removal at later time."""
    data, status_code, headers = upload.upload_release(upload_id)
    return jsonify(data), status_code, headers


# This could be get_logs or retrieve_logs instead of logs
@blueprint.route('/logs/<int:upload_id>', methods=['GET'])
@authorization.scoped('write:upload')
def logs(upload_id: int) -> tuple:
    """Retreive log files related to submission. Indicates
    history or actions on submission package."""
    data, status_code, headers = upload.upload_logs(upload_id)
    return jsonify(data), status_code, headers
