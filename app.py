"""Provides application for development purposes."""

from filemanager.factory import create_web_app
from filemanager.services import uploads

app = create_web_app()

app.app_context().push()

uploads.db.create_all()