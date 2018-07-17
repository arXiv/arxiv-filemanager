Description of individual upload test cases.

This directory contains well-formed submissions along with submissions
designed to trigger specific errors.

Additional details may be found in test_process_upload.py file.

----

Prerequisites: DB uploads table (will be created automatically), development server

Procedure: For each test case upload test submission archive.

Notes: Upload summary indicates errors/warnings and a list of files contained in submission archive.

README.md	- This file!

File			- Expected result

1801.03879-1.tar.gz	- contains hidden files / removed

UnpackWithSubdirectories.tar.gz
* Summary: Submission containing gzipped archives containing other subdirectories.
* Expected results: Nested directories are correctly extracted from archive.
* Status: Ready

Upload9BadFileNames.tar.gz
* Summary: Contains bad file names.
* Expected results: Rename files with warnings.
* Status: Ready with warnings

UploadTestWindowCDrive.tar.gz
* Summary: Contains Windows paths.
* Expected results: Renames Windows paths to Unix style paths.
* Status: Ready with warnings
* Notes: Changes will likely break submission.

UploadWithANCDirectory.tar.gz
* Summary: Upload with ancillary files.
* Expected results: Ancillary files unpacked in anc directory.
* Status: Ready

source_with_dir.tar.gz
* Summary: Remove top level directory
* Expected results: Automatically removes top level directory.
* Status: Ready with warning

upload-nested-zip-and-tar.zip
* Summary: Submission that contains a bad zip
* Expected results: Error about malformed zip file.
* Status: Ready with warnings
* Note: Submitter is still able to proceed with submission. Difficult to know/track whether this
issue is resolved by subsequent uploads.

upload1.tar.gz
* Summary: Contains zero-size file 'espcrc2.sty'
* Expected results: Remove zero-size file
* Status: Ready with warnings

upload2.tar.gz
* Summary: Clean submission: well-formed / valid submission / no errors
* Expected results: Upload without errors/warnings.
* Status: Ready

upload3.tar.gz
* Summary: Clean submission: well-formed / valid submission / no errors
* Expected results: Upload without errors/warnings.
* Status: Ready

upload4.gz
* Summary: Invalid filename
* Expected results: Rename file with warnings.
* Status: Ready with warnings

upload5.pdf
* Summary: Clean submission: well-formed / valid submission / no errors
* Expected results: Upload without errors/warnings.
* Status: Ready

upload5.tar.gz
* Summary: Rename invalid filename to valid filename.
* Expected results: Rename file with warning
* Status: Ready with warnings

upload6.tgz
* Summary: Clean submission: well-formed / valid submission / no errors
* Expected results: Upload without errors/warnings.
* Status: Ready

upload7.tar.gz
* Summary: Contains useless top level directory
* Expected results: Automatically removes top level directory.
* Status: Ready with warnings
