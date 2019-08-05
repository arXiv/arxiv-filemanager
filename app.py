"""Provides application for development purposes."""

from filemanager.factory import create_web_app
from filemanager.services import database

app = create_web_app()

with app.app_context():
    database.db.create_all()
