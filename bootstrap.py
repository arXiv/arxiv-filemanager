"""Bootstrap the file manager service."""

import time
from arxiv.base import logging
from filemanager.factory import create_web_app
from filemanager.services import database

logger = logging.getLogger(__name__)


if __name__ == '__main__':
    app = create_web_app()
    logger.info('New app with database URI: %s',
                app.config['SQLALCHEMY_DATABASE_URI'])
    with app.app_context():
        session = database.db.session
        wait = 2
        while True:
            try:
                session.execute('SELECT 1')
                break
            except Exception as e:
                logger.info(e)
                logger.info(f'...waiting {wait} seconds...')
                time.sleep(wait)
                wait *= 2
        logger.info('Initializing database')
        database.db.create_all()
        exit(0)
