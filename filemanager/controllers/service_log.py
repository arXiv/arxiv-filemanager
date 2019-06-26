"""Temporary logging at service level to get something in place to build on."""

import os
import io
import logging
from http import HTTPStatus as status
from typing import Optional, Tuple
from datetime import datetime
from hashlib import md5
from base64 import urlsafe_b64encode

from arxiv.base.globals import get_application_config

Response = Tuple[Optional[dict], status, dict]

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
formatter = logging.Formatter('%(asctime)s %(message)s', 
                              '%d/%b/%Y:%H:%M:%S %z')
file_handler.setFormatter(formatter)
# logger.handlers = []
logger.addHandler(file_handler)
logger.setLevel(logging.DEBUG)
logger.propagate = True

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
