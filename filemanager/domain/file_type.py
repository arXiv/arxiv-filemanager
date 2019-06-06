from enum import Enum


class FileType(Enum):
    """Known file types."""

    TYPE_UNKNOWN = 'TYPE_UNKNOWN'
    TYPE_ABORT = 'TYPE_ABORT'
    TYPE_FAILED = 'TYPE_FAILED'
    TYPE_ALWAYS_IGNORE = 'TYPE_ALWAYS_IGNORE'
    TYPE_INPUT = 'TYPE_INPUT'
    TYPE_BIBTEX = 'TYPE_BIBTEX'
    TYPE_POSTSCRIPT = 'TYPE_POSTSCRIPT'
    TYPE_DOS_EPS = 'TYPE_DOS_EPS'
    TYPE_PS_FONT = 'TYPE_PS_FONT'
    TYPE_PS_PC = 'TYPE_PS_PC'
    TYPE_IMAGE = 'TYPE_IMAGE'
    TYPE_ANIM = 'TYPE_ANIM'
    TYPE_HTML = 'TYPE_HTML'
    TYPE_PDF = 'TYPE_PDF'
    TYPE_DVI = 'TYPE_DVI'
    TYPE_NOTEBOOK = 'TYPE_NOTEBOOK'
    TYPE_ODF = 'TYPE_ODF'
    TYPE_DOCX = 'TYPE_DOCX'
    TYPE_TEX = 'TYPE_TEX'
    TYPE_PDFTEX = 'TYPE_PDFTEX'
    TYPE_TEX_priority2 = 'TYPE_TEX_priority2'
    TYPE_TEX_AMS = 'TYPE_TEX_AMS'
    TYPE_TEX_priority = 'TYPE_TEX_priority'
    TYPE_TEX_MAC = 'TYPE_TEX_MAC'
    TYPE_LATEX = 'TYPE_LATEX'
    TYPE_LATEX2e = 'TYPE_LATEX2e'
    TYPE_PDFLATEX = 'TYPE_PDFLATEX'
    TYPE_TEXINFO = 'TYPE_TEXINFO'
    TYPE_MF = 'TYPE_MF'
    TYPE_UUENCODED = 'TYPE_UUENCODED'
    TYPE_ENCRYPTED = 'TYPE_ENCRYPTED'
    TYPE_PC = 'TYPE_PC'
    TYPE_MAC = 'TYPE_MAC'
    TYPE_CSH = 'TYPE_CSH'
    TYPE_SH = 'TYPE_SH'
    TYPE_JAR = 'TYPE_JAR'
    TYPE_RAR = 'TYPE_RAR'
    TYPE_XLSX = 'TYPE_XLSX'
    TYPE_COMPRESSED = 'TYPE_COMPRESSED'
    TYPE_ZIP = 'TYPE_ZIP'
    TYPE_GZIPPED = 'TYPE_GZIPPED'
    TYPE_BZIP2 = 'TYPE_BZIP2'
    TYPE_MULTI_PART_MIME = 'TYPE_MULTI_PART_MIME'
    TYPE_TAR = 'TYPE_TAR'
    TYPE_IGNORE = 'TYPE_IGNORE'
    TYPE_README = 'TYPE_README'
    TYPE_TEXAUX = 'TYPE_TEXAUX'
    TYPE_ABS = 'TYPE_ABS'
    TYPE_INCLUDE = 'TYPE_INCLUDE'

    @property
    def name(self) -> str:
        """Human-readable name of the file type."""
        return FILE_TYPE_NAMES.get(self, 'unknown')

    @property
    def is_tex_type(self) -> bool:
        """
        Indicate whether this is a TeX type.

        This method does some normalization prior to calling internal routine.
        """
        return self in TEX_TYPES


FILE_TYPE_NAMES = {
    FileType.TYPE_UNKNOWN: 'Unknown',
    FileType.TYPE_ABORT: 'Immediate stop',
    FileType.TYPE_FAILED: FileType.unknown,
    FileType.TYPE_ALWAYS_IGNORE: 'Always ignore',
    FileType.TYPE_INPUT: 'Input for (La)TeX',
    FileType.TYPE_BIBTEX: FileType.BiBTeX,
    FileType.TYPE_POSTSCRIPT: FileType.Postscript,
    FileType.TYPE_DOS_EPS: 'DOS EPS Binary File',
    FileType.TYPE_PS_FONT: 'Postscript Type 1 Font',
    FileType.TYPE_PS_PC: '^D%! Postscript',
    FileType.TYPE_IMAGE: 'Image (gif/jpg etc)',
    FileType.TYPE_ANIM: 'Animation (mpeg etc)',
    FileType.TYPE_HTML: FileType.HTML,
    FileType.TYPE_PDF: FileType.PDF,
    FileType.TYPE_DVI: FileType.DVI,
    FileType.TYPE_NOTEBOOK: 'Mathematica Notebook',
    FileType.TYPE_ODF: 'OpenDocument Format',
    FileType.TYPE_DOCX: 'Microsoft DOCX',
    FileType.TYPE_TEX: FileType.TEX,
    FileType.TYPE_PDFTEX: FileType.PDFTEX,
    FileType.TYPE_TEX_priority2:
        'TeX (with \\end or \\bye - not starting a line)',
    FileType.TYPE_TEX_AMS: FileType.AMSTeX,
    FileType.TYPE_TEX_priority: 'TeX (with \\end or \\bye)',
    FileType.TYPE_TEX_MAC: 'TeX +macros (harv,lanl..)',
    FileType.TYPE_LATEX: FileType.LaTeX,
    FileType.TYPE_LATEX2e: FileType.LATEX2e,
    FileType.TYPE_PDFLATEX: FileType.PDFLATEX,
    FileType.TYPE_TEXINFO: FileType.Texinfo,
    FileType.TYPE_MF: FileType.Metafont,
    FileType.TYPE_UUENCODED: FileType.UUencoded,
    FileType.TYPE_ENCRYPTED: FileType.Encrypted,
    FileType.TYPE_PC: 'PC-ctrl-Ms',
    FileType.TYPE_MAC: 'MAC-ctrl-Ms',
    FileType.TYPE_CSH: FileType.CSH,
    FileType.TYPE_SH: FileType.SH,
    FileType.TYPE_JAR: 'JAR archive',
    FileType.TYPE_RAR: 'RAR archive',
    FileType.TYPE_XLSX: 'Microsoft XLSX',
    FileType.TYPE_COMPRESSED: 'UNIX-compressed',
    FileType.TYPE_ZIP: 'ZIP-compressed',
    FileType.TYPE_GZIPPED: 'GZIP-compressed',
    FileType.TYPE_BZIP2: 'BZIP2-compressed',
    FileType.TYPE_MULTI_PART_MIME: FileType.MULTI_PART_MIME,
    FileType.TYPE_TAR: 'TAR archive',
    FileType.TYPE_IGNORE: ' user defined IGNORE',
    FileType.TYPE_README: FileType.override,
    FileType.TYPE_TEXAUX: 'TeX auxiliary',
    FileType.TYPE_ABS: FileType.abstract,
    FileType.TYPE_INCLUDE: ' keep'
}

TEX_TYPES = [
    FileType.TYPE_LATEX,
    FileType.TYPE_TEX,
    FileType.TYPE_TEX_priority,
    FileType.TYPE_TEX_AMS,
    FileType.TYPE_TEX_MAC,
    FileType.TYPE_LATEX2e,
    FileType.TYPE_TEX_priority2,
    FileType.TYPE_TEXINFO,
    FileType.TYPE_PDFLATEX,
    FileType.TYPE_PDFTEX
]
