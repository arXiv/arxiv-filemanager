"""
Implements arXiv's file type guess logic.

Attempts to detect obvious errors in uploaded files and assigns priority
in terms of our downstream TeX compilation process.
"""

import os
import os.path
import re
from typing import Tuple, Any

# TeX types
TEX_types = ['LATEX',
             'TEX',
             'TEX_priority',
             'TEX_AMS',
             'TEX_MAC',
             'LATEX2e',
             'TEX_priority2',
             'TEXINFO',
             'PDFLATEX',
             'PDFTEX'
            ]

# Priorities may be redesigned and reimplemented once I understand the entire
# impact of their use. Initial Python implementation attempts to stay true to
# the original Perl version author's design until the point I know better.

type_priorities = [
    'ABORT',
    'FAILED',
    'ALWAYS_IGNORE',
    'INPUT',
    'BIBTEX',
    'POSTSCRIPT',
    'DOS_EPS',
    'PS_FONT',
    'PS_PC',
    'IMAGE',
    'ANIM',
    'HTML',
    'PDF',
    'DVI',
    'NOTEBOOK',
    'ODF',
    'DOCX',
    'TEX',
    'PDFTEX',
    'TEX_priority2',
    'TEX_AMS',
    'TEX_priority',
    'TEX_MAC',
    'LATEX',
    'LATEX2e',
    'PDFLATEX',
    'TEXINFO',
    'MF',
    'UUENCODED',
    'ENCRYPTED',
    'PC',
    'MAC',
    'CSH',
    'SH',
    'JAR',
    'RAR',
    'XLSX',
    'COMPRESSED',
    'ZIP',
    'GZIPPED',
    'BZIP2',
    'MULTI_PART_MIME',
    'TAR',
    'IGNORE',
    'README',
    'TEXAUX',
    'ABS',
    'INCLUDE'
]




# Internal type routines. These routines are core of type guessing logic.




def is_tex_type(type: str) -> bool:
    """Check of type is TeX file."""
    if type in TEX_types:
        return True

    return False


def get_type_name(type: str) -> str:
    """
    Return display string for specified type.

    Will return 'unknown' if type is not recognized.
    """
    if type in type_name.keys():
        return type_name[type]

    return 'unknown'


def get_type_priority(file_type: str) -> int:
    """
    Returns an integer indicating the processing priority of file type.

    Higher numbers should be processed first. Will return 0 (lower
    than all other types) if $type is not recognized.
    """
    if file_type in type_priorities:
        return type_priorities.index(file_type) + 1

    return 0


# These methods filter internal file type information. Need to investigate whether this
# can be eliminated in the future.

def guess(filepath: str) -> str:
    """
    Return a cleaned up version of the internal file type.

    Removes TYPE_ prefix and lower cases resulting type.
    """
    # Not using tex_format or error from guess_file_type at this time
    (file_type, _, _) = guess_file_type(filepath)
    # Type returned does not include TYPE_ prefix

    if file_type.startswith('TYPE_'):
        return file_type[len('TYPE_'):].lower()

    return file_type.lower()


def name(type: str) -> str:
    """Return the cleaned up type of the file."""
    if not type.startswith('TYPE_'):
        type = 'TYPE_' + type

    type = type.upper()

    if type.find('LATEX2E') >= 0:
        type = type.replace('LATEX2E', 'LATEX2e')

    return get_type_name(type)


def _is_tex_type(type: str) -> bool:
    """
    Returns true if file is of TeX type.

    This method does some normalization prior to calling internal routine.
    """
    if not type.startswith('TYPE_'):
        type = 'TYPE_' + type
    type = type.upper()
    if type.find('LATEX2E') >= 0:
        type = type.replace('LATEX2E', 'LATEX2e')
    if type.find('PRIORITY') >= 0:
        type = type.replace('PRIORITY', 'priority')
    return is_tex_type(type)
