File Management Service
=======================

2018-02-13 Initial Notes on arXivNG File Management Service
2018-03-27 Converted to restructure text

Overview
--------

The file management service (FMS) is responsible for facilitating the construction of a sanitized submission packet. This service encapsulates the addfiles, forward files, delete files, and cleanup functionality from the Legacy arXiv system.

A client will work within a 'private' filesystem sandbox to upload and organize the file(s) necessary for their submission. A simple PDF may be composed of a single file. A large TeX document may be composed of numerous files of varying types. The client will have multiple API endpoints for managing their files.

In the past authors have displayed a tendency to package up their entire working directory of files in an archive and upload to the arXiv for submission. Extraneous files are known to cause problems with arXiv's automatic AutoTeX compilation of TeX source. Accepting files from unknown entities also poses certain security risks. 
Therefore the arXiv system checks uploaded sources to reduce subsequent problems in the TeX compilation process.

The file management service executes a long list of checks against the files being uploaded. [add more detail] The majority of these cleanup tasks prepare the submission to be processed by arXiv’s AutoTeX package. [add more here]

…

As an example the current arXiv submission system limits the maximum size of individual files and of the entire submission package. The oversize error is currently displayed in the user interface and prevents an oversize submission from getting published. 
The FMS will provide status information via its API and clients will need to enforce policies like size restrictions for submission.

Once the submission files are in a valid state other services will be able to act on the submission package. In most cases the requests will be made by reference to the specific submission package. The TeX service will receive a call to process submission X and proceed to call the file management service to check status and retrieve the submission package.
The same will happen for the publish service. The publish service may actually call the TeX service to reprocess the article with the appropriate stamp information, which would in turn call the file management service to get the actual files. The publish service would also initiate the migration of source files to the persistent repository for article source files but the persistent store will communicate directly with the file management service to retrieve the submission.

[Note: There are new timing issues with such a distributed set of services. In the legacy system an author may update their submission at any time. The system must prevent updates in the middle of TeX compilation or the lengthy publish process.] One option is to ‘lock’ the submissions file management sandbox during certain critical operations [TeX compilation, publish].

Context
-------

The file management service will support the submissions workflow process. In the legacy arXiv system file management comes right after collecting licensing and primary category information. 
After the file upload step comes the process, metadata, preview, and submission steps. 
The various services in the submission workflow will need to communicate and interact with each other. 
In many cases these services will be a client of the file managment service.

The admins have traditionally had full access to submission files. Their ability to repair/update (‘hack’) submissions needs to be preserved. [Note: The question of editing a version and whether it remains the same version or should become a new version needs to be discussed further]

Handshake
---------

In arXivNG submission workflow will be distributed across several independent services. The file management service will put together a submission package, the TeX compilation service will compile any TeX source, and the publish service will talk to both TeX and FMS to facilitate publication process. 
There must be a secure reliable way of unifying all of these services. The current mechanism for resolving to an article is a submission identifier which links to a directory containing submission files and any associated entries in the database.
The FMS will generate a unique identifier that may be stored and passed around to other services.

The file management service needs to attach a unique identifier to the submission packet. This identifier will be used to create the submission packet and to subsequently passed with a request to other services (TeX, publish).

Status Notifications
--------------------

The file management service detects various conditions that impact the arXiv’s submission process work flow. The status detection and notification tasks need to be discuss further.

Status notification: Indicates whether the general integrity of the submission package is valid. 
If the service detects problems the submission workflow will not progress. 
Subsequent submission work flow steps need to check that submission package is valid before proceeding.

Update notification: Update of submission files by client currently voids ‘submitted’ status. 
If author is currently modifying submission files it does not make sense for moderators to review an old or outdated version. New system will need to monitor the status of the submission and react appropriately. 
Submission status returns to ‘working’ state and admin/moderator workflow is therefore terminated. 
[Does this status triggering mechanism still make sense in new arXivNG architecture?]

There’s one more….


API
^^^

    Note: The API is curently evolving and the details below are the initial draft.

Create - create submission file folder

        [Note: Create versus Upload]
	My concern for creating sandbox in upload request is if a network failue occurs during a large upload. 
	In this case an orphaned sandbox would exist that may consume a significant amount of disk space.

Upload/:submission_id or Upload - upload archive or individual files

	Performs dozens of checks on submitted files.

Manifest or ListFiles

	List set of files with metadata

Status/:submission_id - Current status of the submission package
            Needs to return status or any errors/warnings generated and currently active

Log/:submission_id - keep track of history of interactions with FMS
	Client actions
	Admin actions
	Errors/Warnings
	Status changes?

Lock/:submission_id ??     Ensure client does not update submission files in the middle of critical process [TeX processing, publish/admin work].
	Authorized services must be able to ‘freeze’ changes to submission files while major state change is underway (TeX compilation, Publish)

	Note: Think about whether Admins have special proviledges when locked.

GetFiles/:submission_id
	Return an tar gzipped archive containing all files contained in article workspace.
	Lock submission within FMS. At least for duration of generating archive. 
	If publish is happening may need to lock until publish process is complete to guarantee consistency of submission files.

Purge/submission_id
	When submission system is finished with submission (published, reached expiration date) it may request that files be cleaned up (removed)

Implementation Details:
^^^^^^^^^^^^^^^^^^^^^^^

Upload/Add Files Process
                (I’m mainly referring to arXivLib/lib/arXiv/Submit/Upload.pm source code along with Erick’s Analysis of Submission System)

Top level logic: (from Upload.pm)

	* Upload and clean files
	* Unpack files and do some basic cleanup
	* Create file list
	* Identify file type for each file in submission
	* Check files
	* Performs long list of checks on uploaded files.
	* Check sizes
	* Checks whether submission exceeds per file or per submission size limits.


Upload and Clean Files:

	* Unpack archive (zip tar gzipped bzip2 compressed)
	* Remove symlinks
	* Remove zero-size files
	* Existing papers (replacements)
	* Remove ‘processed’ directories
	* Decrypt any encrypted files from previous version.
	* Individual files
	* Remove __MACOSX directories
	* Unpack any packed files contained within uploaded archive.
	* Set appropriate directory/file permissions
		- Directory: 0775
		- File: 0664

Create File List:
 
	* Iterate over all files in submission
	* Identify file type for each file in submission
	* Utilizes FileType guess method to determine type.

Check Files:
	* Lots of unwanted files are removed
	* Fix/Rename files with naming issues
	* Repair files that may cause problems with AutoTeX
                
Low level code:
	Methods that edit/repair files will take time to reimplement and test.

	* Unmacify
	* Check_ps
	* Repair_ps
	* Uufile - 
	* fix_uname 
	* extract_uu
	* Repair_dos_eps
	* Strip_tiff
	* Strip_preview

Check Size (file and submission limits):
	* Look for any oversize files
	* Compute size of submission and compare to max allowable 
