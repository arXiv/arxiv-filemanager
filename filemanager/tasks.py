"""Asynchronous tasks. NOT IMPLEMENTED AT MOMENT. MAY GO AWAY."""

# TODO: This is not hooked up yet

import time
from datetime import datetime
from typing import Optional, Dict, Any, Tuple, Callable
from celery import shared_task
from celery.result import AsyncResult
from celery.signals import after_task_publish
from celery import current_app

from werkzeug.datastructures import FileStorage

# Upload tasks

from filemanager.services import uploads
from filemanager.domain   import Upload
from filemanager.process  import upload
import filemanager

@shared_task
def sanitize_upload(upload_id: int, file: FileStorage, with_sleep: int = 15) -> Dict[str, Any]:
    """
    Perform some expen$ive mutations on a :class:`.Thing`.

    Parameters
    ----------
    upload_id : int

    file : FileStorage
        Upload file/archive to be processed.

    Returns
    -------
    Still TBD

    """
    print(f'Task: Upload task for {upload_id}')
    upload: Optional[Upload] = uploads.retrieve(upload_id)
    if upload is None:
        # Revisit how to handle error
        raise RuntimeError('No such thing! %s' % upload_id)

    start_datetime = datetime.now()
    #uploadObj = filemanager.process.Upload.process_upload(upload)
    uploadObj = filemanager.process.upload.Upload(upload_id)

    # TODO: Remember to get rid of this sleep statement
    time.sleep(with_sleep)

    # Process upload
    uploadObj.process_upload(file)

    completion_datetime = datetime.now()

    # Colect information we want to retain
    upload.lastupload_logs = str(uploadObj.get_warnings())
    upload.lastupload_start_datetime = start_datetime
    upload.lastupload_completion_datetime = completion_datetime
    # Don't forget about storing file list
    upload.state = 'Active'

    # Save to DB
    uploads.update(upload)

    print(f'Task: Completed upload task for {upload_id}')

    return {'upload_id': upload_id, 'result': len(upload.name)}


def check_sanitize_status(task_id: str) -> Tuple[str, Any]:
    """
    Check the status of a mutation task.

    Parameters
    ----------
    task_id : str
        upload task ID.

    Returns
    -------
    str
        Task status.
    result
        Result from task metadata.
    """
    if not isinstance(task_id, str):
        raise ValueError('task_id must be string, not %s' % type(task_id))
    task = AsyncResult(task_id)
    if task.status in ['SUCCESS', 'FAILED']:
        result = task.result
    else:
        result = None
    return task.status, result

def check_upload_status(task_id: str) -> Tuple[str, Any]:
    """
    Check the status of a upload task.

    Parameters
    ----------
    task_id : str
        upload task ID.

    Returns
    -------
    str
        Status.

    """
    if not isinstance(task_id, str):
        raise ValueError('task_id must be string, not %s' % type(task_id))
    task = AsyncResult(task_id)
    if task.status in ['SUCCESS', 'FAILED']:
        result = task.result
    else:
        result = None
    return task.status, result

@after_task_publish.connect
def update_sent_state(sender: Optional[Callable] = None,
                      headers: Optional[dict] = None, body: Any = None,
                      **kwargs: Any) -> None:
    """Set state to SENT, so that we can tell whether a task exists."""
    task = current_app.tasks.get(sender)
    backend = task.backend if task else current_app.backend
    if headers is not None:
        backend.store_result(headers['id'], None, "SENT")
