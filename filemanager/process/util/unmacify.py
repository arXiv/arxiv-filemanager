import mmap
import re
from arxiv.base import logging

from ...domain import UploadedFile, UploadWorkspace

logger = logging.getLogger(__name__)


# File types unmacify is interested in
PC = 'pc'
MAC = 'mac'


def unmacify(workspace: UploadWorkspace, uploaded_file: UploadedFile) -> None:
    """
    Cleans up files containing carriage returns and line feeds.

    Files generated on Macs and Windows machines frequently have carriage
    returns that we must clean up prior to compilation.

    Jake informs me there is a bug in the Perl unmacify routine.

    Parameters
    ----------
    file_obj : File
        File object containing details about file to unmacify.

    """
    # Determine type of file we are dealing with PC or MAC
    file_type = MAC

    # Check whether file contains '\r\n' sequence
    with workspace.open(uploaded_file, 'rb', buffering=0) as f, \
            mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as s:
        if s.find(b"\r\n") != -1:
            file_type = PC

    # Fix up carriage returns and newlines.
    workspace.log(f'Un{file_type}ify file {uploaded_file.path}')

    # Open file and look for carriage return.
    new_path = f'{uploaded_file.path}.new'
    new_file = workspace.create(new_path, file_type=uploaded_file.file_type)
    with workspace.open(uploaded_file, 'rb', buffering=0) as infile, \
            workspace.open(new_file, 'wb', buffering=0) as outfile, \
            mmap.mmap(infile.fileno(), 0, access=mmap.ACCESS_READ) as s:

        if file_type == PC:
            outfile.write(re.sub(b"\r\n", b"\n", s.read()))
        elif file_type == MAC:
            outfile.write(re.sub(b"\r\n?", b"\n", s.read()))

    # Check if file was changed.
    if workspace.cmp(uploaded_file, new_file, shallow=False):
        with workspace.open(uploaded_file, 'wb') as outfile, \
                workspace.open(new_file, 'rb') as infile:
            outfile.write(infile.read())

        # Check for unwanted termination character
    check_file_termination(workspace, uploaded_file)
    workspace.delete(new_file)


def check_file_termination(workspace: UploadWorkspace,
                           u_file: UploadedFile) -> None:
    r"""
    Check for unwanted characters at end of file.

    The original unmacify/unpcify routine attemtps to cleanup the last few
    characters in a file regardless or whether the file is pc/mac generated.
    For that reason I have refactored the code into a seperate routine for
    ease of testing. This also simplifies the unmacify routine.

    This code basically seeks to the end of file and removes any end of file
    \377, end of transmission ^D (\004), or  characters ^Z (\032).

    At the current time this routine will get called anytime unmacify routine
    is called.

    Parameters
    ----------


    """
    # Check for special characters at end of file.
    # Remove EOT/EOF
    workspace.log(f"Checking file termination for {u_file.path}.")

    with workspace.open(u_file, "rb+") as f:
        # Seek to last two bytes of file
        f.seek(-2, 2)

        # Examine bytes for characters we want to strip.
        input_bytes = f.read(2)
        logger.debug(f"Read '{input_bytes}' from {u_file.path}")

        byte_found = False
        if input_bytes[0] == 0x01A or input_bytes[0] == 0x4 \
                or input_bytes[0] == 0xFF:
            byte_found = True

            f.seek(-2, 2)
            fsize = f.tell()
            f.truncate(fsize)
        elif input_bytes[1] == 0x01A or input_bytes[1] == 0x4 \
                or input_bytes[1] == 0xFF:
            byte_found = True
            f.seek(-1, 2)
            fsize = f.tell()
            f.truncate(fsize)

        if byte_found:
            msg = ""

            if input_bytes[0] == 0x01A or input_bytes[1] == 0x01A:
                msg += "trailing ^Z "
            if input_bytes[0] == 0x4 or input_bytes[1] == 0x4:
                msg += "trailing ^D "
            if input_bytes[0] == 0xFF or input_bytes[1] == 0xFF:
                msg += "trailing =FF "
            if input_bytes[1] == 0x0A:
                workspace.log(f"{u_file.path} [stripped newline] ")

            workspace.add_warning(u_file,
                                  f"{msg} stripped from {u_file.path}.")

        # Check of last character of file is newline character
        # Seek to last two bytes of file
        f.seek(-1, 2)
        last_byte = f.read(1)
        if last_byte != b'\n':
            workspace.add_warning(u_file,
                                  f"File '{u_file.path}' does not end with"
                                  " newline (\\n), TRUNCATED?")
