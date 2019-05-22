"""Application factory for file management app."""

#import logging

from flask import Flask
from celery import Celery

from arxiv import vault
from arxiv.base import Base
from arxiv.base.middleware import wrap
from arxiv.users import auth

from filemanager import celeryconfig
from filemanager.encode import ISO8601JSONEncoder
from filemanager.routes import upload_api
from filemanager.services import uploads



celery_app = Celery(__name__, results=celeryconfig.result_backend,
                    broker=celeryconfig.broker_url)


def create_web_app() -> Flask:
    """Initialize and configure the filemanager application."""
    app = Flask('filemanager')
    app.config.from_pyfile('config.py')
    app.json_encoder = ISO8601JSONEncoder

    # Initialize file management app
    uploads.init_app(app)

    Base(app)    # Gives us access to the base UI templates and resources.
    auth.Auth(app)
    app.register_blueprint(upload_api.blueprint)

    middleware = [auth.middleware.AuthMiddleware]
    if app.config['VAULT_ENABLED']:
        middleware.insert(0, vault.middleware.VaultMiddleware)
    wrap(app, middleware)

    celery_app.config_from_object(celeryconfig)
    celery_app.autodiscover_tasks(['filemanager'], related_name='tasks', force=True)
    celery_app.conf.task_default_queue = 'filemanager-worker'

    return app


def create_worker_app() -> Celery:
    """Initialize and configure the filemanager worker application."""
    app = Flask('filemanager')
    app.config.from_pyfile('config.py')

    uploads.init_app(app)

    celery_app.config_from_object(celeryconfig)
    celery_app.autodiscover_tasks(['filemanager'], related_name='tasks', force=True)
    celery_app.conf.task_default_queue = 'filemanager-worker'

    return app
