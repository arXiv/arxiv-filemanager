"""Response messages."""

# exceptions
UPLOAD_MISSING_FILE = 'missing file/archive payload'
UPLOAD_MISSING_FILENAME = 'file argument missing filename or file not selected'
UPLOAD_FILE_EMPTY = 'file payload is zero length'

UPLOAD_NOT_FOUND = 'upload workspace not found'
UPLOAD_DB_ERROR = 'unable to create/insert new upload workspace into database'
UPLOAD_DB_CONNECT_ERROR = "There was a problem connecting to database."
UPLOAD_IO_ERROR = 'encountered an IOError'
UPLOAD_UNKNOWN_ERROR = 'unknown error'
UPLOAD_DELETED_FILE = 'deleted file'
UPLOAD_DELETED_WORKSPACE = 'deleted workspace'
UPLOAD_FILE_NOT_FOUND = 'file not found'
UPLOAD_DELETED_ALL_FILES = 'deleted all files'
UPLOAD_WORKSPACE_NOT_FOUND = 'workspace not found'
UPLOAD_LOCKED_WORKSPACE = 'locked workspace'
UPLOAD_UNLOCKED_WORKSPACE = 'unlocked workspace'
UPLOAD_RELEASED_WORKSPACE = 'released workspace'
UPLOAD_UNRELEASED_WORKSPACE = 'unreleased workspace'

UPLOAD_NOT_ACTIVE = 'upload workspace is not active.'
UPLOAD_WORKSPACE_LOCKED = 'upload workspace is locked.'

UPLOAD_WORKSPACE_ALREADY_DELETED = 'Request failed. Workspace has been deleted.'

# upload status codes
# INVALID_UPLOAD_ID = {'reason': 'invalid upload identifier'}
# MISSING_UPLOAD_ID = {'reason': 'missing upload id'}

# Indicate requests that have not been implemented yet.
REQUEST_NOT_IMPLEMENTED = {'request not implemented'}

# upload status
NO_SUCH_THING = {'reason': 'there is no upload'}
THING_WONT_COME = {'reason': 'could not get the upload'}

ERROR_RETRIEVING_UPLOAD = 'upload not found'
# UPLOAD_DOESNT_EXIST = {'upload does not exist'}
CANT_CREATE_UPLOAD = 'could not create the upload'  #
CANT_UPLOAD_FILE = 'could not upload file'
CANT_DELETE_FILE = 'could not delete file'
CANT_DELETE_ALL_FILES = 'could not delete all files'
CANT_RELEASE_WORKSPACE = 'could not release workspace'
CANT_UNRELEASE_WORKSPACE = 'could not unrelease workspace'

ACCEPTED = {'reason': 'upload in progress'}

MISSING_NAME = {'an upload needs a name'}

SOME_ERROR = {'Need to define and assign better error'}