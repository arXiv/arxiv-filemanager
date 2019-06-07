from unittest import TestCase
from filemanager.arxiv import file_type
from filemanager.arxiv.file_type import guess_file_type, get_type_priority, is_tex_type, get_type_name, get_type_priority, \
    _is_tex_type, name, guess
import os.path

# type_tests.append(['', ''])

type_tests = []
#type_tests.append(['garbage.txt', 'shit'])
type_tests.append(['00README.XXX', 'README'])
# Ignore/Abort
type_tests.append(['head.tmp', 'ALWAYS_IGNORE'])  # new
type_tests.append(['body.tmp', 'ALWAYS_IGNORE'])  # new
type_tests.append(['missfont.log', 'ABORT'])  # new
# TeX Auxillary Files
type_tests.append(['ms.bbl', 'TEXAUX'])  # new
type_tests.append(['ol.sty', 'TEXAUX'])  # new

type_tests.append(['SciPost.cls', 'TEXAUX'])  # new
# archives
type_tests.append(['compressed.Z', 'COMPRESSED'])
type_tests.append(['gzipped.gz', 'GZIPPED'])
# BZIP
type_tests.append(['short-1.txt.bz2', 'BZIP2'])
type_tests.append(['short-4.txt.bz2', 'BZIP2'])
type_tests.append(['short-9.txt.bz2', 'BZIP2'])
# Tar
type_tests.append(['testtar.tar', 'TAR'])

type_tests.append(['verlinde.dvi', 'DVI'])

# type_tests.append(['image.gif', 'IMAGE'])
# Image
type_tests.append(['image.tif', 'IMAGE'])
type_tests.append(['image.jpg', 'IMAGE'])
type_tests.append(['image.png', 'IMAGE'])
type_tests.append(['image.gif', 'IMAGE'])  # new
type_tests.append(['centaur_1_first1k.mpg', 'ANIM'])

type_tests.append(['pipnss.jar', 'JAR'])
type_tests.append(['odf_test.odt', 'ODF'])
type_tests.append(['Hellotest.docx', 'DOCX'])
type_tests.append(['Agenda_Elegant_Style_EN.Level1.docx', 'DOCX'])
type_tests.append(['Helloworld.xlsx', 'XLSX'])
type_tests.append(['holtxdoc.zip', 'ZIP'])
type_tests.append(['Hellotest.not_docx_ext', 'ZIP'])
type_tests.append(['Helloworld.not_xlsx_ext', 'ZIP'])
type_tests.append(['odf_test.not_odt_ext', 'ZIP'])

type_tests.append(['0604408.pdf', 'RAR'])
type_tests.append(['minimal.pdf', 'PDF'])  # new

# TeX
type_tests.append(['polch.tex', 'LATEX'])
type_tests.append(['paper-t4.1_Vienna_preprint.tex', 'LATEX2e'])
type_tests.append(['minMac.tex', 'LATEX2e', '', 'This file was generated on MAC with \r\n'])
type_tests.append(['pascal_petit.tex', 'PDFLATEX'])

# a \pdfoutput=1 may come in various places, all valid
type_tests.append(['pdfoutput_before_documentclass.tex', 'PDFLATEX'])
type_tests.append(['pdfoutput_sameline_documentclass.tex', 'PDFLATEX'])
type_tests.append(['pdfoutput_after_documentclass.tex', 'PDFLATEX'])
type_tests.append(['pdfoutput_after_documentclass_big_comment_before.tex', 'PDFLATEX'])
# but if we put it too late it is ignored
type_tests.append(['pdfoutput_too_far_after_documentclass.tex', 'LATEX2e'])
type_tests.append(['pdfoutput_too_far_after_documentclass_big_comment_before.tex', 'LATEX2e'])
# EPS
type_tests.append(['dos_eps_1.eps', 'DOS_EPS'])
type_tests.append(['dos_eps_2.eps', 'DOS_EPS'])

# Need MAC

# font files must not be detected as simple PS
type_tests.append(['rtxss.pfb', 'PS_FONT'])
type_tests.append(['c059036l.pfb', 'PS_FONT'])
type_tests.append(['hrscs.pfa', 'PS_FONT'])
type_tests.append(['bchbi.pfa', 'PS_FONT'])
type_tests.append(['mutau2-sub_first10kB.tar', 'PS_PC', '',
                   'Should really be TAR but this is old pre-posix tar which we will not support. Doing so would require re-implementation of the c-code used by the unix file command, there are no magic codes for this. http://issues.library.cornell.edu/browse/ARXIVDEV-146'])
# error cases
type_tests.append(['10240_null_chars.tar', 'FAILED'])
type_tests.append(['file_does_not_exit', 'FAILED'])

type_tests.append(['fmultipart.txt', 'FAILED'])
type_tests.append(['multipart.txt', 'MULTI_PART_MIME'])
type_tests.append(['one.ps', 'POSTSCRIPT'])
type_tests.append(['index.html', 'HTML'])
type_tests.append(['sample.bib', 'BIBTEX'])  # new

name_tests = []


class TestGuessFileType(TestCase):
    """Test file type identification logic"""

    def test_file_type_guess(self):
        """Test file type identification."""

        cwd = os.getcwd()
        testfiles_dir = os.path.join(cwd, 'tests/type_test_files')

        # Reproduce tests from legacy system
        for test in type_tests:

            test_file, test_file_type, deep, note, *extras = test + [None] * 2
            new_path = os.path.join(testfiles_dir, test_file)

            debug = 0
            if debug:
                print("\nTest:" + test_file + ":" + test_file_type + "\tDeep: "
                      + str(deep) + "Note: " + str(note))

            # Make the call - get the file type guess
            guessed_type, tex_type, error_msg = guess_file_type(new_path)

            # print("****File: " + test_file + "   Guessed Type: " + guessed_type
            #      + "  TeX type: " + tex_type + "  Error: " + error_msg + "\n")

            msg = "Expected file '" + test_file + "' of type '" + test_file_type + "' but got '" + guessed_type + "'"
            if note:
                msg = msg + " (" + note + ")"

            self.assertEqual(guessed_type, test_file_type, msg)

    def test_get_type_name(self):
        """Test human readable type name lookup."""
        self.assertEqual(get_type_name('LATEX'), 'LaTeX', 'Lookup type name')
        self.assertEqual(get_type_name('TAR'), 'TAR archive', 'Lookup type name')
        self.assertEqual(get_type_name('DAVID'), 'unknown', 'Lookup name for non existent type')


    def test_is_tex_type(self):
        """Test that TeX file types are identified correctly."""
        self.assertTrue(is_tex_type('LATEX'), 'Expected TeX file type')
        self.assertTrue(is_tex_type('TEX'), 'Expected TeX file type')
        self.assertTrue(is_tex_type('TEX_priority2'), 'Expected TeX file type')
        self.assertFalse(is_tex_type('HTML'), 'Expected non-TeX file type')


    def test_type_priority(self):
        """Spot check type priorities."""
        self.assertEqual(get_type_priority('DOES_NOT_EXIST'), 0,
                         'Unknown type should return lowest priorit=0')
        self.assertLess(get_type_priority('BIBTEX'), get_type_priority('TEX'),
                        'TeX source higher priority than BibTeX')
        self.assertLess(get_type_priority('TEX'), get_type_priority('PDFTEX'),
                        'PDFTEX is higher priority then plain TEX source.')
        self.assertLess(get_type_priority('LATEX'), get_type_priority('LATEX2e'),
                        'PDFTEX is higher priority then plain TEX source.')
        self.assertLess(get_type_priority('LATEX2e'), get_type_priority('PDFLATEX'),
                        'PDFTEX is higher priority then plain TEX source.')

        self.assertLess(get_type_priority('LATEX'), get_type_priority('README'),
                        'README directives file higher priority than TeX source')

        # Add some specific priority tests to catch inadvertant changes to new list
        self.assertEqual(get_type_priority('ABORT'), 1,
                         'Expect signal for immediate stop.')
        self.assertEqual(get_type_priority('FAILED'), 2,
                         'Expect priority for FAILED type guess.')
        self.assertEqual(get_type_priority('PDF'), 13,
                         'Expect priority for PDF type guess.')
        self.assertEqual(get_type_priority('TEX'), 18,
                         'Expect priority for TEX type guess.')
        self.assertEqual(get_type_priority('LATEX'), 24,
                         'Expect priority for LATEX type guess.')
        self.assertEqual(get_type_priority('ZIP'), 39,
                         'Expect priority for ZIP type guess.')
        self.assertEqual(get_type_priority('INCLUDE'), 48,
                         'Expect priority for INCLUDE type guess.')


class TestExternalMethods(TestCase):
    """Test file type identification logic"""

    def test_abreviated_type_methods(self):
        cwd = os.getcwd()
        testfiles_dir = os.path.join(cwd, 'tests/type_test_files')
        testfile_path = os.path.join(testfiles_dir, 'image.gif')
        self.assertEqual(guess(testfile_path), "image", 'Check guess type with normalized/lower cased type')
        self.assertEqual(name('LATEX'), 'LaTeX', 'Lookup type name')
        self.assertTrue(_is_tex_type('LATEX'), 'Expected TeX file type')
        self.assertTrue(_is_tex_type('LATEX2E'), 'Expected TeX file type')
        self.assertTrue(_is_tex_type('TEX_PRIORITY'), 'Expected TeX file type')
        self.assertFalse(_is_tex_type('TEX_FAKE'), 'Expected non-TeX file type')
