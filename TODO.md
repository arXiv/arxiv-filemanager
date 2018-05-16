TODO List:

List of outstanding todo items from PR feedback that could
not be completed or would hold up PR merge. 

1) Conflict between upload functions/variables and Python internal functions.
   Perl legacy code used type() and current code uses file.
   These should be easy to eliminate once PRs are closed.

2) Improve documentation. Develop own template for providing
   useful documentation.

3) Rename awkward file names. Reorganize code files.
   arXiv directory/package name should be changed. This contains
   support routines translated from legacy system.
   utilities - contains other helper routines distilled from
   upload code. May reintegrate some back into sanitize.py 
   (or better yet upload.py).

   Need to clean up file naming and where these files live.

...
