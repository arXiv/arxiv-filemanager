"""Bootstrap the file manager service."""

import time
from arxiv.base import logging
from filemanager.factory import create_web_app
from filemanager.services import uploads

logger = logging.getLogger(__name__)


if __name__ == '__main__':
    app = create_web_app()
    with app.app_context():
        session = uploads.db.session
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
        uploads.db.create_all()
        exit(0)
