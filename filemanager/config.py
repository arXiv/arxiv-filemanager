"""Flask configuration."""

import os
import warnings
import tempfile
from arxiv.util.serialize import dumps, loads

VERSION = '0.2'
APP_VERSION = VERSION

NAMESPACE = os.environ.get('NAMESPACE')
"""Namespace in which this service is deployed; to qualify keys for secrets."""

SECRET_KEY = os.environ.get('SECRET_KEY', 'asdf1234')
SERVER_NAME = os.environ.get('ARXIV_FILE_MANAGMENT')

AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID', 'nope')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', 'nope')
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')

LOGFILE = os.environ.get('LOGFILE')
LOGLEVEL = os.environ.get('LOGLEVEL', 20)

SQLALCHEMY_DATABASE_URI = os.environ.get(
    'FILE_MANAGEMENT_SQLALCHEMY_DATABASE_URI',
    'sqlite:///filemanager.db'
)
SQLALCHEMY_TRACK_MODIFICATIONS = False

if 'mysql' in SQLALCHEMY_DATABASE_URI:
    SQLALCHEMY_ENGINE_OPTIONS = {'json_serializer': dumps,
                                 'json_deserializer': loads}

JWT_SECRET = os.environ.get('JWT_SECRET', 'foosecret')

ARXIV_TWITTER_URL = os.environ.get('ARXIV_TWITTER_URL',
                                   'https://twitter.com/arxiv')
ARXIV_SEARCH_BOX_URL = os.environ.get('SEARCH_BOX_URL', '/search')
ARXIV_SEARCH_ADVANCED_URL = os.environ.get('ARXIV_SEARCH_ADVANCED_URL',
                                           '/search/advanced')
ARXIV_ACCOUNT_URL = os.environ.get('ACCOUNT_URL', '/user')
ARXIV_LOGIN_URL = os.environ.get('LOGIN_URL', '/user/login')
ARXIV_LOGOUT_URL = os.environ.get('LOGOUT_URL', '/user/logout')
ARXIV_HOME_URL = os.environ.get('ARXIV_HOME_URL', 'https://arxiv.org')
ARXIV_HELP_URL = os.environ.get('ARXIV_HELP_URL', '/help')
ARXIV_CONTACT_URL = os.environ.get('ARXIV_CONTACT_URL', '/help/contact')
ARXIV_BLOG_URL = os.environ.get('ARXIV_BLOG_URL',
                                "https://blogs.cornell.edu/arxiv/")
ARXIV_WIKI_URL = os.environ.get(
    'ARXIV_WIKI_URL',
    "https://confluence.cornell.edu/display/arxivpub/arXiv+Public+Wiki"
)
ARXIV_ACCESSIBILITY_URL = os.environ.get(
    'ARXIV_ACCESSIBILITY_URL',
    "mailto:web-accessibility@cornell.edu"
)
ARXIV_LIBRARY_URL = os.environ.get('ARXIV_LIBRARY_URL',
                                   'https://library.cornell.edu')

# Need to set maximum allowed upload
MAX_CONTENT_LENGTH = 16 * 1024 * 1024

UPLOAD_BASE_DIRECTORY = os.environ.get('UPLOAD_BASE_DIRECTORY',
                                       '/tmp/filemanagment/submissions')

NS_AFFIX = '' if NAMESPACE == 'production' else f'-{NAMESPACE}'

KUBE_TOKEN = os.environ.get('KUBE_TOKEN', 'fookubetoken')
"""Service account token for authenticating with Vault. May be a file path."""

VAULT_ENABLED = bool(int(os.environ.get('VAULT_ENABLED', '0')))
"""Enable/disable secret retrieval from Vault."""

VAULT_HOST = os.environ.get('VAULT_HOST', 'foovaulthost')
"""Vault hostname/address."""

VAULT_PORT = os.environ.get('VAULT_PORT', '1234')
"""Vault API port."""

VAULT_ROLE = os.environ.get('VAULT_ROLE', 'filemanager')
"""Vault role linked to this application's service account."""

VAULT_CERT = os.environ.get('VAULT_CERT')
"""Path to CA certificate for TLS verification when talking to Vault."""

VAULT_SCHEME = os.environ.get('VAULT_SCHEME', 'https')
"""Default is ``https``."""

VAULT_REQUESTS = [
    {'type': 'generic',
     'name': 'JWT_SECRET',
     'mount_point': f'secret{NS_AFFIX}/',
     'path': 'jwt',
     'key': 'jwt-secret',
     'minimum_ttl': 60},
    {'type': 'database',
     'engine': os.environ.get('FILEMANAGER_DATABASE_ENGINE', 'mysql+mysqldb'),
     'host': os.environ.get('FILEMANAGER_DATABASE_HOST', 'localhost'),
     'database': os.environ.get('FILEMANAGER_DATABASE', 'filemanager'),
     'params': 'charset=utf8mb4',
     'port': '3306',
     'name': 'SQLALCHEMY_DATABASE_URI',
     'mount_point': f'database{NS_AFFIX}/',
     'role': 'filemanager-write'}
]
"""Requests for Vault secrets."""


STORAGE_BACKEND = os.environ.get('STORAGE_BACKEND', 'simple')
"""Name of the storage backend to use. See :mod:`.services.storage`."""

STORAGE_BASE_PATH = os.environ.get('STORAGE_BASE_PATH', None)
if STORAGE_BASE_PATH is None:
    STORAGE_BASE_PATH = tempfile.mkdtemp()
    warnings.warn('STORAGE_BASE_PATH is not set. Using temp directory: %s' %
                  STORAGE_BASE_PATH)

STORAGE_QUARANTINE_PATH = os.environ.get('STORAGE_QUARANTINE_PATH', None)
