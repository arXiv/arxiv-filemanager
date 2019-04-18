"""Web Server Gateway Interface entry-point."""

from filemanager.factory import create_web_app
import os


__flask_app__ = create_web_app()


def application(environ, start_response):
    """WSGI application factory."""
    for key, value in environ.items():
        if key == 'SERVER_NAME':    # This will only confuse Flask.
            continue
        os.environ[key] = str(value)
    return __flask_app__(environ, start_response)
