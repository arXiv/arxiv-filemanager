
def check_upload_file_size_limit(path: str):
    """Check that upload file size is within limit set for arXiv.

    This checks for upload archive files that are too large. These achives may
    be compressed."""
    # TODO Implement upload file size limit
    return True


def check_individual_file_size_limit (path: str):
    """Make sure individual file size does not exceed limit set for arXiv"""
    return True

def check_aggregate_size_limit (upload_id: int):
    """Make sure aggregate size of upload does not exceed limit set for arXiv.

    Add up size of all files included in upload and compare to maximum limit."""
    return True
