"""Helper script to initialize the Upload database and add a few rows."""

from datetime import datetime
import click
from filemanager.factory import create_web_app
from filemanager.services import database

app = create_web_app()
app.app_context().push()


@app.cli.command()
def populate_database():
    """Initialize the search index."""
    database.db.create_all()
    database.db.session.add(database.DBUpload(name='The first upload', created_datetime=datetime.now(UTC),submission_id='1234567'))
    database.db.session.add(database.DBUpload(name='The second upload', created_datetime=datetime.now(UTC),submission_id='1234568'))
    database.db.session.add(database.DBUpload(name='The third upload', created_datetime=datetime.now(UTC),submission_id='1234569'))
    database.db.session.commit()


if __name__ == '__main__':
    populate_database()
