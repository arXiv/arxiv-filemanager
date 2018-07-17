"""Helper script to initialize the Upload database and add a few rows."""

from datetime import datetime
import click
from filemanager.factory import create_web_app
from filemanager.services import uploads

app = create_web_app()
app.app_context().push()


@app.cli.command()
def populate_database():
    """Initialize the search index."""
    uploads.db.create_all()
    uploads.db.session.add(uploads.DBUpload(name='The first upload', created_datetime=datetime.now(),submission_id='1234567'))
    uploads.db.session.add(uploads.DBUpload(name='The second upload', created_datetime=datetime.now(),submission_id='1234568'))
    uploads.db.session.add(uploads.DBUpload(name='The third upload', created_datetime=datetime.now(),submission_id='1234569'))
    uploads.db.session.commit()


if __name__ == '__main__':
    populate_database()
