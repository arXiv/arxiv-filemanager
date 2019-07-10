"""Application factory for file management app."""

from flask import Flask, jsonify, Response
from werkzeug.exceptions import HTTPException, Forbidden, Unauthorized, \
    BadRequest, MethodNotAllowed, InternalServerError, NotFound

from arxiv import vault
from arxiv.base import Base
from arxiv.base.middleware import wrap

from filemanager import celeryconfig
from filemanager.routes import upload_api
from filemanager.services import database

from arxiv.users import auth
from arxiv.util.serialize import ISO8601JSONEncoder

from werkzeug.contrib.profiler import ProfilerMiddleware


def create_web_app() -> Flask:
    """Initialize and configure the filemanager application."""
    app = Flask('filemanager')
    app.config.from_pyfile('config.py')
    app.json_encoder = ISO8601JSONEncoder

    # This is here for profiling, if needed.
    # app.config['PROFILE'] = True
    # app.wsgi_app = ProfilerMiddleware(app.wsgi_app, restrictions=[30],
    #                                   sort_by=('cumtime', 'calls'))

    # Initialize file management app
    database.init_app(app)

    Base(app)    # Gives us access to the base UI templates and resources.
    auth.Auth(app)
    app.register_blueprint(upload_api.blueprint)

    middleware = [auth.middleware.AuthMiddleware]
    if app.config['VAULT_ENABLED']:
        middleware.insert(0, vault.middleware.VaultMiddleware)
    wrap(app, middleware)

    if app.config['VAULT_ENABLED']:
        app.middlewares['VaultMiddleware'].update_secrets({})

    register_error_handlers(app)
    return app


def register_error_handlers(app: Flask) -> None:
    """Register error handlers for the Flask app."""
    app.errorhandler(Forbidden)(jsonify_exception)
    app.errorhandler(Unauthorized)(jsonify_exception)
    app.errorhandler(BadRequest)(jsonify_exception)
    app.errorhandler(InternalServerError)(jsonify_exception)
    app.errorhandler(NotFound)(jsonify_exception)
    app.errorhandler(MethodNotAllowed)(jsonify_exception)


def jsonify_exception(error: HTTPException) -> Response:
    """Render exceptions as JSON."""
    exc_resp = error.get_response()
    response: Response = jsonify(reason=error.description)
    response.status_code = exc_resp.status_code
    return response
