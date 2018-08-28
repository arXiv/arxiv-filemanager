from unittest import TestCase
from filemanager.arxiv import file_type
from filemanager.arxiv.file_type import guess_file_type, get_type_priority, is_tex_type, get_type_name, get_type_priority, \
    _is_tex_type, name, guess
import os.path

# type_tests.append(['', ''])

type_tests = []
#type_tests.append(['garbage.txt', 'shit'])
type_tests.append(['00README.XXX', 'TYPE_README'])
# Ignore/Abort
type_tests.append(['head.tmp', 'TYPE_ALWAYS_IGNORE'])  # new
type_tests.append(['body.tmp', 'TYPE_ALWAYS_IGNORE'])  # new
type_tests.append(['missfont.log', 'TYPE_ABORT'])  # new
# TeX Auxillary Files
type_tests.append(['ms.bbl', 'TYPE_TEXAUX'])  # new
type_tests.append(['ol.sty', 'TYPE_TEXAUX'])  # new

type_tests.append(['SciPost.cls', 'TYPE_TEXAUX'])  # new
# archives
type_tests.append(['compressed.Z', 'TYPE_COMPRESSED'])
type_tests.append(['gzipped.gz', 'TYPE_GZIPPED'])
# BZIP
type_tests.append(['short-1.txt.bz2', 'TYPE_BZIP2'])
type_tests.append(['short-4.txt.bz2', 'TYPE_BZIP2'])
type_tests.append(['short-9.txt.bz2', 'TYPE_BZIP2'])
# Tar
type_tests.append(['testtar.tar', 'TYPE_TAR'])

type_tests.append(['verlinde.dvi', 'TYPE_DVI'])

# type_tests.append(['image.gif', 'TYPE_IMAGE'])
# Image
type_tests.append(['image.tif', 'TYPE_IMAGE'])
type_tests.append(['image.jpg', 'TYPE_IMAGE'])
type_tests.append(['image.png', 'TYPE_IMAGE'])
type_tests.append(['image.gif', 'TYPE_IMAGE'])  # new
type_tests.append(['centaur_1_first1k.mpg', 'TYPE_ANIM'])

type_tests.append(['pipnss.jar', 'TYPE_JAR'])
type_tests.append(['odf_test.odt', 'TYPE_ODF'])
type_tests.append(['Hellotest.docx', 'TYPE_DOCX'])
type_tests.append(['Agenda_Elegant_Style_EN.Level1.docx', 'TYPE_DOCX'])
type_tests.append(['Helloworld.xlsx', 'TYPE_XLSX'])
type_tests.append(['holtxdoc.zip', 'TYPE_ZIP'])
type_tests.append(['Hellotest.not_docx_ext', 'TYPE_ZIP'])
type_tests.append(['Helloworld.not_xlsx_ext', 'TYPE_ZIP'])
type_tests.append(['odf_test.not_odt_ext', 'TYPE_ZIP'])

type_tests.append(['0604408.pdf', 'TYPE_RAR'])
type_tests.append(['minimal.pdf', 'TYPE_PDF'])  # new

# TeX
type_tests.append(['polch.tex', 'TYPE_LATEX'])
type_tests.append(['paper-t4.1_Vienna_preprint.tex', 'TYPE_LATEX2e'])
type_tests.append(['minMac.tex', 'TYPE_LATEX2e', '', 'This file was generated on MAC with \r\n'])
type_tests.append(['pascal_petit.tex', 'TYPE_PDFLATEX'])

# a \pdfoutput=1 may come in various places, all valid
type_tests.append(['pdfoutput_before_documentclass.tex', 'TYPE_PDFLATEX'])
type_tests.append(['pdfoutput_sameline_documentclass.tex', 'TYPE_PDFLATEX'])
type_tests.append(['pdfoutput_after_documentclass.tex', 'TYPE_PDFLATEX'])
type_tests.append(['pdfoutput_after_documentclass_big_comment_before.tex', 'TYPE_PDFLATEX'])
# but if we put it too late it is ignored
type_tests.append(['pdfoutput_too_far_after_documentclass.tex', 'TYPE_LATEX2e'])
type_tests.append(['pdfoutput_too_far_after_documentclass_big_comment_before.tex', 'TYPE_LATEX2e'])
# EPS
type_tests.append(['dos_eps_1.eps', 'TYPE_DOS_EPS'])
type_tests.append(['dos_eps_2.eps', 'TYPE_DOS_EPS'])

# Need MAC

# font files must not be detected as simple PS
type_tests.append(['rtxss.pfb', 'TYPE_PS_FONT'])
type_tests.append(['c059036l.pfb', 'TYPE_PS_FONT'])
type_tests.append(['hrscs.pfa', 'TYPE_PS_FONT'])
type_tests.append(['bchbi.pfa', 'TYPE_PS_FONT'])
type_tests.append(['mutau2-sub_first10kB.tar', 'TYPE_PS_PC', '',
                   'Should really be TYPE_TAR but this is old pre-posix tar which we will not support. Doing so would require re-implementation of the c-code used by the unix file command, there are no magic codes for this. http://issues.library.cornell.edu/browse/ARXIVDEV-146'])
# error cases
type_tests.append(['10240_null_chars.tar', 'TYPE_FAILED'])
type_tests.append(['file_does_not_exit', 'TYPE_FAILED'])

type_tests.append(['fmultipart.txt', 'TYPE_FAILED'])
type_tests.append(['multipart.txt', 'TYPE_MULTI_PART_MIME'])
type_tests.append(['one.ps', 'TYPE_POSTSCRIPT'])
type_tests.append(['index.html', 'TYPE_HTML'])
type_tests.append(['sample.bib', 'TYPE_BIBTEX'])  # new

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
        self.assertEqual(get_type_name('TYPE_LATEX'), 'LaTeX', 'Lookup type name')
        self.assertEqual(get_type_name('TYPE_TAR'), 'TAR archive', 'Lookup type name')
        self.assertEqual(get_type_name('TYPE_DAVID'), 'unknown', 'Lookup name for non existent type')


    def test_is_tex_type(self):
        """Test that TeX file types are identified correctly."""
        self.assertTrue(is_tex_type('TYPE_LATEX'), 'Expected TeX file type')
        self.assertTrue(is_tex_type('TYPE_TEX'), 'Expected TeX file type')
        self.assertTrue(is_tex_type('TYPE_TEX_priority2'), 'Expected TeX file type')
        self.assertFalse(is_tex_type('TYPE_HTML'), 'Expected non-TeX file type')


    def test_type_priority(self):
        """Spot check type priorities."""
        self.assertEqual(get_type_priority('TYPE_DOES_NOT_EXIST'), 0,
                         'Unknown type should return lowest priorit=0')
        self.assertLess(get_type_priority('TYPE_BIBTEX'), get_type_priority('TYPE_TEX'),
                        'TeX source higher priority than BibTeX')
        self.assertLess(get_type_priority('TYPE_TEX'), get_type_priority('TYPE_PDFTEX'),
                        'PDFTEX is higher priority then plain TEX source.')
        self.assertLess(get_type_priority('TYPE_LATEX'), get_type_priority('TYPE_LATEX2e'),
                        'PDFTEX is higher priority then plain TEX source.')
        self.assertLess(get_type_priority('TYPE_LATEX2e'), get_type_priority('TYPE_PDFLATEX'),
                        'PDFTEX is higher priority then plain TEX source.')

        self.assertLess(get_type_priority('TYPE_LATEX'), get_type_priority('TYPE_README'),
                        'README directives file higher priority than TeX source')

        # Add some specific priority tests to catch inadvertant changes to new list
        self.assertEqual(get_type_priority('TYPE_ABORT'), 1,
                         'Expect signal for immediate stop.')
        self.assertEqual(get_type_priority('TYPE_FAILED'), 2,
                         'Expect priority for TYPE_FAILED type guess.')
        self.assertEqual(get_type_priority('TYPE_PDF'), 13,
                         'Expect priority for TYPE_PDF type guess.')
        self.assertEqual(get_type_priority('TYPE_TEX'), 18,
                         'Expect priority for TYPE_TEX type guess.')
        self.assertEqual(get_type_priority('TYPE_LATEX'), 24,
                         'Expect priority for TYPE_LATEX type guess.')
        self.assertEqual(get_type_priority('TYPE_ZIP'), 39,
                         'Expect priority for TYPE_ZIP type guess.')
        self.assertEqual(get_type_priority('TYPE_INCLUDE'), 48,
                         'Expect priority for TYPE_INCLUDE type guess.')


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
        self.assertTrue(_is_tex_type('TYPE_TEX_PRIORITY'), 'Expected TeX file type')
        self.assertFalse(_is_tex_type('TYPE_TEX_FAKE'), 'Expected non-TeX file type')
