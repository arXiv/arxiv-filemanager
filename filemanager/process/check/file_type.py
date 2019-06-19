"""Methods for file type checking."""

import os
import io
import re
from typing import Callable, Optional

from arxiv.base import logging

from ...domain import FileType, UploadedFile, UploadWorkspace
from .base import BaseChecker


logger = logging.getLogger(__name__)
logger.propagate = False


class InferFileType(BaseChecker):
    """Attempt to check the :class:`.FileType` of an :class:`.UploadedFile`."""

    def check_UNKNOWN(self, workspace: UploadWorkspace, u_file: UploadedFile) \
            -> UploadedFile:
        """Perform file type check."""
        logger.debug('Identify a type for %s', u_file.path)
        for check_type in _type_checkers:
            file_type = check_type(workspace, u_file)
            logger.debug('Tried %s, got %s', check_type.__name__, file_type)
            if file_type is not None:
                u_file.file_type = file_type
                return u_file

        # We need up to the first kilobyte of the file.
        with workspace.open(u_file, 'rb') as f:
            content = f.read(1024)

        for check_type in _content_type_checkers:
            file_type = check_type(workspace, u_file, content)
            logger.debug('Tried %s, got %s', check_type.__name__, file_type)
            if file_type is not None:
                u_file.file_type = file_type
                return u_file

        file_type = _heavy_introspection(workspace, u_file)
        logger.debug('Tried %s, got %s', 'heavy_introspection', file_type)
        if file_type is not None:
            u_file.file_type = file_type
            return u_file

        # Failed type identification
        logger.debug('Type identification failed for %s', u_file.path)
        u_file.file_type = FileType.FAILED    # , '', ''
        return u_file


# These are compiled ahead of time, since we may use them many many times in a
# single request.
ARXIV_COMMAND_FILE = re.compile(r'(^|/)00README\.XXX$')
DVIPS_TEMP_FILE = re.compile(r'(^|/)(head|body)\.tmp$')
MISSFONT_LOG_FILE = re.compile(r'(^|/)missfont\.log$')
AUX_TEX_FILE = re.compile(r'\.(sty|cls|mf|\d*pk|bbl|bst|tfm|ax|def|log|hrfldf'
                          r'|cfg|clo|inx|end|fgx|tbx|rtx|rty|toc)$',
                          re.IGNORECASE)
ABS_FILE = re.compile(r'\.abs$')
XFIG_FILE = re.compile(r'\.fig$')
NOTEBOOK_FILE = re.compile(r'\.nb$', re.IGNORECASE)
INPUT_FILE = re.compile(r'\.inp$', re.IGNORECASE)
HTML_FILE = re.compile(r'\.html?$', re.IGNORECASE)
ENCRYPTED_FILE = re.compile(r'\.cry$')
TIFF_FILE = re.compile(r'\.tif$', re.IGNORECASE)
JAR_FILE = re.compile(r'\.jar$', re.IGNORECASE)
ODT_FILE = re.compile(r'\.odt$', re.IGNORECASE)
DOCX_FILE = re.compile(r'\.docx$', re.IGNORECASE)
XLSX_FILE = re.compile(r'\.xlsx$', re.IGNORECASE)

# Patterns for content matching.
MAC = re.compile(rb'#!/bin/csh -f\r#|(\r|^)begin \d{1,4}\s+\S.*\r[^\n]')
PDF = re.compile(b'%PDF-')
AUTO_IGNORE = re.compile(rb'%auto-ignore')
TEXINFO = re.compile(rb'\\input texinfo')
MULTI_PART_MIME = re.compile(rb'(^|\r)Content-type: ', re.IGNORECASE)
PS_FONT = re.compile(rb'^(......)?%!(PS-AdobeFont-1\.|FontType1'
                     rb'|PS-Adobe-3\.0 Resource-Font)',
                     re.MULTILINE | re.DOTALL)
POSTSCRIPT = re.compile(b'^%!')
PS_PC = re.compile(b'(^%*\004%!)|(.*%!PS-Adobe)')
PS = re.compile(rb'^%!PS')
LATEX_MACRO = re.compile(rb'^\r?%&([^\s\n]+)')
HTML = re.compile(rb'<html[>\s]', re.IGNORECASE)
INCLUDE = re.compile(rb'%auto-include')

PERCENT_COMMENT = re.compile(rb'\%[^\r]*')
LATEX = re.compile(rb'(^|\r)\s*\\documentstyle')
LATEX2E_PDFLATEX = re.compile(rb'(^|\r)\s*\\documentclass')
MAYBE_TEX = re.compile(rb'(^|\r)\s*(\\font|\\magnification|\\input|\\def'
                       rb'|\\special|\\baselineskip|\\begin)')
TEX_PRIORITY = re.compile(rb'\\input\s+amstex')
PARTIAL_HINT_1 = re.compile(rb'(^|\r)\s*\\(end|bye)(\s|$)')
PARTIAL_HINT_2 = re.compile(rb'\\(end|bye)(\s|$)')
TEX_MAC = re.compile(rb'(\\input *(harv|lanl)mac)|(\\input\s+phyzzx)')
METAFONT = re.compile(rb'beginchar\(')
BIBTEX = re.compile(rb'(^|\r)@(book|article|inbook|unpublished){',
                    re.IGNORECASE)
BEGIN = re.compile(rb'^begin \d{1,4}\s+[^\s]+\r?$')
CARRIAGE_RETURN = re.compile(rb'\r$')
ALWAYS_IGNORE = re.compile(b'paper deliberately replaced by what little')
INCLUDE_GRAPHICS = re.compile(rb'^[^%]*\\includegraphics[^%]*\.'
                              rb'(?:pdf|png|gif|jpg)\s?\}',
                              re.IGNORECASE)
PDF_OUTPUT = re.compile(rb'^[^%]*\\pdfoutput(?:\s+)?=(?:\s+)?1')


def _check_exists(workspace: UploadWorkspace,
                  u_file: UploadedFile) -> Optional[FileType]:
    """Check whether file exists (new)."""
    if not workspace.exists(u_file.path):
        return FileType.FAILED    # , '', ''


def _check_command(workspace: UploadWorkspace,
                   u_file: UploadedFile) -> Optional[FileType]:
    """Check for arXiv's special command file."""
    if ARXIV_COMMAND_FILE.search(u_file.path):
        return FileType.README    # , '', ''


def _check_dvips_temp(workspace: UploadWorkspace,
                      u_file: UploadedFile) -> Optional[FileType]:
    """Ignore tmp files created by (unpatched) dvihps, in top dir."""
    if DVIPS_TEMP_FILE.search(u_file.path):
        return FileType.ALWAYS_IGNORE    # , '', ''


# QUESTION: is this still relevant, given that FM service is decoupled from
# compilation? -- Erick
def _check_missing_font(workspace: UploadWorkspace,
                        u_file: UploadedFile) -> Optional[FileType]:
    """Missing font error is fatal error."""
    if MISSFONT_LOG_FILE.search(u_file.path):
        return FileType.ABORT    # ', '', ''


def _check_aux_tex(workspace: UploadWorkspace,
                   u_file: UploadedFile) -> Optional[FileType]:
    """Check whether this is an auxillary TeX File."""
    if AUX_TEX_FILE.search(u_file.path):
        return FileType.TEXAUX    # ', '', ''


def _check_abs_file(workspace: UploadWorkspace,
                    u_file: UploadedFile) -> Optional[FileType]:
    """Check whether this is an arXiv legacy abstract metadata record."""
    if ABS_FILE.search(u_file.path):
        return FileType.ABS    # ', '', ''


def _check_xfig(workspace: UploadWorkspace,
                u_file: UploadedFile) -> Optional[FileType]:
    # Ignore xfig files
    if XFIG_FILE.search(u_file.path):
        return FileType.IGNORE    # , '', ''


def _check_notebook(workspace: UploadWorkspace,
                    u_file: UploadedFile) -> Optional[FileType]:
    if NOTEBOOK_FILE.search(u_file.path):
        return FileType.NOTEBOOK    # , '', ''


def _check_input(workspace: UploadWorkspace,
                 u_file: UploadedFile) -> Optional[FileType]:
    if INPUT_FILE.search(u_file.path):
        return FileType.INPUT    # , '', ''


def _check_html(workspace: UploadWorkspace,
                u_file: UploadedFile) -> Optional[FileType]:
    if HTML_FILE.search(u_file.path):
        return FileType.HTML    # , '', ''


def _check_encrypted(workspace: UploadWorkspace,
                     u_file: UploadedFile) -> Optional[FileType]:
    if ENCRYPTED_FILE.search(u_file.path):
        return FileType.ENCRYPTED    # , '', ''


def _check_zero_size(workspace: UploadWorkspace,
                     u_file: UploadedFile) -> Optional[FileType]:
    """Check for zero size file size."""
    if workspace.get_size(u_file) == 0:
        return FileType.IGNORE    # , '', ''


# Check for compressed formats (compressed,gzip,bzips)
def _check_compressed(workspace: UploadWorkspace, u_file: UploadedFile,
                      content: bytes) -> Optional[FileType]:
    if content[0] == 0x1F and content[1] == 0x9D:
        return FileType.COMPRESSED    # , '', ''


def _check_gzipped(workspace: UploadWorkspace, u_file: UploadedFile,
                   content: bytes) -> Optional[FileType]:
    if content[0] == 0x1F and content[1] == 0x8B:
        return FileType.GZIPPED    # , '', ''


def _check_bzip2(workspace: UploadWorkspace, u_file: UploadedFile,
                 content: bytes) -> Optional[FileType]:
    if content[0] == 0x42 and content[1] == 0x5A \
            and content[2] == 0x68 and content[3] > 0x2F:
        return FileType.BZIP2   # , '', ''


def _check_posix_tarfile(workspace: UploadWorkspace,
                         u_file: UploadedFile,
                         content: bytes) -> Optional[FileType]:
    # POSIX tarfiles: look for the string 'ustar' at position 257
    # (There used to be additional code to detect non-POSIX tar files
    # which is not detected with above, no longer necessary)
    if content[257:262] == b'ustar':
        return FileType.TAR    # , '', ''


def _check_dvi(workspace: UploadWorkspace, u_file: UploadedFile,
               content: bytes) -> Optional[FileType]:
    """Check for DVI file."""
    if content[0] == 0xF7 and content[1] == 2:
        return FileType.DVI    # , '', ''


def _check_gif8(workspace: UploadWorkspace, u_file: UploadedFile,
                content: bytes) -> Optional[FileType]:
    """Check for GIF8 image."""
    if content[0:4] == b'GIF8':
        return FileType.IMAGE    # , '', ''


def _check_png(workspace: UploadWorkspace, u_file: UploadedFile,
               content: bytes) -> Optional[FileType]:
    """Check for PNG image."""
    if content[0:8] == b'\211PNG\r\n\032\n':
        return FileType.IMAGE    # , '', ''


def _check_tiff(workspace: UploadWorkspace, u_file: UploadedFile,
                content: bytes) -> Optional[FileType]:
    """
    Check for TIFF image (big endian and little endian).

    Should really test b3 and b4 also, see
    `https://en.wikipedia.org/wiki/List_of_file_signatures`_.
    """
    if TIFF_FILE.search(u_file.path):
        if content[0] == 0x4D and content[1] == 0x4D:
            return FileType.IMAGE    # , '', ''
        if content[0] == 0x49 and content[1] == 0x49:
            return FileType.IMAGE    # , '', ''


def _check_jpeg(workspace: UploadWorkspace, u_file: UploadedFile,
                content: bytes) -> Optional[FileType]:
    """
    Check for JPEG image.

    2015-11: not sure about b4==0xEE, perhaps should add
    b4==0xDB || b4==0xE1
    """
    if content[0] == 0xFF and content[1] == 0xD8 and content[2] == 0xFF \
            and (content[3] == 0xE0 or content[4] == 0xEE):
        return FileType.IMAGE    # , '', ''


def _check_mpeg_image(workspace: UploadWorkspace, u_file: UploadedFile,
                      content: bytes) -> Optional[FileType]:
    """
    Check for MPEG image.

    2015-11: other seqs for MPEG, and certainly other movie types missing.
    """
    if content[0] == 0x0 and content[1] == 0x0 and content[2] == 0x1 \
            and content[3] == 0xB3:
        return FileType.ANIM    # , '', ''


def _check_zip_and_extensions(workspace: UploadWorkspace,
                              u_file: UploadedFile,
                              content: bytes) -> Optional[FileType]:
    """
    Check for zip format or an extension.

    Related formats: JAR, ODF,DOCX,XLSX,ZIP.
    """
    zip_preamble_1 = b'PK\003\004'
    zip_preamble_2 = b'PK00PK\003\004'
    if content[0:4] == zip_preamble_1 or content[0:8] == zip_preamble_2:
        if JAR_FILE.search(u_file.path):
            return FileType.JAR    # , '', ''
        if ODT_FILE.search(u_file.path):
            return FileType.ODF    # , '', ''
        if DOCX_FILE.search(u_file.path):
            return FileType.DOCX    # , '', ''
        if XLSX_FILE.search(u_file.path):
            return FileType.XLSX    # , '', ''
        return FileType.ZIP    # , '', ''


def _check_rar(workspace: UploadWorkspace, u_file: UploadedFile,
               content: bytes) -> Optional[FileType]:
    """Check for a RAR file."""
    if content[0:4] == b'Rar!':
        return FileType.RAR    # , '', ''


def _check_dos_eps(workspace: UploadWorkspace, u_file: UploadedFile,
                   content: bytes) -> Optional[FileType]:
    """
    Check for DOS EPS.

    :0  belong          0xC5D0D3C6      DOS EPS Binary File
    ->4 long            >0              Postscript starts at byte %d
    """
    if content[0] == 0xC5 and content[1] == 0xD0 and content[2] == 0xD3 \
            and content[3] == 0xC6:
        return FileType.DOS_EPS    # , '', ''


def _check_pdf(workspace: UploadWorkspace, u_file: UploadedFile,
               content: bytes) -> Optional[FileType]:
    if PDF.search(content):
        return FileType.PDF    # , '', ''


def _check_mac(workspace: UploadWorkspace, u_file: UploadedFile,
               content: bytes) -> Optional[FileType]:
    if MAC.search(content):
        return FileType.MAC    # , '', ''


# TODO: this can use more refactoring, but didn't want to get too deep into
# it right now. -- Erick
def _heavy_introspection(workspace: UploadWorkspace,
                         u_file: UploadedFile) -> Optional[FileType]:
    """
    Perform final checks that involve heavy reading from the file.

    This implementation is stateful, so this should be preserved as one
    function unless refactored to be less stateful.
    """
    # Keep track of TeX files
    maybe_tex = 0
    maybe_tex_priority = 0
    maybe_tex_priority2 = 0

    # Scan file line by line looking for a wide variety of type indicators
    with workspace.open(u_file, 'rb') as f:
        line_no = 1
        accum = b""
        for line in f:
            # Ignore
            if line_no <= 10 and AUTO_IGNORE.search(line):
                return FileType.IGNORE    # , '', ''
            # TeXinfo
            if line_no <= 10 and TEXINFO.search(line):
                return FileType.TEXINFO    # , '', ''
            # Mult part document
            if line_no <= 40 and MULTI_PART_MIME.search(line):
                return FileType.MULTI_PART_MIME    # , '', ''

            # LaTeX2e/PDFLaTeX
            if line[0:6] == '%!TEX ' and line_no == 1:
                return _type_of_latex2e(u_file, line_no)

            accum += line   # Accumulate what we've already seen.

            # QUESTION: why does this (now commented by me) code exist? The
            # print statement will never be reached, and it does not generate
            # information about a file type. -- Erick
            #
            # once = 0
            # if re.search(rb'PS-AdobeFont-1\.', accum):
            #     if once:
            #         print("ACCUM: " + str(accum[0:200]) + "\n")
            #         once += 1

            # Match strings starting at either 1st or 7th byte. Use $accum
            # to build string of file to this point as the preceding 6 chars
            # may include \n

            # Postscript Font
            if line_no <= 7 and PS_FONT.search(accum):
                return FileType.PS_FONT    # , '', ''

            # Postscript
            if POSTSCRIPT.search(line) and line_no == 1:
                return FileType.POSTSCRIPT    # , '', ''

            # TODO MUST Test this adjusted regex
            if ((line_no == 1 and PS_PC.search(line))
                    or (line_no <= 10 and PS.search(line) and maybe_tex == 0)):
                return FileType.PS_PC    # , '', ''

            # LaTeX and TeX macros
            match = LATEX_MACRO.search(line)
            if line_no <= 12 and match:
                latex_type = ''
                if match is not None:
                    latex_type = match.group(1)
                    if (latex_type == 'latex209' or latex_type == 'biglatex'
                            or latex_type == 'latex' or latex_type == 'LaTeX'):
                        return FileType.LATEX    # , str(latex_type), ''

                    return FileType.TEX_MAC    # , str(latex_type), ''

            # HTML
            if line_no <= 10 and HTML.search(line):
                return FileType.HTML    # , '', ''

            # Include
            if line_no <= 10 and INCLUDE.search(line):
                return FileType.INCLUDE    # , '', ''

            # All subsequent checks have lines with '%' in them chopped.
            #  if we need to look for a % then do it earlier!
            orig = line
            line = re.sub(PERCENT_COMMENT, b'', line)
            if line != orig:
                logger.debug('ORIG: %s', orig)
                logger.debug('New: %s', line)

            # LaTeX
            if LATEX.search(line):
                return FileType.LATEX    # , '', ''

            # LaTeX2e/PDFLaTeX
            if LATEX2E_PDFLATEX.search(line):
                return _type_of_latex2e(f, line_no)

            if MAYBE_TEX.search(line):
                maybe_tex = 1
                if TEX_PRIORITY.search(line):
                    return FileType.TEX_priority    # , '', ''

            # Partianl Hint
            if PARTIAL_HINT_1.search(line):
                maybe_tex_priority = 1

            # Partial Hint
            if PARTIAL_HINT_2.search(line):
                maybe_tex_priority2 = 1

            if TEX_MAC.search(line):
                return FileType.TEX_MAC    # , '', ''

            # MetaFont
            if METAFONT.search(line):
                return FileType.MF    # , '', ''

            # BibTeX
            if BIBTEX.search(line):
                return FileType.BIBTEX    # , '', ''

            # Make some decisions using partial hints we've seen already
            # TeX,PC,UUENCODED
            if BEGIN.search(line):
                if maybe_tex_priority:
                    return FileType.TEX_priority    # , '', ''
                if maybe_tex:
                    return FileType.TEX    # , '', ''
                if CARRIAGE_RETURN.search(line):
                    return FileType.PC    # , '', ''
                return FileType.UUENCODED    # , '', ''

            if ALWAYS_IGNORE.search(line):
                return FileType.ALWAYS_IGNORE    # , '', ''
            line_no += 1

        # last chance guesses
        if maybe_tex_priority:
            return FileType.TEX_priority    # , '', ''
        if maybe_tex_priority2:
            return FileType.TEX_priority2, '', ''
        if maybe_tex:
            return FileType.TEX    # , '', ''


# Select bewteen PDFLATEX and LATEX2e types.
def _type_of_latex2e(f: io.BytesIO, count: int) -> FileType:
    """Determine whether file is PDFLATEX or LATEX2e."""
    limit = count + 5
    f.seek(0, 0)    # Rewind to beginning of file
    line_no = 1
    for line in f:
        if INCLUDE_GRAPHICS.search(line) \
                or (line_no < limit and PDF_OUTPUT.search(line)):
            return FileType.PDFLATEX    # ', '', ''
        line_no += 1
    return FileType.LATEX2e    # ', '', ''


_type_checkers: Callable[[UploadWorkspace, UploadedFile],
                         Optional[FileType]] = [
    _check_exists,
    # Currently the following type identification relies on the extension
    # to identify the type without inspecting content of file.
    _check_command,
    _check_dvips_temp,
    _check_missing_font,
    _check_aux_tex,
    _check_abs_file,
    _check_xfig,
    _check_notebook,
    _check_input,
    _check_html,
    _check_encrypted,
    _check_zero_size,
]
"""Checks that do not require inspecting content."""

_content_type_checkers: Callable[[UploadWorkspace, UploadedFile, bytes],
                                 Optional[FileType]] = [
    _check_compressed,
    _check_gzipped,
    _check_bzip2,
    _check_posix_tarfile,
    _check_dvi,
    _check_gif8,
    _check_png,
    _check_tiff,
    _check_jpeg,
    _check_mpeg_image,
    _check_zip_and_extensions,
    _check_rar,
    _check_dos_eps,
    _check_pdf,
    _check_mac,

]
"""Checks requiring content inspection."""
