"""Helper script to initialize the Upload database and add a few rows."""

from datetime import datetime
import click
from filemanager.factory import create_web_app
from filemanager.services import database

from pytz import UTC

app = create_web_app()


@app.cli.command()
def populate_database():
    """Initialize the database."""
    with app.app_context():
        database.db.create_all()
        database.db.session.add(database.DBUpload())
        database.db.session.add(database.DBUpload())
        database.db.session.add(database.DBUpload())
        database.db.session.commit()


if __name__ == '__main__':
    populate_database()
