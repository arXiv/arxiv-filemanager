"""Unpack upload archive into source directory for analysis.

Upload archive may contain other tarred/gzipped archives internally.

"""

# TODO Compress - Need to implement uncompress for traditional Unix compress .Z files.
#      Need to figure best way to shell/system out to system uncompress program since
#      this is not supported directly in Python.

import shutil
import os.path

import tarfile
import zipfile

from filemanager.arxiv.file import File


ERROR_MSG_PRE = 'There were problems unpacking "'
ERROR_MSG_SUF = '" -- continuing. Please try again and confirm your files.'

# TODO Add logging so we are able to capture additional information during
# debugging - for now deactivate
DEBUG = 0


def unpack_archive(upload: 'Upload') -> None:
    """
    Unpack uploaded files.

    Unpack uploaded archives and recursively traverse the source directory
    and unpack any additional gzipped/tar archives contained within original
    archive.

    Parameters
    ----------
    upload : Upload
        Upload object with files to be unpacks.

    Returns
    -------
    None

    Notes
    -----
    Originates from Upload.pm (Perl).
    """
    #archive_name = os.path.basename(archive_path)
    # TODO debug logging ("*******Process upload: " + archive_name + '*****************')

    source_directory = upload.get_source_path()
    removed_directory = upload.get_removed_path()

    # Recursively scan source directory and uplack all archives until there
    # are no more gzipped/tar archives.
    packed_file = 1
    round = 1
    while packed_file:
        # TODO debug logging ("\n*****ROUND " + str(round) + '  Packed: '
        # + str(packed_file) + '*****\n')

        for root_directory, subdirs, files in os.walk(source_directory):
            # TODO debug logging (f"---> Dir {root_directory} contains the
            # directories {b} and the files {c}")
            # ignoring directories using '_' above

            for dir in subdirs:
                # create path
                path = os.path.join(root_directory, dir)

                # wrap in our File encapsulation class
                obj = File(path, source_directory)

                # if obj.name == '__MACOSX':
                #     upload.add_warning(obj.public_filepath, "Removed '__MACOSX' directory.")
                #     # Remove __MACOSX directory
                #     if os.path.exists(path):
                #         shutil.rmtree(path)
                #     # Remove deleted directory from os.walk
                #     subdirs.remove(dir)
                # elif obj.name == 'processed':  # and from_paper_id
                #     # TODO: Need to investigate what's going on here so we
                #     # TODO: understand what needs to be done.
                #     #
                #     # Deletion of 'processed' directory depends on
                #     # from_paper_id also being set.
                #     #
                #     # This appears to be related to replacing a submission
                #     # where files are imported/copied from previous version of paper.
                #     #
                #     # Legacy action is to delete 'processed' directory when
                #     # from_paper_id is set.
                #     #
                #     # We have not reached the point of implementing this yet so
                #     # I will only issue a warning for now.
                #     upload.add_warning(obj.public_filepath, "Detected 'processed' directory. Please check.")

            for file in files:

                # os.walk provides a list of files with the root directory so
                # we need to build path at each step
                path = os.path.join(root_directory, file)

                # wrap in our File encapsulation class
                obj = File(path, source_directory)

                # TODO log something to source log
                # print("File is : " + file + " Size: " + str(obj.size)
                # + " File is type: " + obj.type + ":" + obj.type_string + '\n')

                # Tar module is supposed to handle bz2 compressed files (gzip too)
                # if ((obj.type == 'tar' or obj.type == 'gzipped')
                #         and tarfile.is_tarfile(path)) or obj.type == 'bzip2':
                #     # TODO debug logging ("**Found tar  or bzip2 file!**\n")
                #
                #     target_directory = os.path.join(source_directory, root_directory)
                #
                #     msg = f"***** unpack {obj.type} {file} to dir: {target_directory}"
                #     upload.log(msg)
                #     # Move gzipped file out of way
                #     rfile = os.path.join(removed_directory, os.path.basename(path))
                    #
                    # # Maybe can't do this in production if submitter reloads tar.gz
                    # if os.path.exists(rfile) and (os.path.getsize(rfile) == os.path.getsize(path)):
                    #     # File (same size) saved already! Remove tar file
                    #     msg = f"Removed packed file {file}"
                    #     upload.log(msg)
                    #     os.remove(path)
                    # else:
                    #     rem_path = os.path.join(removed_directory, os.path.basename(path))
                    #     msg = f"Removed packed file {file}"
                    #     upload.log(msg)
                    #     # Now move tar file out of way to removed directory
                    #     shutil.move(path, rem_path)
                    # # Since we are unpacking something we want to make one more pass over files.
                    # packed_file += 1

                # elif obj.type == 'tar' and not tarfile.is_tarfile(path):
                #     print("Package 'tarfile' unable to read this tar file.")
                #     # TODO Throw an error

                # Hanlde .zip files
                # elif obj.type == 'zip' and zipfile.is_zipfile(path):
                #     target_directory = os.path.join(source_directory, root_directory)
                #     print("*******Process zip archive: " + path)
                #     msg = f"***** unpack {obj.type} {file} to dir: {target_directory}"
                #     upload.log(msg)
                #     try:
                #         with zipfile.ZipFile(path, "r") as zip_ref:
                #             zip_ref.extractall(target_directory)
                #             # Now move zip file out of way to removed directory
                #             rem_path = os.path.join(removed_directory, os.path.basename(path))
                #             msg = f"Removed packed file {file}"
                #             upload.log(msg)
                #             shutil.move(path, rem_path)
                #             # Since we are unpacking something we want to make
                #             # one more pass over files.
                #             packed_file += 1
                #     except zipfile.BadZipFile as error:
                #         # TODO: Think about warnings a bit. Tar/zip problems
                #         # currently reported as warnings. Upload warnings allow
                #         # submitter to continue on to process/compile step.
                #         upload.add_warning(obj.public_filepath, ERROR_MSG_PRE + obj.public_filepath + ERROR_MSG_SUF)
                #         upload.add_warning(obj.public_filepath, 'Zip error message: ' + error.__str__())

                # TODO: Add support for compressed files
                # elif obj.type == 'compressed':
                #     print("We can't uncompress .Z files yet.")
                #     msg = f"***** unpack {obj.type} {file} to dir: {source_directory}"
                #     upload.log(msg)
                #     msg = "Unable to uncompress .Z file. Not implemented yet"
                #     upload.log(msg)

                # TODO: Handle 'processed' and __MACOSX directories (removal of/deletion)

                # TODO: Handle encrypted files - need to investigate Crypt and how we are using it.

        round += 1
        packed_file -= 1

    # Set permissions on all directories and files
    upload.set_file_permissions()
