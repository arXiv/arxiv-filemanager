"""Web Server Gateway Interface entry-point."""

import os
from typing import Optional

from flask import Flask

from filemanager.factory import create_web_app


__flask_app__: Optional[Flask] = None


def application(environ, start_response):
    """WSGI application factory."""
    global __flask_app__
    for key, value in environ.items():
        if key == 'SERVER_NAME':    # This will only confuse Flask.
            continue
        os.environ[key] = str(value)
        if __flask_app__ is not None:
            __flask_app__.config[key] = value
    __flask_app__ = create_web_app()
    return __flask_app__(environ, start_response)
