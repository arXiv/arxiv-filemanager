class UploadFileSecurityError(RuntimeError):
    """Potential file path security issue.

    This error is generated when s client supplied file path changes after we
    sanitize the public file path. This indicates potential manipulation of
    public_file_path argument to process methods.
    """


class InvalidUploadContentError(ValueError):
    """The upload content payload is invalid."""


class EmptyUploadContentError(ValueError):
    """The upload content payload is empty."""


class NoSourceFilesToCheckpoint(RuntimeError):
    """There are no user uploaded files to checkpoint."""