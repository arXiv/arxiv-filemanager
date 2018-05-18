"""Implements arXiv's file type guess logic.

   Attempts to detect obvious errors in uploaded files and assigns priority
   in terms of our downstream TeX compilation process.
   """

import os
import os.path
import re
from typing import Tuple

# TeX types
TEX_types = ['TYPE_LATEX',
             'TYPE_TEX',
             'TYPE_TEX_priority',
             'TYPE_TEX_AMS',
             'TYPE_TEX_MAC',
             'TYPE_LATEX2e',
             'TYPE_TEX_priority2',
             'TYPE_TEXINFO',
             'TYPE_PDFLATEX',
             'TYPE_PDFTEX'
            ]

# Priorities may be redesigned and reimplemented once I understand the entire
# impact of their use. Initial Python implementation attempts to stay true to
# the original Perl version author's design until the point I know better.

# Type priorities
priority = 0


def set_priority() -> int:
    """This is going away real soon. But still needs doc string!"""
    global priority
    priority = + priority
    priority = priority + 1
    return priority

type_priorities = [
    'TYPE_ABORT',
    'TYPE_FAILED',
    'TYPE_ALWAYS_IGNORE',
    'TYPE_INPUT',
    'TYPE_BIBTEX',
    'TYPE_POSTSCRIPT',
    'TYPE_DOS_EPS',
    'TYPE_PS_FONT',
    'TYPE_PS_PC',
    'TYPE_IMAGE',
    'TYPE_ANIM',
    'TYPE_HTML',
    'TYPE_PDF',
    'TYPE_DVI',
    'TYPE_NOTEBOOK',
    'TYPE_ODF',
    'TYPE_DOCX',
    'TYPE_TEX',
    'TYPE_PDFTEX',
    'TYPE_TEX_priority2',
    'TYPE_TEX_AMS',
    'TYPE_TEX_priority',
    'TYPE_TEX_MAC',
    'TYPE_LATEX',
    'TYPE_LATEX2e',
    'TYPE_PDFLATEX',
    'TYPE_TEXINFO',
    'TYPE_MF',
    'TYPE_UUENCODED',
    'TYPE_ENCRYPTED',
    'TYPE_PC',
    'TYPE_MAC',
    'TYPE_CSH',
    'TYPE_SH',
    'TYPE_JAR',
    'TYPE_RAR',
    'TYPE_XLSX',
    'TYPE_COMPRESSED',
    'TYPE_ZIP',
    'TYPE_GZIPPED',
    'TYPE_BZIP2',
    'TYPE_MULTI_PART_MIME',
    'TYPE_TAR',
    'TYPE_IGNORE',
    'TYPE_README',
    'TYPE_TEXAUX',
    'TYPE_ABS',
    'TYPE_INCLUDE'
]

#type_priorities = {}
type_name = {}

type_name['TYPE_ABORT'] = 'Immediate stop'
type_name['TYPE_FAILED'] = 'unknown'
type_name['TYPE_ALWAYS_IGNORE'] = 'Always ignore'
type_name['TYPE_INPUT'] = 'Input for (La)TeX'
type_name['TYPE_BIBTEX'] = 'BiBTeX'
type_name['TYPE_POSTSCRIPT'] = 'Postscript'
type_name['TYPE_DOS_EPS'] = 'DOS EPS Binary File'
type_name['TYPE_PS_FONT'] = 'Postscript Type 1 Font'
type_name['TYPE_PS_PC'] = '^D%! Postscript'
type_name['TYPE_IMAGE'] = 'Image (gif/jpg etc)'
type_name['TYPE_ANIM'] = 'Animation (mpeg etc)'
type_name['TYPE_HTML'] = 'HTML'
type_name['TYPE_PDF'] = 'PDF'
type_name['TYPE_DVI'] = 'DVI'
type_name['TYPE_NOTEBOOK'] = 'Mathematica Notebook'
type_name['TYPE_ODF'] = 'OpenDocument Format'
type_name['TYPE_DOCX'] = 'Microsoft DOCX'
type_name['TYPE_TEX'] = 'TEX'
type_name['TYPE_PDFTEX'] = 'PDFTEX'
type_name['TYPE_TEX_priority2'] = 'TeX (with \\end or \\bye - not starting a line)'
type_name['TYPE_TEX_AMS'] = 'AMSTeX'
type_name['TYPE_TEX_priority'] = 'TeX (with \\end or \\bye)'
type_name['TYPE_TEX_MAC'] = 'TeX +macros (harv,lanl..)'
type_name['TYPE_LATEX'] = 'LaTeX'
type_name['TYPE_LATEX2e'] = 'LATEX2e'
type_name['TYPE_PDFLATEX'] = 'PDFLATEX'
type_name['TYPE_TEXINFO'] = 'Texinfo'
type_name['TYPE_MF'] = 'Metafont'
type_name['TYPE_UUENCODED'] = 'UUencoded'
type_name['TYPE_ENCRYPTED'] = 'Encrypted'
type_name['TYPE_PC'] = 'PC-ctrl-Ms'
type_name['TYPE_MAC'] = 'MAC-ctrl-Ms'
type_name['TYPE_CSH'] = 'CSH'
type_name['TYPE_SH'] = 'SH'
type_name['TYPE_JAR'] = 'JAR archive'
type_name['TYPE_RAR'] = 'RAR archive'
type_name['TYPE_XLSX'] = 'Microsoft XLSX'
type_name['TYPE_COMPRESSED'] = 'UNIX-compressed'
type_name['TYPE_ZIP'] = 'ZIP-compressed'
type_name['TYPE_GZIPPED'] = 'GZIP-compressed'
type_name['TYPE_BZIP2'] = 'BZIP2-compressed'
type_name['TYPE_MULTI_PART_MIME'] = 'MULTI_PART_MIME'
type_name['TYPE_TAR'] = 'TAR archive'
type_name['TYPE_IGNORE'] = ' user defined IGNORE'
type_name['TYPE_README'] = 'override'
type_name['TYPE_TEXAUX'] = 'TeX auxiliary'
type_name['TYPE_ABS'] = 'abstract'
type_name['TYPE_INCLUDE'] = ' keep'


# Select bewteen PDFLATEX and LATEX2e types.
def _type_of_latex2e(file, count: int) -> Tuple[str, str, str]:
    """Determine whether file is PDFLATEX or LATEX2e."""
    limit = count + 5

    # Rewind to beginning of file
    file.seek(0, 0)

    line_no = 1
    for line in file:
        if re.search(rb'^[^%]*\\includegraphics[^%]*\.'
                     + rb'(?:pdf|png|gif|jpg)\s?\}', line, re.IGNORECASE) \
                or (line_no < limit and re.search(rb'^[^%]*\\pdfoutput(?:\s+)?=(?:\s+)?1', line)):
            return 'TYPE_PDFLATEX', '', ''
        line_no += 1
    return 'TYPE_LATEX2e', '', ''

# Internal type routines. These routines are core of type guessing logic.

def guess_file_type(filepath: str) -> Tuple[str, str, str]:
    """Guess the file type of filename.
    :type filepath: object
    """

    # check whether file exists (new)
    if not os.path.isfile(filepath):
        return 'TYPE_FAILED', '', ''

    # Currently the following type identification relies on the extension
    # to identify the type without inspecting content of file.

    # arXxiv's special command file
    if re.search(r'(^|/)00README\.XXX$', filepath):
        return "TYPE_README", '', ''

    # Ignore tmp files created by (unpatched) dvihps, in top dir
    if re.search(r'(^|/)(head|body)\.tmp$', filepath):
        return 'TYPE_ALWAYS_IGNORE', '', ''

    # Missing font error is fatal error
    if re.search(r'(^|/)missfont\.log$', filepath):
        return 'TYPE_ABORT', '', ''

    # Auxillary TeX Files
    if re.search(r'\.(sty|cls|mf|\d*pk|bbl|bst|tfm|ax|def|log|hrfldf|cfg'
                 + r'|clo|inx|end|fgx|tbx|rtx|rty|toc)$',
                 filepath, re.IGNORECASE):
        return 'TYPE_TEXAUX', '', ''

    # Abstract
    if re.search(r'\.abs$', filepath):
        return 'TYPE_ABS', '', ''

    # Ignore xfig files
    if re.search(r'\.fig$', filepath):
        return 'TYPE_IGNORE', '', ''

    if re.search(r'\.nb$', filepath, re.IGNORECASE):
        return 'TYPE_NOTEBOOK', '', ''

    if re.search(r'\.inp$', filepath, re.IGNORECASE):
        return 'TYPE_INPUT', '', ''

    if re.search(r'\.html?$', filepath):
        return 'TYPE_HTML', '', ''

    if re.search(r'\.cry$', filepath):
        return 'TYPE_ENCRYPTED', '', ''

    # Check for zero size file size
    if os.stat(filepath).st_size == 0:
        return 'TYPE_IGNORE', '', ''

    # Checks requiring content inspection

    # Check for compressed formats (compressed,gzip,bzips)
    # Need to inspect first 8 input_bytes of file
    fd = open(filepath, "rb")
    input_bytes = fd.read(8)
    fd.close()

    # Compressed
    if input_bytes[0] == 0x1F and input_bytes[1] == 0x9D:
        return 'TYPE_COMPRESSED', '', ''
    if input_bytes[0] == 0x1F and input_bytes[1] == 0x8B:
        return 'TYPE_GZIPPED', '', ''
    if input_bytes[0] == 0x42 and input_bytes[1] == 0x5A \
            and input_bytes[2] == 0x68 and input_bytes[3] > 0x2F:
        return 'TYPE_BZIP2', '', ''

    # POSIX tarfiles: look for the string 'ustar' at position 257
    # (There used to be additional code to detect non-POSIX tar files
    # which is not detected with above, no longer necessary)
    file = open(filepath, "rb")
    file.seek(257, 0)
    tar_test = file.read(5)

    if tar_test == b'ustar':
        return 'TYPE_TAR', '', ''

    # DVI
    if input_bytes[0] == 0xF7 and input_bytes[1] == 2:
        return 'TYPE_DVI', '', ''

    if input_bytes[0:4] == b'GIF8':
        return 'TYPE_IMAGE', '', ''

    # PNG IMAGE
    if input_bytes[0:8] == b'\211PNG\r\n\032\n':
        return 'TYPE_IMAGE', '', ''

    # TIFF IMAGE
    # (big endian and little endian)
    # should really test b3 and b4 also, see https://en.wikipedia.org/wiki/List_of_file_signatures
    if re.search(r'\.tif$', filepath):
        if input_bytes[0] == 0x4D and input_bytes[1] == 0x4D:
            return 'TYPE_IMAGE', '', ''
        if input_bytes[0] == 0x49 and input_bytes[1] == 0x49:
            return 'TYPE_IMAGE', '', ''

    # JPEG IMAGE
    # 2015-11: not sure about b4==0xEE, perhaps should add b4==0xDB || b4==0xE1
    if input_bytes[0] == 0xFF and input_bytes[1] == 0xD8 and input_bytes[2] == 0xFF and \
            (input_bytes[3] == 0xE0 or input_bytes[4] == 0xEE):
        return 'TYPE_IMAGE', '', ''

    # MPEG IMAGE
    # 2015-11: other seqs for MPEG, and certainly other movie types missing
    if input_bytes[0] == 0x0 and input_bytes[1] == 0x0 \
            and input_bytes[2] == 0x1 and input_bytes[3] == 0xB3:
        return 'TYPE_ANIM', '', ''

    # Related formats: JAR, ODF,DOCX,XLSX,ZIP
    option1 = b'PK\003\004'
    option2 = b'PK00PK\003\004'

    if (input_bytes[0:4] == option1) or (input_bytes[0:8] == option2):
        if re.search(r'\.jar$', filepath, re.IGNORECASE):
            return 'TYPE_JAR', '', ''
        if re.search(r'\.odt$', filepath, re.IGNORECASE):
            return 'TYPE_ODF', '', ''
        if re.search(r'\.docx$', filepath, re.IGNORECASE):
            return 'TYPE_DOCX', '', ''
        if re.search(r'\.xlsx$', filepath, re.IGNORECASE):
            return 'TYPE_XLSX', '', ''
        return 'TYPE_ZIP', '', ''

    # RAR
    option = b'Rar!'
    if option == input_bytes[0:4]:
        return 'TYPE_RAR', '', ''

    # DOS EPS
    #:0  belong          0xC5D0D3C6      DOS EPS Binary File
    # ->4 long            >0              Postscript starts at byte %d
    if input_bytes[0] == 0xC5 and input_bytes[1] == 0xD0 \
            and input_bytes[2] == 0xD3 and input_bytes[3] == 0xC6:
        return 'TYPE_DOS_EPS', '', ''

    # Fetch a chunck of data from file
    file.seek(0, 0)
    kilo = file.read(1024)

    if re.search(b'%PDF-', kilo):
        return 'TYPE_PDF', '', ''

    if re.search(rb'#!/bin/csh -f\r#|(\r|^)begin \d{1,4}\s+\S.*\r[^\n]', kilo):
        return 'TYPE_MAC', '', ''

    set = 0  # debugging

    # Keep track of TeX files
    maybe_tex = 0
    maybe_tex_priority = 0
    maybe_tex_priority2 = 0

    # Scan file line by line looking for a wide variety of type indicators
    file.seek(0, 0)
    line_no = 1
    accum = b""
    for line in file:
        #     if line_no <= 10:
        # print("Line: " + str(line_no) + " : " + str(line))
        # Ignore
        if line_no <= 10 and re.search(rb'%auto-ignore', line):
            return 'TYPE_IGNORE', '', ''
        # TeXinfo
        if line_no <= 10 and re.search(rb'\\input texinfo', line):
            return 'TYPE_TEXINFO', '', ''
        # Mult part document
        if line_no <= 40 and re.search(rb'(^|\r)Content-type: ', line, re.IGNORECASE):
            return 'TYPE_MULTI_PART_MIME', '', ''
        # LaTeX2e/PDFLaTeX
        if line[0:6] == '%!TEX ' and line_no == 1:
            # TODO investigate reset of file pointer - understand what is going on
            _type_of_latex2e(file, line_no)

        # Accumulate what we've already seen
        accum += line
        # Match strings starting at either 1st or 7th byte. Use $accum
        # to build string of file to this point as the preceding 6 chars
        # may include \n
        once = 0
        if re.search(rb'PS-AdobeFont-1\.', accum):
            if once:
                print("ACCUM: " + str(accum[0:200]) + "\n")
                once += 1

        # Postscript Font
        if line_no <= 7 and \
                re.search(rb'^(......)?%!(PS-AdobeFont-1\.|FontType1|PS-Adobe-3\.0 Resource-Font)',
                          accum, re.MULTILINE | re.DOTALL):
            return 'TYPE_PS_FONT', '', ''

        # Postscript
        if re.search(b'^%!', line) and line_no == 1:
            return 'TYPE_POSTSCRIPT', '', ''

        # TODO MUST Test this adjusted regex
        if ((line_no == 1 and re.search(b'(^%*\004%!)|(.*%!PS-Adobe)', line))
                or (line_no <= 10 and re.search(rb'^%!PS', line) and maybe_tex == 0)):
            return 'TYPE_PS_PC', '', ''

        # LaTeX and MAC TeX
        if line_no <= 12 and re.search(rb'^\r?%&([^\s\n]+)', line):
            match = re.search(rb'^\r?%&([^\s\n]+)', line)
            latex_type = ''
            if match is not None:
                latex_type = re.search(rb'^\r?%&([^\s\n]+)', line).group(1)
            if (latex_type == 'latex209' or latex_type == 'biglatex'
                    or latex_type == 'latex' or latex_type == 'LaTeX'):
                return 'TYPE_LATEX', str(latex_type), ''
            else:
                return 'TYPE_TEX_MAC', str(latex_type), ''

        # HTML
        if line_no <= 10 and re.search(rb'<html[>\s]', line, re.IGNORECASE):
            return 'TYPE_HTML', '', ''

        # Include
        if line_no <= 10 and re.search(rb'%auto-include', line):
            return 'TYPE_INCLUDE', '', ''

        # All subsequent checks have lines with '%' in them chopped.
        #  if we need to look for a % then do it earlier!
        orig = line
        line = line.replace(rb'\%[^\r]*', b'')
        # if line.replace(b'\%[^\r]*', b''):
        if line != orig:
            print("ORIG: " + str(orig))
            print("New: ", str(line))
        if re.search(rb'%[^\r]*', line):
            #print("Found commented lineA" + str(line) + '\n')
            line = line.replace(rb'\%[^\r]*', b'')
            #print("Found commented lineB" + str(line) + '\n')

        # LaTeX
        if re.search(rb'(^|\r)\s*\\documentstyle', line):
            return 'TYPE_LATEX', '', ''
        # LaTeX2e/PDFLaTeX
        if re.search(rb'(^|\r)\s*\\documentclass', line):
            return _type_of_latex2e(file, line_no)

        if re.search(rb'(^|\r)\s*(\\font|\\magnification|\\input|\\def|\\special|'
                     + rb'\\baselineskip|\\begin)', line):
            maybe_tex = 1
            match = re.search(rb'(^|\r)\s*(\\font|\\magnification|\\input|\\def|'
                              + rb'\\special|\\baselineskip|\\begin)',
                              line).group(2)
            if set == 0:
                print("Set HINT TYPE_TEX 0 (line:[" + str(line_no) + "]\n" + str(match))
                set = 1
            if re.search(rb'\\input\s+amstex', line):
                return 'TYPE_TEX_priority', '', ''
        # Partianl Hint
        if re.search(rb'(^|\r)\s*\\(end|bye)(\s|$)', line):
            maybe_tex_priority = 1
        # Partial Hint
        if re.search(rb'\\(end|bye)(\s|$)', line):
            maybe_tex_priority2 = 1

        if re.search(rb'(\\input *(harv|lanl)mac)|(\\input\s+phyzzx)', line):
            return 'TYPE_TEX_MAC', '', ''

        # MetaFont
        if re.search(rb'beginchar\(', line):
            return 'TYPE_MF', '', ''

        # BibTeX
        if re.search(rb'(^|\r)@(book|article|inbook|unpublished){', line, re.IGNORECASE):
            return 'TYPE_BIBTEX', '', ''

        # Make some decisions using partial hints we've seen already
        # TeX,PC,UUENCODED
        if re.search(rb'^begin \d{1,4}\s+[^\s]+\r?$', line):
            if maybe_tex_priority:
                return 'TYPE_TEX_priority', '', ''
            if maybe_tex:
                print("Set TYPE_TEX 1\n")
                return 'TYPE_TEX', '', ''
            if re.search(b'\r$', line):
                return 'TYPE_PC', '', ''
            return 'TYPE_UUENCODED', '', ''

        if re.search(b'paper deliberately replaced by what little', line):
            return 'TYPE_ALWAYS_IGNORE', '', ''
        line_no += 1

    # cleanup
    file.close()

    # last chance guesses
    if maybe_tex_priority:
        return 'TYPE_TEX_priority', '', ''
    if maybe_tex_priority2:
        return 'TYPE_TEX_priority2', '', ''
    if maybe_tex:
        print("Set TYPE_TEX 2\n")
        return 'TYPE_TEX', '', ''

    # Failed type identification
    return 'TYPE_FAILED', '', ''


def is_tex_type(type: str) -> bool:
    """Check of type is TeX file."""
    if type in TEX_types:
        return True
    else:
        return False


def get_type_name(type: str) -> str:
    """Return display string for specified type or 'unknown' if type is not
    recognized."""

    if type in type_name.keys():
        return type_name[type]
    else:
        return 'unknown'


def get_type_priority(type: str) -> int:
    """Returns an integer indicating the processing priority of this file
    type. Higher numbers should be processed first. Will return 0 (lower
    than all other types) if $type is not recognized."""
    if type in type_priorities:
        return type_priorities.index(type) + 1
    else:
        return 0


# These methods filter internal file type information. Need to investigate whether this
# can be eliminated in the future.

def guess(filepath: str) -> str:
    """Return a cleaned up version of the internal file type minus
    TYPE prefix and lower cased."""
    (type, tex_format, error) = guess_file_type(filepath)
    # Type returned does not include TYPE_ prefix

    if type.startswith('TYPE_'):
        return type[len('TYPE_'):].lower()

    return type.lower()


def name(type: str) -> str:
    """Return the cleaned up type of the file."""
    if not type.startswith('TYPE_'):
        type = 'TYPE_' + type

    type = type.upper()
    return get_type_name(type)


def _is_tex_type(type: str) -> bool:
    """Returns true if file is of TeX type. This method does some normalization
    prior to calling internal routine."""
    if not type.startswith('TYPE_'):
        type = 'TYPE_' + type
    type = type.upper()
    if type.find('TYPE_LATEX2E') >= 0:
        type = type.replace('TYPE_LATEX2E', 'TYPE_LATEX2e')
    if type.find('PRIORITY') >= 0:
        type = type.replace('PRIORITY', 'priority')
    return is_tex_type(type)
