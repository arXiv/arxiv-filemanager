"""Provides application for development purposes."""

from filemanager.factory import create_web_app
from filemanager.services import uploads

app = create_web_app()

uploads.db.create_all()