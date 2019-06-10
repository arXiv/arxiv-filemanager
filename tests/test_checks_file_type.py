"""
Tests for :mod:`.check.file_type`.

Moved these file type checks over from test_unit_file_type, since I separated
the FileType domain class from the type inference routines (now in
filemanager.process.check.file_type). -- Erick 2019-06-10
"""

import os
from unittest import TestCase, mock

from arxiv.base import logging
from filemanager.domain import UploadWorkspace, UploadedFile, FileType
from filemanager.process.check.file_type import InferFileType
logger = logging.getLogger(__name__)

parent, _ = os.path.split(os.path.abspath(__file__))
DATA_PATH = os.path.join(parent, 'type_test_files')

type_tests = []
#type_tests.append(['garbage.txt', FileType.shit])
type_tests.append(['00README.XXX', FileType.README])
# Ignore/Abort
type_tests.append(['head.tmp', FileType.ALWAYS_IGNORE])  # new
type_tests.append(['body.tmp', FileType.ALWAYS_IGNORE])  # new
type_tests.append(['missfont.log', FileType.ABORT])  # new
# TeX Auxillary Files
type_tests.append(['ms.bbl', FileType.TEXAUX])  # new
type_tests.append(['ol.sty', FileType.TEXAUX])  # new

type_tests.append(['SciPost.cls', FileType.TEXAUX])  # new
# archives
type_tests.append(['compressed.Z', FileType.COMPRESSED])
type_tests.append(['gzipped.gz', FileType.GZIPPED])
# BZIP
type_tests.append(['short-1.txt.bz2', FileType.BZIP2])
type_tests.append(['short-4.txt.bz2', FileType.BZIP2])
type_tests.append(['short-9.txt.bz2', FileType.BZIP2])
# Tar
type_tests.append(['testtar.tar', FileType.TAR])

type_tests.append(['verlinde.dvi', FileType.DVI])

# type_tests.append(['image.gif', FileType.IMAGE])
# Image
type_tests.append(['image.tif', FileType.IMAGE])
type_tests.append(['image.jpg', FileType.IMAGE])
type_tests.append(['image.png', FileType.IMAGE])
type_tests.append(['image.gif', FileType.IMAGE])  # new
type_tests.append(['centaur_1_first1k.mpg', FileType.ANIM])

type_tests.append(['pipnss.jar', FileType.JAR])
type_tests.append(['odf_test.odt', FileType.ODF])
type_tests.append(['Hellotest.docx', FileType.DOCX])
type_tests.append(['Agenda_Elegant_Style_EN.Level1.docx', FileType.DOCX])
type_tests.append(['Helloworld.xlsx', FileType.XLSX])
type_tests.append(['holtxdoc.zip', FileType.ZIP])
type_tests.append(['Hellotest.not_docx_ext', FileType.ZIP])
type_tests.append(['Helloworld.not_xlsx_ext', FileType.ZIP])
type_tests.append(['odf_test.not_odt_ext', FileType.ZIP])

type_tests.append(['0604408.pdf', FileType.RAR])
type_tests.append(['minimal.pdf', FileType.PDF])  # new

# TeX
type_tests.append(['polch.tex', FileType.LATEX])
type_tests.append(['paper-t4.1_Vienna_preprint.tex', FileType.LATEX2e])
type_tests.append(['minMac.tex', FileType.LATEX2e, '',
                   'This file was generated on MAC with \r\n'])
type_tests.append(['pascal_petit.tex', FileType.PDFLATEX])

# a \pdfoutput=1 may come in various places, all valid
type_tests.append(['pdfoutput_before_documentclass.tex', FileType.PDFLATEX])
type_tests.append(['pdfoutput_sameline_documentclass.tex', FileType.PDFLATEX])
type_tests.append(['pdfoutput_after_documentclass.tex', FileType.PDFLATEX])
type_tests.append(['pdfoutput_after_documentclass_big_comment_before.tex',
                  FileType.PDFLATEX])
# but if we put it too late it is ignored
type_tests.append(['pdfoutput_too_far_after_documentclass.tex',
                  FileType.LATEX2e])
type_tests.append([
    'pdfoutput_too_far_after_documentclass_big_comment_before.tex',
    FileType.LATEX2e
])
# EPS
type_tests.append(['dos_eps_1.eps', FileType.DOS_EPS])
type_tests.append(['dos_eps_2.eps', FileType.DOS_EPS])

# Need MAC

# font files must not be detected as simple PS
type_tests.append(['rtxss.pfb', FileType.PS_FONT])
type_tests.append(['c059036l.pfb', FileType.PS_FONT])
type_tests.append(['hrscs.pfa', FileType.PS_FONT])
type_tests.append(['bchbi.pfa', FileType.PS_FONT])
type_tests.append(['mutau2-sub_first10kB.tar', FileType.PS_PC, '',
                   'Should really be TAR but this is old pre-posix tar which'
                   ' we will not support. Doing so would require'
                   ' re-implementation of the c-code used by the unix file'
                   ' command, there are no magic codes for this.'
                   ' http://issues.library.cornell.edu/browse/ARXIVDEV-146'])
# error cases
type_tests.append(['10240_null_chars.tar', FileType.FAILED])
type_tests.append(['file_does_not_exit', FileType.FAILED])

type_tests.append(['fmultipart.txt', FileType.FAILED])
type_tests.append(['multipart.txt', FileType.MULTI_PART_MIME])
type_tests.append(['one.ps', FileType.POSTSCRIPT])
type_tests.append(['index.html', FileType.HTML])
type_tests.append(['sample.bib', FileType.BIBTEX])  # new


class TestInferFileType(TestCase):
    """Test file type inference."""

    def setUp(self):
        """We have a checker instance."""
        self.check = InferFileType()
        self.mock_workspace = mock.MagicMock(spec=UploadWorkspace)
        self.mock_workspace.get_full_path.side_effect \
            = lambda f: os.path.join(DATA_PATH, f.path)
        self.mock_workspace.open.side_effect \
            = lambda f, m, **k: open(os.path.join(DATA_PATH, f.path), m, **k)

    def test_infer_gif(self):
        """Infer file type of a gif image."""
        mock_file = mock.MagicMock(path='image.gif',
                                   file_type=FileType.UNKNOWN,
                                   size_bytes=495)
        self.check(self.mock_workspace, mock_file)
        self.assertEqual(mock_file.file_type, FileType.IMAGE)

    def test_file_type_guess(self):
        """
        Test file type identification.

        Reproduces tests from legacy system.
        """
        for test in type_tests:
            test_file, test_file_type, deep, note, *extras = test + [None] * 2
            logger.debug("Test:%s:%s\tDeep: %s\tNote: %s",
                         test_file, test_file_type, str(deep), str(note))
            # Make the call - get the file type guess
            mock_file = mock.MagicMock(path=test_file,
                                       file_type=FileType.UNKNOWN)
            self.check(self.mock_workspace, mock_file)
            # guessed_type, tex_type, error_msg = guess_file_type(new_path)

            msg = "Expected file '%s' of type '%s' but got '%s' (%s)" % \
                (test_file, test_file_type, mock_file.file_type.value, note)

            self.assertEqual(mock_file.file_type, test_file_type, msg)
